#!/usr/bin/env bash
# scratch-guard-test.sh — self-test for scripts/lib/scratch-guard.sh and its consumers.
# Usage: bash tests/scratch-guard-test.sh
# Prints one FAIL line per broken case and exits non-zero; exits 0 when all pass.

set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LIB="${REPO_ROOT}/cdev/scripts/lib/scratch-guard.sh"
RM="${REPO_ROOT}/cdev/scripts/rm-tmp.sh"
FD="${REPO_ROOT}/cdev/scripts/fetch-diff.sh"

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
same cdev/scripts/lib/scratch-guard.sh src/cdev/scripts/lib/scratch-guard.sh
same cdev/scripts/lib/scratch-guard.sh creview/scripts/lib/scratch-guard.sh
same cdev/scripts/lib/scratch-guard.sh src/creview/scripts/lib/scratch-guard.sh
same cdev/scripts/rm-tmp.sh src/cdev/scripts/rm-tmp.sh
same cdev/scripts/rm-tmp.sh creview/scripts/rm-tmp.sh
same cdev/scripts/rm-tmp.sh src/creview/scripts/rm-tmp.sh
same cdev/scripts/fetch-diff.sh src/cdev/scripts/fetch-diff.sh
same creview/scripts/fetch-diff.sh src/creview/scripts/fetch-diff.sh

# --- syntax --------------------------------------------------------------------
for f in cdev/scripts/lib/scratch-guard.sh cdev/scripts/rm-tmp.sh cdev/scripts/fetch-diff.sh \
         creview/scripts/fetch-diff.sh; do
    bash -n "${REPO_ROOT}/${f}" || { note "FAIL: bash -n ${f}"; fail=1; }
done

# --- unit cases (sandbox) -------------------------------------------------------
SANDBOX="$(mktemp -d)"
trap 'rm -rf "${SANDBOX}"' EXIT
mkdir -p "${SANDBOX}/proj/.claude/tmp/sub" "${SANDBOX}/outside"
: > "${SANDBOX}/proj/.claude/tmp/sub/file.txt"
: > "${SANDBOX}/outside/victim.txt"
cd "${SANDBOX}/proj"

. "${LIB}"

guard_out=""
t() { # <expected-rc> [scratch_guard args...]
    local expected="$1" rc=0
    shift
    guard_out="$(scratch_guard "$@" 2>/dev/null)" || rc=$?
    check "scratch_guard $*" "${expected}" "${rc}"
}

# accepted forms
t 0 .claude/tmp/sub
t 0 ./.claude/tmp/sub
t 0 "${PWD}/.claude/tmp/sub"
# rejected: outside / traversal / spoofed prefixes / bare root disguises
t 1 /etc/passwd
t 1 "${SANDBOX}/outside/victim.txt"
t 1 "C:/outside/victim.txt"
t 1 .claude/tmp/../evil
t 1 .claude/tmp/foo..bar
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

# normalization output
out="$(scratch_guard ./.claude/tmp//sub/. 2>/dev/null)"
[[ "${out}" == ".claude/tmp/sub" ]] \
    || { note "FAIL: normalization (got '${out}')"; fail=1; }

# symlink escape (requires a real symlink; MSYS may create a copy instead — skip then)
MSYS=winsymlinks:nativestrict ln -s ../../../outside .claude/tmp/esc 2>/dev/null || true
if [[ -L .claude/tmp/esc ]]; then
    t 1 -p .claude/tmp/esc/victim.txt
else
    note "SKIP: symlink escape case (real symlinks unavailable on this platform)"
fi

# --- rm-tmp.sh end-to-end --------------------------------------------------------
mkdir -p .claude/tmp/e2e/dir
: > .claude/tmp/e2e/dir/f
rc=0; bash "${RM}" .claude/tmp/e2e/dir 2>/dev/null || rc=$?
check "rm-tmp legit delete" 0 "${rc}"
[[ ! -e .claude/tmp/e2e/dir ]] || { note "FAIL: rm-tmp did not delete the target"; fail=1; }
rc=0; bash "${RM}" .claude/tmp/ 2>/dev/null || rc=$?
check "rm-tmp bare root rejected" 1 "${rc}"
rc=0; bash "${RM}" .claude/tmp/gone/x 2>/dev/null || rc=$?
check "rm-tmp missing parent skipped" 0 "${rc}"
rc=0; bash "${RM}" "${SANDBOX}/outside/victim.txt" 2>/dev/null || rc=$?
check "rm-tmp outside rejected" 1 "${rc}"
[[ -e "${SANDBOX}/outside/victim.txt" ]] || { note "FAIL: rm-tmp deleted outside file"; fail=1; }

# --- fetch-diff.sh (cdev) end-to-end ----------------------------------------------
git init -q .
: > tracked.txt
rc=0; bash "${FD}" snapshot .claude/tmp/e2e/baseline 2>/dev/null || rc=$?
check "fetch-diff snapshot ok" 0 "${rc}"
[[ -s .claude/tmp/e2e/baseline ]] || { note "FAIL: snapshot wrote no baseline"; fail=1; }
rc=0; bash "${FD}" snapshot "${SANDBOX}/outside/base" 2>/dev/null || rc=$?
check "fetch-diff outside OUT rejected" 1 "${rc}"
echo changed > tracked.txt
rc=0; bash "${FD}" diff .claude/tmp/e2e/baseline .claude/tmp/e2e/changes.txt 2>/dev/null || rc=$?
check "fetch-diff diff ok" 0 "${rc}"
grep -q '=== Diff (since coding start) ===' .claude/tmp/e2e/changes.txt 2>/dev/null \
    || { note "FAIL: diff output missing expected section"; fail=1; }
printf '%s\n' '--output=pwn' > .claude/tmp/e2e/bad-baseline
rc=0; bash "${FD}" diff .claude/tmp/e2e/bad-baseline .claude/tmp/e2e/changes2.txt 2>/dev/null || rc=$?
check "fetch-diff tampered baseline rejected" 1 "${rc}"

if [[ "${fail}" -eq 0 ]]; then
    note "PASS: all scratch-guard cases"
fi
exit "${fail}"
