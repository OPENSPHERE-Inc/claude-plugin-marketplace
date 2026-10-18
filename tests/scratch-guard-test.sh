#!/usr/bin/env bash
# scratch-guard-test.sh — self-test for scripts/lib/scratch-guard.py, its consumers, worktree.sh,
# gh-pr.py's helpers and sparse checkout, and gh-pr.py remove's path check.
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
GHPR="${REPO_ROOT}/creview/scripts/gh-pr.py"

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
same creview/scripts/gh-pr.py src/creview/scripts/gh-pr.py
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
PYTHONPYCACHEPREFIX="${SANDBOX}/pycache" python3 -m py_compile "${GHPR}" \
    || { note "FAIL: python3 -m py_compile gh-pr.py"; fail=1; }
python3 -I -B - "${GHPR}" "${SANDBOX}" <<'PY' || fail=1
import importlib.util
import os
import subprocess
import sys

spec = importlib.util.spec_from_file_location("gh_pr", sys.argv[1])
g = importlib.util.module_from_spec(spec)
spec.loader.exec_module(g)
failed = False


def report(case, want, got):
    global failed
    print(f"FAIL: gh-pr.py {case} (expected {want:.300}, got {got!r:.300})")
    failed = True


def expect(case, got, want):
    if got != want:
        report(case, repr(want), got)


def expect_error(case, func, *parts):
    try:
        got = func()
    except Exception as e:
        got = e
    if not isinstance(got, g.Error) or not all(p in str(got) for p in parts):
        report(case, f"an Error with {parts}", got)


job = "https://github.com/o/r/actions/runs/123/job/456"
for url, run_id in ((job, "123"), ("https://example.com/x", None), (None, None)):
    expect(f"check_key {url}", g.check_key({"workflowName": "w", "name": "n", "detailsUrl": url}),
           ("w", "n", run_id))

expect("any_case .mcp.json", g.any_case(".mcp.json"), ".[mM][cC][pP].[jJ][sS][oO][nN]")

# The sparse checkout cmd_checkout runs through gh, run here with git checkout.
repo, wt = os.path.join(sys.argv[2], "sparse"), os.path.join(sys.argv[2], "sparse-wt")
agent_paths = ["CLAUDE.md", "sub/claude.MD", "sub/.Claude/x.md", "AGENTS.md", ".mcp.json",
               "docs/CLAUDE.local.md"]


def git(*args, cwd=repo, env=None):
    subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t",
                    "-c", "commit.gpgsign=false", *args],
                   cwd=cwd, env=env, check=True, capture_output=True)


os.makedirs(repo)
git("init", "-q")
for path in ["sub/notes.txt", *agent_paths]:
    os.makedirs(os.path.dirname(os.path.join(repo, path)), exist_ok=True)
    with open(os.path.join(repo, path), "w") as f:
        f.write(path)
    git("add", "--", path)
    git("commit", "-qm", path)
git("branch", "tip")
base = f"HEAD~{len(agent_paths)}"
probe = dict(os.environ, GIT_CONFIG_COUNT="1", GIT_CONFIG_KEY_0="t.k", GIT_CONFIG_VALUE_0="v")
if subprocess.run(["git", "config", "--get", "t.k"], env=probe, capture_output=True,
                  text=True).stdout.strip() != "v":
    print("SKIP: gh-pr.py sparse checkout cases (git does not apply GIT_CONFIG_COUNT)")
