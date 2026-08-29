#!/usr/bin/env bash
# scratch-guard-test.sh — self-test for scripts/lib/scratch-guard.py and its consumers.
# Usage: bash tests/scratch-guard-test.sh
# Prints one FAIL line per broken case and exits non-zero; exits 0 when all pass.

set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
GUARD="${REPO_ROOT}/cdev/scripts/lib/scratch-guard.py"
CJ="${REPO_ROOT}/cdev/scripts/check-jsonl.py"
RM="${REPO_ROOT}/cdev/scripts/del-tmp.sh"
FD="${REPO_ROOT}/cdev/scripts/fetch-diff.sh"
CFD="${REPO_ROOT}/creview/scripts/fetch-diff.sh"

fail=0
note() { printf '%s\n' "$*"; }
check() { # <name> <expected-rc> <actual-rc>
    if [[ "$2" -ne "$3" ]]; then
        note "FAIL: $1 (expected rc=$2, got rc=$3)"
        fail=1
    fi
}

# --- the shared copies must stay byte-identical -------------------------------
same() {
    cmp -s "${REPO_ROOT}/$1" "${REPO_ROOT}/$2" || { note "FAIL: $1 and $2 differ"; fail=1; }
}
same cdev/scripts/lib/scratch-guard.py src/cdev/scripts/lib/scratch-guard.py
same cdev/scripts/lib/scratch-guard.py creview/scripts/lib/scratch-guard.py
same cdev/scripts/lib/scratch-guard.py src/creview/scripts/lib/scratch-guard.py
same cdev/scripts/del-tmp.sh src/cdev/scripts/del-tmp.sh
same cdev/scripts/del-tmp.sh creview/scripts/del-tmp.sh
same cdev/scripts/del-tmp.sh src/creview/scripts/del-tmp.sh
same cdev/scripts/check-jsonl.py src/cdev/scripts/check-jsonl.py
same cdev/scripts/check-jsonl.py creview/scripts/check-jsonl.py
same cdev/scripts/check-jsonl.py src/creview/scripts/check-jsonl.py
same cdev/scripts/fetch-diff.sh src/cdev/scripts/fetch-diff.sh
same creview/scripts/fetch-diff.sh src/creview/scripts/fetch-diff.sh

# --- consumer scripts must carry the executable bit in the git index ----------
mode_check() { # <repo-relative-script>
    local entry mode
    entry="$(git -C "${REPO_ROOT}" ls-files -s -- "$1")"
    mode="${entry%% *}"
    [[ "${mode}" == "100755" ]] \
        || { note "FAIL: $1 git mode '${mode:-missing}' (expected 100755)"; fail=1; }
}
for d in cdev creview src/cdev src/creview; do
    for s in fetch-diff.sh del-tmp.sh; do
        mode_check "${d}/scripts/${s}"
    done
done

# --- syntax --------------------------------------------------------------------
for f in cdev/scripts/del-tmp.sh cdev/scripts/fetch-diff.sh creview/scripts/fetch-diff.sh; do
    bash -n "${REPO_ROOT}/${f}" || { note "FAIL: bash -n ${f}"; fail=1; }
done

# --- unit cases (sandbox) -------------------------------------------------------
SANDBOX="$(mktemp -d)"
trap 'cd / && rm -rf "${SANDBOX}"' EXIT
PYTHONPYCACHEPREFIX="${SANDBOX}/pycache" python3 -m py_compile "${GUARD}" \
    || { note "FAIL: python3 -m py_compile scratch-guard.py"; fail=1; }
PYTHONPYCACHEPREFIX="${SANDBOX}/pycache" python3 -m py_compile "${CJ}" || { note "FAIL: python3 -m py_compile check-jsonl.py"; fail=1; }
mkdir -p "${SANDBOX}/proj/.claude/tmp/sub" "${SANDBOX}/outside"
: > "${SANDBOX}/proj/.claude/tmp/sub/file.txt"
: > "${SANDBOX}/outside/victim.txt"
cd "${SANDBOX}/proj" || exit 1

run_guard() { python3 "${GUARD}" "$@"; }

t() { # <expected-rc> [guard args...]
    local expected="$1" rc=0
    shift
    run_guard "$@" >/dev/null 2>&1 || rc=$?
    check "scratch-guard $*" "${expected}" "${rc}"
}

