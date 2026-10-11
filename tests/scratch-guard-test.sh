#!/usr/bin/env bash
# scratch-guard-test.sh — self-test for scripts/lib/scratch-guard.py, its consumers, and worktree.sh.
# Usage: bash tests/scratch-guard-test.sh
# Prints one FAIL line per broken case and exits non-zero; exits 0 when all pass.

set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
GUARD="${REPO_ROOT}/cdev/scripts/lib/scratch-guard.py"
CJ="${REPO_ROOT}/cdev/scripts/check-jsonl.py"
RM="${REPO_ROOT}/cdev/scripts/del-tmp.sh"
FD="${REPO_ROOT}/cdev/scripts/fetch-diff.sh"
CFD="${REPO_ROOT}/creview/scripts/fetch-diff.sh"
WT="${REPO_ROOT}/cdev/scripts/worktree.sh"

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
for d in src/cdev creview src/creview cprompt src/cprompt; do
    same cdev/scripts/worktree.sh "${d}/scripts/worktree.sh"
done

# --- consumer scripts must carry the executable bit in the git index ----------
mode_check() { # <repo-relative-script>
    local entry mode
    entry="$(git -C "${REPO_ROOT}" ls-files -s -- "$1")"
    mode="${entry%% *}"
    [[ "${mode}" == "100755" ]] \
        || { note "FAIL: $1 git mode '${mode:-missing}' (expected 100755)"; fail=1; }
}
for d in cdev creview src/cdev src/creview; do
    for s in fetch-diff.sh del-tmp.sh worktree.sh; do
        mode_check "${d}/scripts/${s}"
    done
done
for d in cprompt src/cprompt; do
    mode_check "${d}/scripts/worktree.sh"
done

# --- syntax --------------------------------------------------------------------
for f in cdev/scripts/del-tmp.sh cdev/scripts/fetch-diff.sh creview/scripts/fetch-diff.sh \
    cdev/scripts/worktree.sh; do
    bash -n "${REPO_ROOT}/${f}" || { note "FAIL: bash -n ${f}"; fail=1; }
done

# --- unit cases (sandbox) -------------------------------------------------------
SANDBOX="$(mktemp -d)"
trap 'cd / && { chmod -R u+rwx "${SANDBOX}" 2>/dev/null; rm -rf "${SANDBOX}"; }' EXIT
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

# --- worktree.sh + scratch dir of another working tree ----------------------------
MAIN="$(git rev-parse --show-toplevel)"
rc=0; bash "${FD}" snapshot .claude/tmp/e2e/wt-baseline 2>/dev/null || rc=$?
check "fetch-diff snapshot before worktree" 0 "${rc}"
out="$(bash "${WT}" create feat/wt 2>/dev/null)"; rc=$?
check "worktree create new branch" 0 "${rc}"
WT_PATH="$(printf '%s\n' "${out}" | sed -n 's/^worktree_path=//p')"
[[ "${WT_PATH}" == "${MAIN}/.claude/worktrees/feat-wt" && -d "${WT_PATH}" ]] \
    || { note "FAIL: worktree create printed '${WT_PATH}'"; fail=1; }
[[ "$(printf '%s\n' "${out}" | sed -n 's/^main_root=//p')" == "${MAIN}" ]] \
    || { note "FAIL: worktree create main_root"; fail=1; }
rc=0; bash "${WT}" create feat/wt >/dev/null 2>&1 || rc=$?
check "worktree create existing path rejected" 1 "${rc}"
rc=0; bash "${WT}" create "$(git branch --show-current)" >/dev/null 2>&1 || rc=$?
[[ "${rc}" -ne 0 ]] || { note "FAIL: worktree create on the checked-out branch accepted"; fail=1; }
for bad in -x 'a..b' ''; do
    rc=0; bash "${WT}" create "${bad}" >/dev/null 2>&1 || rc=$?
    [[ "${rc}" -ne 0 ]] || { note "FAIL: worktree create accepted branch '${bad}'"; fail=1; }
done

cd "${WT_PATH}" || exit 1
t 0 -w "${MAIN}/.claude/tmp/sub/newfile"
t 3 -w "${MAIN}/.claude/tmp/wt-new/x"
t 1 "${MAIN}/tracked.txt"
t 1 "${MAIN}/.claude/tmp"
t 1 "${MAIN}/.claude/tmp/../escape"
t 1 "${SANDBOX}/outside/victim.txt"
out="$(run_guard "${MAIN}/.claude/tmp//sub/." 2>/dev/null)"
[[ "${out}" == "${MAIN}/.claude/tmp/sub" ]] \
    || { note "FAIL: cross-worktree normalization (got '${out}')"; fail=1; }
MSYS=winsymlinks:nativestrict ln -s ../../../outside "${MAIN}/.claude/tmp/esc" 2>/dev/null || true
if [[ -L "${MAIN}/.claude/tmp/esc" ]]; then
    t 1 -w "${MAIN}/.claude/tmp/esc/sub/out.txt"
    rm "${MAIN}/.claude/tmp/esc"