else:
    # Under core.ignorecase=false the sparse patterns match case-sensitively, as on Linux.
    checkout = ("-c", "core.ignorecase=false", "checkout", "-q", "--detach", "tip")
    git("worktree", "add", "-q", "--no-checkout", "--detach", wt, base)
    git(*checkout, cwd=wt, env=g.leave_out_agent_files(wt, os.environ))
    expect("sparse checkout keeps sub/notes.txt",
           os.path.isfile(os.path.join(wt, "sub", "notes.txt")), True)
    expect("sparse checkout leaves out agent files", g.agent_file_left(wt), None)
    for p in agent_paths:
        expect(f"sparse checkout leaves out {p}", os.path.lexists(os.path.join(wt, p)), False)
    with open(os.path.join(wt, "sub", "CLAUDE.md"), "w"):
        pass
    expect("agent_file_left sub/CLAUDE.md", g.agent_file_left(wt), "sub/CLAUDE.md")
    expect_error("check_agent_files_left_out sub/CLAUDE.md",
                 lambda: g.check_agent_files_left_out(wt, 7),
                 "PR #7 still resolves the agent file 'sub/CLAUDE.md'", "--trust")
    git("worktree", "remove", "--force", wt)
    plain = os.path.join(sys.argv[2], "sparse-plain")
    git("worktree", "add", "-q", "--no-checkout", "--detach", plain, base)
    git(*checkout, cwd=plain)
    for p in agent_paths:
        expect(f"checkout without sparse env resolves {p}",
               os.path.lexists(os.path.join(plain, p)), True)
    expect("checkout without sparse env resolves CLAUDE.md", g.agent_file_left(plain),
           "CLAUDE.md")
    git("worktree", "remove", "--force", plain)
try:
    raised = repr(g.agent_file_left(os.path.join(sys.argv[2], "missing")))
except Exception as e:
    raised = type(e).__name__
expect("agent_file_left on a missing directory", raised, "FileNotFoundError")
expect_error("check_agent_files_left_out on a missing directory",
             lambda: g.check_agent_files_left_out(os.path.join(sys.argv[2], "missing"), 7),
             "PR #7 could not be examined for the agent files", "FileNotFoundError", "--trust")
lstat_root = os.path.join(sys.argv[2], "lstat-root")
os.makedirs(lstat_root)
real_lstat = g.os.lstat
too_long, not_found = FileNotFoundError(2, "x"), FileNotFoundError(2, "x")
too_long.winerror, not_found.winerror = 206, 2
# lstat-root has no subdirectory, so os.walk makes no lstat call of its own.
for case, error, want in (("PermissionError", PermissionError(13, "x"), "PermissionError"),
                          ("winerror 206", too_long, "FileNotFoundError"),
                          ("winerror 2", not_found, "None")):
    def lstat(path, *args, error=error, **kwargs):
        if os.path.basename(path) in g.AGENT_FILES:
            raise error
        return real_lstat(path, *args, **kwargs)
    g.os.lstat = lstat
    try:
        raised = repr(g.agent_file_left(lstat_root))
    except Exception as e:
        raised = type(e).__name__
    finally:
        g.os.lstat = real_lstat
    expect(f"agent_file_left when lstat raises {case}", raised, want)
sys.exit(1 if failed else 0)
PY
for opt in --trusted -t; do
    out="$(python3 "${GHPR}" checkout "${SANDBOX}/no-pr.json" "${opt}" 2>&1)"; rc=$?
    check "gh-pr.py checkout rejects ${opt}" 1 "${rc}"
    [[ "${out}" == *"unknown checkout option"* ]] \
        || { note "FAIL: gh-pr.py checkout ${opt} printed '${out}'"; fail=1; }
done
out="$(python3 "${GHPR}" checkout a b c 2>&1)"; rc=$?
check "gh-pr.py checkout with three arguments" 1 "${rc}"
[[ "${out}" == *"Usage:"* ]] \
    || { note "FAIL: gh-pr.py checkout with three arguments printed '${out}'"; fail=1; }
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

# --- fetch-diff.sh (creview) --pr: the pull request's attributes and renames hide nothing -
PRD="${SANDBOX}/prdiff"
prd_git() {
    git -C "${PRD}" -c user.email=test@test -c user.name=test -c commit.gpgsign=false \
        -c core.autocrlf=false "$@"
}
prd_diff() { # <mode> <from> <to> <output-name>, with rename detection on (diff.renames=true)
    (cd "${PRD}" && GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=diff.renames GIT_CONFIG_VALUE_0=true \
        bash "${CFD}" "$1" "$2" "$3" ".claude/tmp/$4")
}
# Commits: base (HEAD~3), rename (HEAD~2), attrs (HEAD~1), nested (HEAD).
mkdir -p "${PRD}/sub" && prd_git init -q && printf 'original\n' > "${PRD}/CLAUDE.md" \
    && printf 'payload line\n' > "${PRD}/fixture.txt" && prd_git add CLAUDE.md fixture.txt \
    && prd_git commit -qm base && prd_git mv fixture.txt AGENTS.md && prd_git commit -qm rename \
    && printf 'CLAUDE.md -diff\n' > "${PRD}/.gitattributes" \
    && printf 'changed\n' > "${PRD}/CLAUDE.md" && prd_git add .gitattributes CLAUDE.md \
    && prd_git commit -qm attrs && printf 'x -diff\n' > "${PRD}/sub/.GitAttributes" \
    && prd_git add sub/.GitAttributes && prd_git commit -qm nested \
    || { note "FAIL: creview fetch-diff --pr repository setup"; fail=1; }