# accepted forms
t 0 .claude/tmp/sub
t 0 ./.claude/tmp/sub
t 0 "${PWD}/.claude/tmp/sub"
t 0 .claude/tmp/foo..bar
# rejected: outside / traversal / spoofed prefixes / bare root disguises
t 1 /etc/passwd
t 1 "${SANDBOX}/outside/victim.txt"
t 1 "C:/outside/victim.txt"
t 1 .claude/tmp/../evil
t 1 .claude/tmpX/y
t 1 .claude/tmp
t 1 .claude/tmp/
t 1 .claude/tmp//
t 1 .claude/tmp/.
t 1 .claude/tmp/./
t 1 ""
# physical mode
t 0 -p .claude/tmp/sub/file.txt
t 3 -p .claude/tmp/nonexistent/x
t 1 -p .claude/tmp/sub/file.txt/child
# write-target mode
t 0 -w .claude/tmp/sub/file.txt
t 0 -w .claude/tmp/sub/newfile
t 3 -w .claude/tmp/nonexistent/x

# normalization output
out="$(run_guard ./.claude/tmp//sub/. 2>/dev/null)"
[[ "${out}" == ".claude/tmp/sub" ]] \
    || { note "FAIL: normalization (got '${out}')"; fail=1; }

# symlink escapes (require real symlinks; MSYS may create a copy instead — skip then)
MSYS=winsymlinks:nativestrict ln -s ../../../outside .claude/tmp/esc 2>/dev/null || true
if [[ -L .claude/tmp/esc ]]; then
    t 1 -p .claude/tmp/esc/victim.txt
    # missing subpath under a symlinked ancestor must be rejected (rc=1),
    # not reported as a creatable missing parent (rc=3)
    t 1 -w .claude/tmp/esc/sub/out.txt
    MSYS=winsymlinks:nativestrict ln -s ../../../outside/victim.txt .claude/tmp/lnk 2>/dev/null || true
    if [[ -L .claude/tmp/lnk ]]; then
        t 1 -w .claude/tmp/lnk
    else
        note "SKIP: -w symlink-to-file case (symlink creation failed)"
    fi
    MSYS=winsymlinks:nativestrict ln -s ../../../outside/gone .claude/tmp/dangling 2>/dev/null || true
    if [[ -L .claude/tmp/dangling ]]; then
        t 1 -w .claude/tmp/dangling
    else
        note "SKIP: -w dangling-symlink case (symlink creation failed)"
    fi
else
    note "SKIP: symlink escape cases (real symlinks unavailable on this platform)"
fi

# --- del-tmp.sh end-to-end --------------------------------------------------------
mkdir -p .claude/tmp/e2e/dir
: > .claude/tmp/e2e/dir/f
rc=0; bash "${RM}" .claude/tmp/e2e/dir 2>/dev/null || rc=$?
check "del-tmp legit delete" 0 "${rc}"
[[ ! -e .claude/tmp/e2e/dir ]] || { note "FAIL: del-tmp did not delete the target"; fail=1; }
rc=0; bash "${RM}" .claude/tmp/ 2>/dev/null || rc=$?
check "del-tmp bare root rejected" 1 "${rc}"
rc=0; bash "${RM}" .claude/tmp/gone/x 2>/dev/null || rc=$?
check "del-tmp missing parent skipped" 0 "${rc}"
rc=0; bash "${RM}" "${SANDBOX}/outside/victim.txt" 2>/dev/null || rc=$?
check "del-tmp outside rejected" 1 "${rc}"
[[ -e "${SANDBOX}/outside/victim.txt" ]] || { note "FAIL: del-tmp deleted outside file"; fail=1; }
if [[ -L .claude/tmp/esc ]]; then
    rc=0; bash "${RM}" .claude/tmp/esc 2>/dev/null || rc=$?
    check "del-tmp symlink entry delete" 0 "${rc}"
    [[ ! -L .claude/tmp/esc ]] || { note "FAIL: del-tmp left the symlink entry"; fail=1; }
    [[ -e "${SANDBOX}/outside/victim.txt" ]] \
        || { note "FAIL: del-tmp followed the symlink and deleted its target"; fail=1; }
fi