fi
mkdir -p "${MAIN}/.claude/tmp/wt-e2e/dir"
rc=0; bash "${RM}" "${MAIN}/.claude/tmp/wt-e2e/dir" 2>/dev/null || rc=$?
check "del-tmp cross-worktree delete" 0 "${rc}"
[[ ! -e "${MAIN}/.claude/tmp/wt-e2e/dir" ]] || { note "FAIL: cross-worktree delete"; fail=1; }
rc=0; bash "${FD}" snapshot "${MAIN}/.claude/tmp/wt-e2e/baseline" 2>/dev/null || rc=$?
check "fetch-diff cross-worktree snapshot" 0 "${rc}"
[[ -s "${MAIN}/.claude/tmp/wt-e2e/baseline" ]] || { note "FAIL: cross-worktree baseline"; fail=1; }
GONE="$(cd "${SANDBOX}" && pwd -P)/gone-wt"
for lock in '' --lock; do
    if git worktree add -q --detach ${lock} "${GONE}" >/dev/null 2>&1; then
        rm -rf "${GONE}"
        t 1 -w "${GONE}/.claude/tmp/x/out.txt"
        mkdir "${GONE}"
        t 1 -w "${GONE}/.claude/tmp/x/out.txt"
        rmdir "${GONE}"
        [[ -z "${lock}" ]] || git worktree unlock "${GONE}"
        git worktree prune
    else
        note "FAIL: git worktree add for the removed-worktree case (${lock:-unlocked})"; fail=1
    fi
done
# git lists linked worktrees sorted by path, so the unreachable locked entry precedes LATER.
HIDDEN="$(cd "${SANDBOX}" && pwd -P)/a-hidden"
LATER="$(cd "${SANDBOX}" && pwd -P)/b-later"
if [[ "$(id -u)" -ne 0 ]]; then
    if git worktree add -q --detach --lock "${HIDDEN}/wt" >/dev/null 2>&1 \
        && git worktree add -q --detach "${LATER}" >/dev/null 2>&1; then
        mkdir -p "${LATER}/.claude/tmp/x"
        chmod 000 "${HIDDEN}"
        t 0 -w "${LATER}/.claude/tmp/x/out.txt"
        chmod 755 "${HIDDEN}"
    else
        note "FAIL: git worktree add for the unreachable-worktree case"; fail=1
    fi
    git worktree remove -f -f "${HIDDEN}/wt" >/dev/null 2>&1
    git worktree remove -f "${LATER}" >/dev/null 2>&1
fi
: > "${WT_PATH}/dirty.txt"
cd "${MAIN}" || exit 1
rc=0; bash "${CFD}" HEAD .claude/tmp/e2e/wt-review.txt 2>/dev/null || rc=$?
check "creview fetch-diff with leftover worktree" 0 "${rc}"
! grep -qF '.claude/worktrees' .claude/tmp/e2e/wt-review.txt \
    || { note "FAIL: creview fetch-diff listed .claude/worktrees"; fail=1; }
rc=0; bash "${FD}" diff .claude/tmp/e2e/wt-baseline .claude/tmp/e2e/wt-changes.txt 2>/dev/null \
    || rc=$?
check "fetch-diff diff with leftover worktree" 0 "${rc}"
! grep -qF '.claude/worktrees' .claude/tmp/e2e/wt-changes.txt \
    || { note "FAIL: cdev fetch-diff listed .claude/worktrees"; fail=1; }

rc=0; bash "${WT}" remove "${WT_PATH}" >/dev/null 2>&1 || rc=$?
[[ "${rc}" -ne 0 && -d "${WT_PATH}" ]] || { note "FAIL: worktree remove deleted a dirty worktree"; fail=1; }
rm "${WT_PATH}/dirty.txt"
rc=0; bash "${WT}" remove "${WT_PATH}" >/dev/null 2>&1 || rc=$?
check "worktree remove clean" 0 "${rc}"
[[ ! -e "${WT_PATH}" && ! -e "${MAIN}/.claude/worktrees" ]] \
    || { note "FAIL: worktree remove left files behind"; fail=1; }
git show-ref --verify --quiet refs/heads/feat/wt || { note "FAIL: worktree remove dropped the branch"; fail=1; }
rc=0; bash "${WT}" create feat/wt >/dev/null 2>&1 || rc=$?
check "worktree create existing branch" 0 "${rc}"
rc=0; bash "${WT}" remove "${WT_PATH}" >/dev/null 2>&1 || rc=$?
check "worktree remove after reuse" 0 "${rc}"
rc=0; bash "${WT}" remove "${MAIN}" >/dev/null 2>&1 || rc=$?
[[ "${rc}" -ne 0 ]] || { note "FAIL: worktree remove accepted the main worktree"; fail=1; }

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