rc=0; prd_diff --range HEAD~3 HEAD~2 range-rename.txt 2>/dev/null || rc=$?
check "creview fetch-diff --range over a rename" 0 "${rc}"
grep -q '^rename from' "${PRD}/.claude/tmp/range-rename.txt" 2>/dev/null \
    || { note "FAIL: creview fetch-diff --range control: no rename detected"; fail=1; }
rc=0; prd_diff --pr HEAD~3 HEAD~2 pr-rename.txt 2>/dev/null || rc=$?
check "creview fetch-diff --pr over a rename" 0 "${rc}"
grep -q '^+payload line$' "${PRD}/.claude/tmp/pr-rename.txt" 2>/dev/null \
    && ! grep -q '^rename from' "${PRD}/.claude/tmp/pr-rename.txt" \
    || { note "FAIL: creview fetch-diff --pr hid the content of a renamed file"; fail=1; }
if git -C "${PRD}" --attr-source=HEAD rev-parse --git-dir >/dev/null 2>&1; then
    rc=0; prd_diff --range HEAD~2 HEAD~1 range-attrs.txt 2>/dev/null || rc=$?
    check "creview fetch-diff --range over a .gitattributes change" 0 "${rc}"
    grep -q '^Binary files' "${PRD}/.claude/tmp/range-attrs.txt" 2>/dev/null \
        || { note "FAIL: creview fetch-diff --range control: CLAUDE.md is not binary"; fail=1; }
    rc=0; prd_diff --pr HEAD~2 HEAD~1 pr-attrs.txt 2>"${SANDBOX}/prdiff.err" || rc=$?
    check "creview fetch-diff --pr over a .gitattributes change" 0 "${rc}"
    grep -q '^+changed$' "${PRD}/.claude/tmp/pr-attrs.txt" 2>/dev/null \
        && ! grep -q '^Binary files' "${PRD}/.claude/tmp/pr-attrs.txt" \
        && ! grep -qF -- '--attr-source' "${SANDBOX}/prdiff.err" \
        || { note "FAIL: creview fetch-diff --pr applied the PR's .gitattributes"; fail=1; }
else
    note "SKIP: creview fetch-diff --pr attribute case (git has no --attr-source)"
fi
# A shim stands in for a Git older than 2.40, which rejects --attr-source as an unknown option.
OLDGIT="${SANDBOX}/oldgit"
mkdir -p "${OLDGIT}" \
    && printf '#!/usr/bin/env bash\n%s\nexec %q "$@"\n' \
        'case "${1:-}" in --attr-source=*) exit 129 ;; esac' "$(command -v git)" \
        > "${OLDGIT}/git" && chmod +x "${OLDGIT}/git" \
    || { note "FAIL: creview fetch-diff --pr old git shim setup"; fail=1; }
old_diff() { # <from> <to> <output-name>: prd_diff --pr with the shim first on the PATH
    (export PATH="${OLDGIT}:${PATH}"; prd_diff --pr "$@") 2>"${SANDBOX}/prdiff-old.err"
}
rc=0; old_diff HEAD~3 HEAD~2 old-rename.txt || rc=$?
check "creview fetch-diff --pr without --attr-source, .gitattributes unchanged" 0 "${rc}"
grep -q '^+payload line$' "${PRD}/.claude/tmp/old-rename.txt" 2>/dev/null \
    && ! grep -qF -- '--attr-source' "${SANDBOX}/prdiff-old.err" \
    || { note "FAIL: creview fetch-diff --pr without --attr-source: no diff or a warning"; fail=1; }