# --- fetch-diff.sh (cdev) end-to-end ----------------------------------------------
git init -q .
: > tracked.txt
rc=0; bash "${FD}" snapshot .claude/tmp/e2e/baseline 2>/dev/null || rc=$?
check "fetch-diff snapshot ok" 0 "${rc}"
[[ -s .claude/tmp/e2e/baseline ]] || { note "FAIL: snapshot wrote no baseline"; fail=1; }
rc=0; bash "${FD}" snapshot "${SANDBOX}/outside/base" 2>/dev/null || rc=$?
check "fetch-diff outside OUT rejected" 1 "${rc}"
MSYS=winsymlinks:nativestrict ln -s ../../../outside .claude/tmp/esc 2>/dev/null || true
if [[ -L .claude/tmp/esc ]]; then
    rc=0; bash "${FD}" snapshot .claude/tmp/esc/sub/out.txt 2>/dev/null || rc=$?
    check "fetch-diff OUT under symlinked ancestor rejected" 1 "${rc}"
    [[ ! -e "${SANDBOX}/outside/sub" ]] \
        || { note "FAIL: fetch-diff created a directory outside scratch via symlink"; fail=1; }
    rm .claude/tmp/esc
else
    note "SKIP: fetch-diff symlinked OUT case (real symlinks unavailable on this platform)"
fi
echo changed > tracked.txt
rc=0; bash "${FD}" diff .claude/tmp/e2e/baseline .claude/tmp/e2e/changes.txt 2>/dev/null || rc=$?
check "fetch-diff diff ok" 0 "${rc}"
grep -q '=== Diff (since coding start) ===' .claude/tmp/e2e/changes.txt 2>/dev/null \
    || { note "FAIL: diff output missing expected section"; fail=1; }
printf '%s\n' '--output=pwn' > .claude/tmp/e2e/bad-baseline
rc=0; bash "${FD}" diff .claude/tmp/e2e/bad-baseline .claude/tmp/e2e/changes2.txt 2>/dev/null || rc=$?
check "fetch-diff tampered baseline rejected" 1 "${rc}"

# --- fetch-diff.sh (creview) end-to-end: base branch validation -------------------
git -c user.email=test@test -c user.name=test -c commit.gpgsign=false \
    commit -q --allow-empty -m init
rc=0; bash "${CFD}" HEAD .claude/tmp/e2e/review.txt 2>/dev/null || rc=$?
check "creview fetch-diff valid base accepted" 0 "${rc}"
grep -q '=== Commit Log' .claude/tmp/e2e/review.txt 2>/dev/null \
    || { note "FAIL: creview fetch-diff output missing expected section"; fail=1; }
rc=0; bash "${CFD}" no-such-ref .claude/tmp/e2e/review2.txt 2>/dev/null || rc=$?
check "creview fetch-diff missing ref rejected" 1 "${rc}"
rc=0; bash "${CFD}" --output=pwn .claude/tmp/e2e/review3.txt 2>/dev/null || rc=$?
check "creview fetch-diff option-like base rejected" 1 "${rc}"
rc=0; bash "${CFD}" HEAD..HEAD .claude/tmp/e2e/review4.txt 2>/dev/null || rc=$?
check "creview fetch-diff range base rejected" 1 "${rc}"

# --- check-jsonl.py accepts both shapes and rejects malformed input ---------------
JD="${SANDBOX}/jsonl"
mkdir -p "${JD}"
echo '{"id":"C-1"}' > "${JD}/object.jsonl"
{ echo '{'; echo '  "id": "C-1"'; echo '}'; } > "${JD}/pretty.jsonl"
{ echo '{"a":1}'; echo '{"b":2}'; } > "${JD}/lines.jsonl"
{ echo '{"a":1}'; echo '{"b":2'; echo '{"c":3}'; } > "${JD}/broken.jsonl"
echo '{"a":1},' > "${JD}/trailing.jsonl"
: > "${JD}/empty.jsonl"
for case in object:0 pretty:0 lines:0 broken:1 trailing:1 empty:1 missing:1; do
    rc=0; python3 "${CJ}" "${JD}/${case%%:*}.jsonl" >/dev/null 2>&1 || rc=$?
    check "check-jsonl ${case%%:*}" "${case##*:}" "${rc}"
done
rc=0; python3 "${CJ}" >/dev/null 2>&1 || rc=$?
check "check-jsonl no argument" 1 "${rc}"
rc=0; python3 "${CJ}" "${JD}/object.jsonl" "${JD}/broken.jsonl" >/dev/null 2>&1 || rc=$?
check "check-jsonl one bad among many" 1 "${rc}"

if [[ "${fail}" -eq 0 ]]; then
    note "PASS: all scratch-guard cases"
fi
exit "${fail}"