rc=0; old_diff HEAD~2 HEAD~1 old-attrs.txt || rc=$?
check "creview fetch-diff --pr without --attr-source, .gitattributes changed" 1 "${rc}"
grep -qF '.gitattributes' "${SANDBOX}/prdiff-old.err" \
    && [[ ! -e "${PRD}/.claude/tmp/old-attrs.txt" ]] \
    || { note "FAIL: creview fetch-diff --pr without --attr-source: no error or a diff"; fail=1; }
rc=0; old_diff HEAD~1 HEAD old-nested.txt || rc=$?
check "creview fetch-diff --pr without --attr-source, sub/.GitAttributes added" 1 "${rc}"
rc=0; (export GIT_LITERAL_PATHSPECS=1; old_diff HEAD~2 HEAD~1 old-literal.txt) || rc=$?
check "creview fetch-diff --pr without --attr-source under GIT_LITERAL_PATHSPECS=1" 1 "${rc}"

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
# Windows looks a bare program name up in the working directory before PATH, so a
# git.exe planted in a checked-out tree must not stand in for git.
if [[ "$(python3 -c 'import os; print(os.name)')" == nt ]]; then
    cp "$(type -P true)" git.exe
    rc=0
    env -u NoDefaultCurrentDirectoryInExePath python3 "${GUARD}" \
        -w "${MAIN}/.claude/tmp/sub/newfile" >/dev/null 2>&1 || rc=$?
    check "scratch-guard ignores a git.exe in the working directory" 0 "${rc}"
    rm git.exe
fi
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
for bad in "${WT_PATH}" "${MAIN}"; do
    rc=0; python3 "${GHPR}" remove "${bad}" >/dev/null 2>&1 || rc=$?
    [[ "${rc}" -ne 0 ]] || { note "FAIL: gh-pr.py remove accepted '${bad}'"; fail=1; }
done
[[ -d "${WT_PATH}" ]] || { note "FAIL: gh-pr.py remove deleted a worktree checkout did not add"; fail=1; }
PR_WT="${MAIN}/.claude/worktrees/creview-pr-1-20260101-000000"
if git worktree add -q --detach "${PR_WT}" >/dev/null 2>&1; then
    rc=0; python3 "${GHPR}" remove "${WT_PATH}/../${PR_WT##*/}" >/dev/null 2>&1 || rc=$?
    [[ "${rc}" -ne 0 && -d "${PR_WT}" ]] \
        || { note "FAIL: gh-pr.py remove accepted a path with a .. component"; fail=1; }
    if [[ "$(GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=t.k GIT_CONFIG_VALUE_0=v \
        git config --get t.k 2>/dev/null)" == v ]]; then
        FSM_HOOK="${SANDBOX}/fsmonitor-hook" FSM_MARK="${SANDBOX}/fsmonitor-ran"
        printf '#!/bin/sh\n: > "%s"\n' "${FSM_MARK}" > "${FSM_HOOK}"
        chmod +x "${FSM_HOOK}"
        git config core.fsmonitor "${FSM_HOOK}"
        git -C "${PR_WT}" status >/dev/null 2>&1
        if [[ -e "${FSM_MARK}" ]]; then
            rm "${FSM_MARK}"
        else
            note "SKIP: gh-pr.py remove core.fsmonitor case (git status did not run the hook)"
        fi
        rc=0; python3 "${GHPR}" remove "${PR_WT}" >/dev/null 2>&1 || rc=$?
        git config --unset core.fsmonitor
        check "gh-pr.py remove a worktree checkout adds" 0 "${rc}"
        [[ ! -e "${PR_WT}" ]] || { note "FAIL: gh-pr.py remove left the worktree behind"; fail=1; }
        [[ ! -e "${FSM_MARK}" ]] \
            || { note "FAIL: gh-pr.py remove ran the core.fsmonitor hook"; fail=1; }
    else
        note "SKIP: gh-pr.py remove success case (git does not apply GIT_CONFIG_COUNT)"
    fi
    [[ ! -e "${PR_WT}" ]] || git worktree remove --force -- "${PR_WT}" >/dev/null 2>&1
else
    note "FAIL: git worktree add for the gh-pr.py remove case"; fail=1
fi
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
