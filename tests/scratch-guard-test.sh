#!/usr/bin/env bash
# scratch-guard-test.sh — self-test for scripts/lib/scratch-guard.py, its consumers, worktree.sh,
# gh-pr.py's helpers, header parsing, and sparse checkout, gh-pr.py doc-checkout, gh-pr.py
# remove's path check, and render-review.py's metadata lines.
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
RR="${REPO_ROOT}/creview/scripts/render-review.py"

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

for name in ("-x", "a..b", "", "bad name"):
    expect_error(f"valid_branch {name!r}", lambda name=name: g.valid_branch(name),
                 "invalid branch name")
expect("valid_branch creview-pr-12", g.valid_branch("creview-pr-12"), "creview-pr-12")

docs = os.path.join(sys.argv[2], "docs")
os.makedirs(docs)


def doc(name, *bullets, eol="\n"):
    # A bullet under a severity heading is a finding's text, not a header bullet.
    path = os.path.join(docs, name)
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write(eol.join(["# Report", "", "- **Date:** 2026-01-01", *bullets, "- **Scope:** x", "",
                          "## Major", "", "- **Trust:** on", "- **Branch:** x", ""]))
    return path


A, B = "a" * 40, "b" * 64
PR_LINE = f"- **PR:** https://github.com/o/r/pull/3 (head {A}, base {B})"
expect("parse_header with no header bullets", g.parse_header(doc("none.md")),
       {"pr": None, "branch": None, "trust": "off"})
expect("parse_header PR, Branch, and Trust",
       g.parse_header(doc("full.md", PR_LINE, "- **Branch:** feat/x", "- **Trust:** on",
                          eol="\r\n")),
       {"pr": {"url": "https://github.com/o/r/pull/3", "number": 3, "head_sha": A,
               "merge_base": B, "line": 3},
        "branch": "feat/x", "trust": "on"})
expect("parse_header a non-ASCII branch",
       g.parse_header(doc("ja.md", "- **Branch:** feature/日本語"))["branch"], "feature/日本語")
for bullet in (f"- **PR:** https://github.com/o/r/pull/3/files (head {A}, base {B})",
               f"- **PR:** https://example.com/x (head {A}, base {B})",
               f"- **PR:** https://github.com/o/r/pull/3 (head {A[:39]}, base {B})",
               f"- **PR:** https://github.com/o/r/pull/3 (head {A.upper()}, base {B})",
               "- **PR:** https://github.com/o/r/pull/3",
               "- **Branch:** a$(touch x)", "- **Branch:** it's", "- **Branch:** a b",
               "- **Branch:** -x", "- **Branch:** a..b", "- **Branch:** feature/#123",
               "- **Trust:** yes", "- **Trust:** ON"):
    expect_error(f"parse_header {bullet!r}", lambda b=bullet: g.parse_header(doc("bad.md", b)),
                 "malformed review document header")
expect_error("parse_header two Trust bullets",
             lambda: g.parse_header(doc("dup.md", "- **Trust:** off", "- **Trust:** on")),
             "more than one Trust bullet")
record = doc("record.md", PR_LINE, "- **Trust:** off", eol="\r\n")
g.record_branch(record, 3, "creview-pr-3")
with open(record, encoding="utf-8", newline="") as f:
    expect("record_branch inserts the Branch bullet after the PR bullet", f.readlines()[3:6],
           [PR_LINE + "\r\n", "- **Branch:** creview-pr-3\r\n", "- **Trust:** off\r\n"])
expect("record_branch writes a bullet parse_header reads", g.parse_header(record)["branch"],
       "creview-pr-3")

# A document doc-checkout cannot update after adding a PR worktree.
saved = {name: getattr(g, name) for name in ("run", "contains", "view_pr", "checkout_pr",
                                              "record_branch", "remove_worktree")}
added_path, removed = "/m/.claude/worktrees/creview-pr-3-20260101-000000", []


def deny(*args):
    raise PermissionError("denied")


g.run = lambda cmd, **kw: saved["run"](cmd, **kw) if cmd[1] == "check-ref-format" else ""
g.contains = lambda commit: False
g.view_pr = lambda url, fields="": ("github.com", "o/r", 3, url, {"headRefOid": A})
g.checkout_pr = lambda *args: {"main_root": "/m", "worktree_path": added_path}
g.record_branch = deny
g.remove_worktree = lambda path: removed.append(path) or ""
try:
    expect_error("doc-checkout --fix-branch with a document it cannot update",
                 lambda: g.cmd_doc_checkout(doc("locked.md", PR_LINE), "--fix-branch"),
                 "the review document could not be updated")
    expect("doc-checkout removes the worktree it added for a document it cannot update",
           removed, [added_path])
finally:
    for name, value in saved.items():
        setattr(g, name, value)

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
config_count = subprocess.run(["git", "config", "--get", "t.k"], env=probe,
                              capture_output=True, text=True).stdout.strip() == "v"
if not config_count:
    print("SKIP: gh-pr.py sparse checkout cases (git does not apply GIT_CONFIG_COUNT)")
else:
    # Under core.ignorecase=false the sparse patterns match case-sensitively, as on Linux.
    checkout = ("-c", "core.ignorecase=false", "checkout", "-q", "--detach", "tip")
    git("worktree", "add", "-q", "--no-checkout", "--detach", wt, base)
    sparse_env = g.leave_out_agent_files(wt, os.environ)
    git(*checkout, cwd=wt, env=sparse_env)
    expect("sparse checkout keeps sub/notes.txt",
           os.path.isfile(os.path.join(wt, "sub", "notes.txt")), True)
    expect("sparse checkout leaves out agent files", g.agent_file_left(wt), None)
    for p in agent_paths:
        expect(f"sparse checkout leaves out {p}", os.path.lexists(os.path.join(wt, p)), False)

    def current(path):
        return subprocess.run(["git", "branch", "--show-current"], cwd=path,
                              capture_output=True, text=True).stdout.strip()

    tip = subprocess.run(["git", "rev-parse", "tip"], cwd=repo, capture_output=True,
                         text=True).stdout.strip()
    g.attach_branch(wt, "fix", tip, sparse_env)
    expect("attach_branch creates the branch", current(wt), "fix")
    expect("attach_branch keeps agent files left out", g.agent_file_left(wt), None)
    other = os.path.join(sys.argv[2], "sparse-other")
    git("worktree", "add", "-q", "--detach", other, "tip")
    git("branch", "stale", base)
    expect_error("attach_branch on a branch at another commit",
                 lambda: g.attach_branch(other, "stale", tip, os.environ), "stale",
                 "already exists")
    expect_error("attach_branch on a branch checked out elsewhere",
                 lambda: g.attach_branch(other, "fix", tip, os.environ), "fix")
    expect("attach_branch failures leave HEAD detached", current(other), "")
    git("branch", "fresh", "tip")
    g.attach_branch(other, "fresh", tip, os.environ)
    expect("attach_branch reuses a branch at the PR head", current(other), "fresh")
    git("worktree", "remove", "--force", other)
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
links = os.path.join(sys.argv[2], "links")
os.makedirs(links)
git("init", "-q", cwd=links)
blob = subprocess.run(["git", "hash-object", "-w", "--stdin"], cwd=links, input=b"x",
                      capture_output=True, check=True).stdout.strip()
index_info = b"".join(b"120000 %s\t%s\0" % (blob, p) for p in (b"a", b"l\xe9"))
subprocess.run(["git", "update-index", "-z", "--index-info"], cwd=links, input=index_info,
               capture_output=True, check=True)
try:
    g.skip_worktree_links(links, os.environ)
except g.Error as e:
    report("skip_worktree_links on a path that is not UTF-8", "no error", e)
expect("skip_worktree_links marks a path that is not UTF-8",
       subprocess.run(["git", "ls-files", "-v", "-z"], cwd=links, capture_output=True).stdout,
       b"S a\0S l\xe9\0")
# Windows decodes a path as strict UTF-8; subprocess passes str arguments through fsdecode.
real_fsdecode = g.os.fsdecode
g.os.fsdecode = lambda name: name if isinstance(name, str) else name.decode("utf-8")
try:
    expect("changed_links sets apart a path that does not decode",
           g.changed_links(links, os.environ), (["a"], [b"l\xe9"]))

    def lstat(path, *args, **kwargs):
        if path == os.path.join(links, "a"):
            raise too_long
        return real_lstat(path, *args, **kwargs)
    g.os.lstat = lstat
    expect("changed_links sets apart a path lstat fails on with winerror 206",
           g.changed_links(links, os.environ), ([], ["a", b"l\xe9"]))
    g.os.lstat = real_lstat
    os.makedirs(os.path.join(links, ".git", "info"), exist_ok=True)
    with open(os.path.join(links, ".git", "info", "sparse-checkout"), "w") as f:
        f.write("/*\n")
    for args, data in ((["--index-info"], b"120000 %s\t.CLAUDE/m\xe9\0" % blob),
                       (["--skip-worktree", "--stdin"], b".CLAUDE/m\xe9\0")):
        subprocess.run(["git", "update-index", "-z", *args], cwd=links, input=data,
                       capture_output=True, check=True)
    expect("changed_links passes over an agent path a sparse checkout leaves out",
           g.changed_links(links, os.environ), (["a"], [b"l\xe9"]))
finally:
    g.os.fsdecode, g.os.lstat = real_fsdecode, real_lstat
expect("quoted escapes the names and shows the first 3",
       g.quoted(["a\nb", "c", "d", b"l\xe9"]), "'a\\nb', 'c', 'd' and 1 more")
expect("quoted one name", g.quoted(["x"]), "'x'")
expect("quoted a name that does not decode", g.quoted([b"l\xe9"]), "b'l\\xe9'")
# cmd_remove runs changed_links under hook_free_env, which needs GIT_CONFIG_COUNT.
if not config_count:
    print("SKIP: gh-pr.py remove when changed_links fails (git does not apply GIT_CONFIG_COUNT)")
else:
    os.makedirs(os.path.join(links, ".claude", "worktrees", "creview-pr-7-20260101-000000"))
    real_changed_links, cwd = g.changed_links, os.getcwd()
    os.chdir(links)
    try:
        top = subprocess.run(["git", "rev-parse", "--show-toplevel"], capture_output=True,
                             text=True, check=True).stdout.strip()
        kept = f"{top}/.claude/worktrees/creview-pr-7-20260101-000000"
        for error in (PermissionError(13, "x"), g.Error("x")):
            def fail_examining(path, env, error=error):
                raise error
            g.changed_links = fail_examining
            case = f"remove when changed_links raises {type(error).__name__}"
            expect_error(case, lambda: g.cmd_remove(kept), "is kept", "do not run git in it",
                         "git worktree remove --force")
            expect(f"{case} keeps the worktree", os.path.isdir(kept), True)
    finally:
        g.changed_links = real_changed_links
        os.chdir(cwd)
sys.exit(1 if failed else 0)
PY
for opt in --trusted -t; do
    out="$(python3 "${GHPR}" checkout "${SANDBOX}/no-pr.json" "${opt}" 2>&1)"; rc=$?
    check "gh-pr.py checkout rejects ${opt}" 1 "${rc}"
    [[ "${out}" == *"unknown checkout option"* ]] \
        || { note "FAIL: gh-pr.py checkout ${opt} printed '${out}'"; fail=1; }
done
for args in "checkout a b c" "doc-checkout" "doc-checkout a b c" "remove" "remove a b" \
    "no-such-command"; do
    # shellcheck disable=SC2086
    out="$(python3 "${GHPR}" ${args} 2>&1)"; rc=$?
    check "gh-pr.py ${args}" 1 "${rc}"
    [[ "${out}" == *"Usage:"* ]] || { note "FAIL: gh-pr.py ${args} printed '${out}'"; fail=1; }
done
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
# Commits: base (HEAD~2), rename (HEAD~1), attrs (HEAD).
mkdir -p "${PRD}" && prd_git init -q && printf 'original\n' > "${PRD}/CLAUDE.md" \
    && printf 'payload line\n' > "${PRD}/fixture.txt" && prd_git add CLAUDE.md fixture.txt \
    && prd_git commit -qm base && prd_git mv fixture.txt AGENTS.md && prd_git commit -qm rename \
    && printf 'CLAUDE.md -diff\n' > "${PRD}/.gitattributes" \
    && printf 'changed\n' > "${PRD}/CLAUDE.md" && prd_git add .gitattributes CLAUDE.md \
    && prd_git commit -qm attrs \
    || { note "FAIL: creview fetch-diff --pr repository setup"; fail=1; }
# fetch-diff.sh --pr runs only on a git that accepts --attr-source (Git 2.41 or later).
ATTR_SOURCE_OK=0
git -C "${PRD}" --attr-source=HEAD rev-parse --git-dir >/dev/null 2>&1 && ATTR_SOURCE_OK=1
rc=0; prd_diff --range HEAD~2 HEAD~1 range-rename.txt 2>/dev/null || rc=$?
check "creview fetch-diff --range over a rename" 0 "${rc}"
grep -q '^rename from' "${PRD}/.claude/tmp/range-rename.txt" 2>/dev/null \
    || { note "FAIL: creview fetch-diff --range control: no rename detected"; fail=1; }
if [[ "${ATTR_SOURCE_OK}" -eq 1 ]]; then
    rc=0; prd_diff --pr HEAD~2 HEAD~1 pr-rename.txt 2>/dev/null || rc=$?
    check "creview fetch-diff --pr over a rename" 0 "${rc}"
    grep -q '^+payload line$' "${PRD}/.claude/tmp/pr-rename.txt" 2>/dev/null \
        && ! grep -q '^rename from' "${PRD}/.claude/tmp/pr-rename.txt" \
        || { note "FAIL: creview fetch-diff --pr hid the content of a renamed file"; fail=1; }
    rc=0; prd_diff --range HEAD~1 HEAD range-attrs.txt 2>/dev/null || rc=$?
    check "creview fetch-diff --range over a .gitattributes change" 0 "${rc}"
    grep -q '^Binary files' "${PRD}/.claude/tmp/range-attrs.txt" 2>/dev/null \
        || { note "FAIL: creview fetch-diff --range control: CLAUDE.md is not binary"; fail=1; }
    rc=0; prd_diff --pr HEAD~1 HEAD pr-attrs.txt 2>"${SANDBOX}/prdiff.err" || rc=$?
    check "creview fetch-diff --pr over a .gitattributes change" 0 "${rc}"
    grep -q '^+changed$' "${PRD}/.claude/tmp/pr-attrs.txt" 2>/dev/null \
        && ! grep -q '^Binary files' "${PRD}/.claude/tmp/pr-attrs.txt" \
        && ! grep -qF -- '--attr-source' "${SANDBOX}/prdiff.err" \
        || { note "FAIL: creview fetch-diff --pr applied the PR's .gitattributes"; fail=1; }
else
    note "SKIP: creview fetch-diff --pr rename and attribute cases (git has no --attr-source)"
fi
# A shim stands in for a Git older than 2.41, which rejects --attr-source as an unknown option.
OLDGIT="${SANDBOX}/oldgit"
mkdir -p "${OLDGIT}" \
    && printf '#!/usr/bin/env bash\n%s\nexec %q "$@"\n' \
        'case "${1:-}" in --attr-source=*) exit 129 ;; esac' "$(command -v git)" \
        > "${OLDGIT}/git" && chmod +x "${OLDGIT}/git" \
    || { note "FAIL: creview fetch-diff --pr old git shim setup"; fail=1; }
old_case() { # <case> <from> <to> <output-name>: prd_diff --pr with the shim first on the PATH
    local rc=0 err="${SANDBOX}/prdiff-old.err"
    (export PATH="${OLDGIT}:${PATH}"; prd_diff --pr "$2" "$3" "$4") 2>"${err}" || rc=$?
    check "creview fetch-diff --pr without --attr-source, $1" 1 "${rc}"
    grep -qF 'Git 2.41 or later' "${err}" && [[ ! -e "${PRD}/.claude/tmp/$4" ]] \
        || { note "FAIL: creview fetch-diff --pr on an old git, $1: no error or a diff"; fail=1; }
}
old_case ".gitattributes unchanged" HEAD~2 HEAD~1 old-rename.txt
old_case ".gitattributes changed" HEAD~1 HEAD old-attrs.txt

# --- fetch-diff.sh (creview) --pr: the pull request's .gitmodules hides no submodule change -
PRS="${SANDBOX}/prsub"
prs_git() {
    git -C "${PRS}" -c user.email=test@test -c user.name=test -c commit.gpgsign=false \
        -c core.autocrlf=false "$@"
}
prs_diff() { # <mode> <output-name>: fetch-diff.sh <mode> HEAD~1 HEAD, with diff.submodule=log
    (cd "${PRS}" && GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=diff.submodule GIT_CONFIG_VALUE_0=log \
        bash "${CFD}" "$1" HEAD~1 HEAD ".claude/tmp/$2")
}
# Commits: base, lib added as a submodule with ignore = all (HEAD~1), lib moved (HEAD).
mkdir -p "${PRS}" && prs_git init -q && prs_git commit -q --allow-empty -m base \
    && SUB_OLD="$(prs_git rev-parse HEAD)" \
    && printf '[submodule "lib"]\n\tpath = lib\n\tignore = all\n' > "${PRS}/.gitmodules" \
    && prs_git add .gitmodules && prs_git update-index --add --cacheinfo "160000,${SUB_OLD},lib" \
    && prs_git commit -qm submodule && SUB_NEW="$(prs_git rev-parse HEAD)" \
    && prs_git update-index --cacheinfo "160000,${SUB_NEW},lib" && prs_git commit -qm bump \
    || { note "FAIL: creview fetch-diff --pr submodule repository setup"; fail=1; }
rc=0; prs_diff --range range-sub.txt 2>/dev/null || rc=$?
check "creview fetch-diff --range over a submodule with ignore = all" 0 "${rc}"
[[ -s "${PRS}/.claude/tmp/range-sub.txt" ]] \
    && ! grep -q 'Subproject commit' "${PRS}/.claude/tmp/range-sub.txt" \
    || { note "FAIL: creview fetch-diff --range control: the submodule change is shown"; fail=1; }
if [[ "${ATTR_SOURCE_OK}" -eq 1 ]]; then
    rc=0; prs_diff --pr pr-sub.txt 2>/dev/null || rc=$?
    check "creview fetch-diff --pr over a submodule with ignore = all" 0 "${rc}"
    grep -q $'^M\tlib$' "${PRS}/.claude/tmp/pr-sub.txt" 2>/dev/null \
        && grep -qxF "+Subproject commit ${SUB_NEW}" "${PRS}/.claude/tmp/pr-sub.txt" \
        || { note "FAIL: creview fetch-diff --pr hid or reformatted a submodule change"; fail=1; }
else
    note "SKIP: creview fetch-diff --pr submodule case (git has no --attr-source)"
fi

# --- fetch-diff.sh (creview): a non-ASCII path is printed as it is, not octal-escaped -
PRQ="${SANDBOX}/prquote"
QNAME=$'\xe7\x94\xbb\xe5\x83\x8f.png'
prq_git() {
    git -C "${PRQ}" -c user.email=test@test -c user.name=test -c commit.gpgsign=false \
        -c core.autocrlf=false "$@"
}
mkdir -p "${PRQ}" && prq_git init -q && prq_git commit -q --allow-empty -m base \
    && printf '\x89PNG\0\1' > "${PRQ}/${QNAME}" && prq_git add -- "${QNAME}" \
    && prq_git commit -qm image \
    || { note "FAIL: creview fetch-diff non-ASCII path repository setup"; fail=1; }
rc=0
(cd "${PRQ}" && GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=core.quotePath GIT_CONFIG_VALUE_0=true \
    bash "${CFD}" --range HEAD~1 HEAD .claude/tmp/quote.txt) 2>/dev/null || rc=$?
check "creview fetch-diff --range over a non-ASCII path" 0 "${rc}"
grep -qF "$(printf 'A\t%s' "${QNAME}")" "${PRQ}/.claude/tmp/quote.txt" 2>/dev/null \
    && grep -qF "Binary files /dev/null and b/${QNAME} differ" "${PRQ}/.claude/tmp/quote.txt" \
    || { note "FAIL: creview fetch-diff octal-escaped a non-ASCII path"; fail=1; }

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

# --- gh-pr.py doc-checkout ---------------------------------------------------------
DOCS="${SANDBOX}/doc-checkout"
mkdir -p "${DOCS}"
HEAD_SHA="$(git rev-parse HEAD)"
CUR="$(git branch --show-current)"
PR_LINE="- **PR:** https://github.com/o/r/pull/3 (head ${HEAD_SHA}, base ${HEAD_SHA})"
write_doc() { # <name> <header-bullet>...
    local name="$1"
    shift
    { printf '# Report\n\n'; printf '%s\n' "$@"; printf -- '- **Scope:** x\n\n## Major\n'; } \
        > "${DOCS}/${name}"
}
field() { # <name>: prints a field of the JSON object on stdin, JSON-encoded unless a string
    python3 -c 'import json, sys
v = json.load(sys.stdin)[sys.argv[1]]
sys.stdout.buffer.write((v if isinstance(v, str) else json.dumps(v)).encode() + b"\n")' "$1"
}
shlex_join() {
    python3 -c 'import shlex, sys; sys.stdout.buffer.write(shlex.join(sys.argv[1:]).encode())' "$@"
}
doc_checkout() { python3 "${GHPR}" doc-checkout "$@"; }
write_doc none.md
write_doc bad.md "- **Trust:** yes"
write_doc no-branch.md "- **Branch:** no-such"
MOVED_SHA="$(printf 'a%.0s' {1..40})"
write_doc moved.md "- **PR:** https://github.com/o/r/pull/3 (head ${MOVED_SHA}, base ${HEAD_SHA})"
for case in "none.md --trusted|unknown doc-checkout option" \
    "bad.md|malformed review document header" "no-branch.md|no local branch no-such" \
    "moved.md|is not a remote of this repository" "missing.md|No such file"; do
    # shellcheck disable=SC2086
    set -- ${case%%|*}
    out="$(doc_checkout "${DOCS}/$1" "${@:2}" 2>&1)"; rc=$?
    check "gh-pr.py doc-checkout ${case%%|*}" 1 "${rc}"
    [[ "${out}" == *"${case#*|}"* ]] \
        || { note "FAIL: gh-pr.py doc-checkout ${case%%|*} printed '${out}'"; fail=1; }
done
set --
write_doc cur.md "- **Branch:** ${CUR}"
write_doc pr-here.md "${PR_LINE}" "- **Trust:** off"
cp "${DOCS}/pr-here.md" "${DOCS}/pr-here.orig"
for name in none.md cur.md pr-here.md; do
    out="$(doc_checkout "${DOCS}/${name}" 2>/dev/null)"; rc=$?
    check "gh-pr.py doc-checkout ${name}" 0 "${rc}"
    [[ "$(printf '%s' "${out}" | field in_place)" == true \
        && "$(printf '%s' "${out}" | field branch)" == "${CUR}" ]] \
        || { note "FAIL: gh-pr.py doc-checkout ${name} printed '${out}'"; fail=1; }
done
[[ "$(printf '%s' "${out}" | field merge_base)" == "${HEAD_SHA}" ]] \
    || { note "FAIL: gh-pr.py doc-checkout pr-here.md merge_base in '${out}'"; fail=1; }
cmp -s "${DOCS}/pr-here.md" "${DOCS}/pr-here.orig" \
    || { note "FAIL: gh-pr.py doc-checkout without --fix-branch changed the document"; fail=1; }
for run in 1 2; do
    rc=0; doc_checkout "${DOCS}/pr-here.md" --fix-branch >/dev/null 2>&1 || rc=$?
    check "gh-pr.py doc-checkout --fix-branch in place (run ${run})" 0 "${rc}"
done
[[ "$(sed -n 4p "${DOCS}/pr-here.md")" == "- **Branch:** ${CUR}" \
    && "$(grep -c '^- \*\*Branch:\*\*' "${DOCS}/pr-here.md")" == 1 ]] \
    || { note "FAIL: gh-pr.py doc-checkout --fix-branch wrote $(cat "${DOCS}/pr-here.md")"; fail=1; }
if git checkout -q --detach 2>/dev/null; then
    cp "${DOCS}/pr-here.orig" "${DOCS}/pr-detached.md"
    out="$(doc_checkout "${DOCS}/pr-detached.md" --fix-branch 2>/dev/null)"; rc=$?
    check "gh-pr.py doc-checkout --fix-branch in place on a detached HEAD" 0 "${rc}"
    [[ "$(printf '%s' "${out}" | field in_place)" == true \
        && "$(printf '%s' "${out}" | field branch)" == null ]] \
        || { note "FAIL: gh-pr.py doc-checkout --fix-branch on a detached HEAD: '${out}'"; fail=1; }
    cmp -s "${DOCS}/pr-detached.md" "${DOCS}/pr-here.orig" || {
        note "FAIL: gh-pr.py doc-checkout --fix-branch on a detached HEAD wrote" \
            "$(cat "${DOCS}/pr-detached.md")"
        fail=1
    }
    git checkout -q "${CUR}" \
        || { note "FAIL: git checkout ${CUR} after the detached HEAD case"; fail=1; }
else
    note "FAIL: git checkout --detach for the detached HEAD case"; fail=1
fi
# A branch name a Branch bullet cannot hold is worked on in place but not recorded.
if git checkout -q -b 'feature/#123' 2>/dev/null; then
    cp "${DOCS}/pr-here.orig" "${DOCS}/pr-hash.md"
    out="$(doc_checkout "${DOCS}/pr-hash.md" --fix-branch 2>/dev/null)"; rc=$?
    check "gh-pr.py doc-checkout --fix-branch in place on feature/#123" 0 "${rc}"
    [[ "$(printf '%s' "${out}" | field in_place)" == true \
        && "$(printf '%s' "${out}" | field branch)" == 'feature/#123' ]] \
        || { note "FAIL: gh-pr.py doc-checkout --fix-branch on feature/#123: '${out}'"; fail=1; }
    cmp -s "${DOCS}/pr-hash.md" "${DOCS}/pr-here.orig" || {
        note "FAIL: gh-pr.py doc-checkout --fix-branch on feature/#123 wrote" \
            "$(cat "${DOCS}/pr-hash.md")"
        fail=1
    }
    git checkout -q "${CUR}" && git branch -q -D 'feature/#123' \
        || { note "FAIL: git checkout ${CUR} after the feature/#123 case"; fail=1; }
else
    note "FAIL: git checkout -b for the feature/#123 case"; fail=1
fi

PR_SRC="${SANDBOX}/pr-src"
git worktree add -q -b pr-src "${PR_SRC}" >/dev/null 2>&1 \
    && mkdir -p "${PR_SRC}/sub" && echo src > "${PR_SRC}/sub/src.txt" \
    && echo agent > "${PR_SRC}/sub/CLAUDE.md" \
    && git -C "${PR_SRC}" add -- sub 2>/dev/null \
    && git -C "${PR_SRC}" update-index --add --cacheinfo \
        "120000,$(printf src.txt | git -C "${PR_SRC}" hash-object -w --stdin),sub/link" \
    && git -C "${PR_SRC}" update-index --add --cacheinfo \
        "120000,$(printf CLAUDE.md | git -C "${PR_SRC}" hash-object -w --stdin),sub/AGENTS.md" \
    && git -C "${PR_SRC}" -c user.email=test@test -c user.name=test -c commit.gpgsign=false \
        commit -qm pr \
    && git worktree remove --force -- "${PR_SRC}" \
    || { note "FAIL: gh-pr.py doc-checkout repository setup"; fail=1; }
drop_worktree() { # <path>: removes a worktree a failed case left behind
    [[ -d "$1" ]] || return 0
    python3 "${GHPR}" remove "$1" >/dev/null 2>&1 \
        || { git worktree remove --force -- "$1" >/dev/null 2>&1; rmdir -- "${1%/*}" 2>/dev/null; }
}
kept_link() { # <doc> <worktree> <change>: gh-pr.py remove keeps the worktree, naming sub/link
    local out rc=0 want
    want="$(shlex_join git worktree remove --force -- "$2") in $(shlex_join "${MAIN}")"
    out="$(python3 "${GHPR}" remove "$2" 2>&1)" || rc=$?
    [[ "${rc}" -eq 1 && -d "$2" && "${out}" == *"symbolic links 'sub/link', which"* \
        && "${out}" == *"do not run git in it"* && "${out}" == *"${want}"* ]] && return
    note "FAIL: gh-pr.py remove did not keep the worktree of $1 with sub/link $3: '${out}'"
    fail=1
    drop_worktree "$2"
    return 1
}
# check_worktree <doc> <path-prefix> <pr_worktree> <trust> <agent file kept>
check_worktree() {
    local out wt err="${SANDBOX}/doc-checkout.err"
    out="$(doc_checkout "${DOCS}/$1" 2>"${err}")" \
        || { note "FAIL: gh-pr.py doc-checkout $1: $(cat "${err}")"; fail=1; return; }
    wt="$(printf '%s' "${out}" | field worktree_path)"
    [[ "${wt}" == "${MAIN}/.claude/worktrees/$2"* \
        && "$(printf '%s' "${out}" | field main_root)" == "${MAIN}" \
        && "$(printf '%s' "${out}" | field in_place)" == false \
        && "$(printf '%s' "${out}" | field pr_worktree)" == "$3" \
        && "$(printf '%s' "${out}" | field trust)" == "$4" \
        && "$(printf '%s' "${out}" | field branch)" == pr-src ]] \
        || { note "FAIL: gh-pr.py doc-checkout $1 printed '${out}'"; fail=1
            drop_worktree "${wt}"; return; }
    [[ "$(git -C "${wt}" branch --show-current)" == pr-src && -f "${wt}/sub/src.txt" ]] \
        || { note "FAIL: gh-pr.py doc-checkout $1 did not check out pr-src"; fail=1; }
    if [[ "$5" == yes ]]; then
        [[ -f "${wt}/sub/CLAUDE.md" ]] \
            || { note "FAIL: gh-pr.py doc-checkout $1 left out sub/CLAUDE.md"; fail=1; }
    else
        [[ ! -e "${wt}/sub/CLAUDE.md" ]] \
            || { note "FAIL: gh-pr.py doc-checkout $1 kept sub/CLAUDE.md"; fail=1; }
    fi
    if [[ "$3" == true ]]; then
        [[ -z "$(git -C "${wt}" -c core.symlinks=true status --porcelain)" \
            && "$(git -C "${wt}" ls-files -v -- sub/link)" == S* ]] \
            || { note "FAIL: gh-pr.py doc-checkout $1 left sub/link a type change"; fail=1; }
        git -C "${wt}" -c core.symlinks=true add -- . >/dev/null 2>&1 \
            && git -C "${wt}" diff --cached --quiet \
            || { note "FAIL: git add in the worktree of $1 staged sub/link"; fail=1; }
        printf other > "${wt}/sub/link"
        kept_link "$1" "${wt}" changed || return
        rm "${wt}/sub/link"
        kept_link "$1" "${wt}" deleted || return
        printf src.txt > "${wt}/sub/link"
    else
        [[ -z "$(git -C "${wt}" status --porcelain)" ]] \
            || { note "FAIL: gh-pr.py doc-checkout $1 left the worktree dirty"; fail=1; }
    fi
    : > "${wt}/uncommitted.txt"
    rc=0; out="$(python3 "${GHPR}" remove "${wt}" 2>&1)" || rc=$?
    if [[ "${rc}" -eq 1 && -f "${wt}/uncommitted.txt" ]]; then
        if [[ "$3" == true ]]; then
            [[ "${out}" == *"do not run git in it"* \
                && "${out}" == *"$(shlex_join git worktree remove --force -- "${wt}")"* ]]
        else
            [[ "${out}" != *"do not run git in it"* ]]
        fi || { note "FAIL: gh-pr.py remove the dirty worktree of $1 printed '${out}'"; fail=1; }
        rm "${wt}/uncommitted.txt"
        rc=0; python3 "${GHPR}" remove "${wt}" >/dev/null 2>&1 || rc=$?
        check "gh-pr.py remove the worktree of $1" 0 "${rc}"
        [[ "${rc}" -eq 0 ]] || drop_worktree "${wt}"
    else
        note "FAIL: gh-pr.py remove did not keep the dirty worktree of $1 (rc=${rc})"; fail=1
        drop_worktree "${wt}"
    fi
}
write_doc branch.md "- **Branch:** pr-src" "- **Trust:** off"
check_worktree branch.md creview-branch- false off yes
# git refuses to remove a worktree whose git directory has a modules directory.
out="$(doc_checkout "${DOCS}/branch.md" 2>&1)"; rc=$?
wt=""
[[ "${rc}" -ne 0 ]] || wt="$(printf '%s' "${out}" | field worktree_path)"
if [[ -d "${wt}" ]] && modules="$(git -C "${wt}" rev-parse --absolute-git-dir)/modules" \
    && mkdir "${modules}"; then
    out="$(python3 "${GHPR}" remove "${wt}" 2>&1)"; rc=$?
    check "gh-pr.py remove a worktree with initialized submodules" 1 "${rc}"
    [[ -d "${wt}" && "${out}" == *"$(shlex_join git worktree remove --force -- "${wt}")"* ]] || {
        note "FAIL: gh-pr.py remove a worktree with initialized submodules printed '${out}'"
        fail=1
    }
    rmdir "${modules}"
    rc=0; python3 "${GHPR}" remove "${wt}" >/dev/null 2>&1 || rc=$?
    check "gh-pr.py remove a worktree whose submodules are gone" 0 "${rc}"
else
    note "FAIL: gh-pr.py doc-checkout branch.md for the submodule case: '${out}'"; fail=1
fi
drop_worktree "${wt}"
HOOKS="${SANDBOX}/failing-hooks"
mkdir -p "${HOOKS}" && printf '#!/bin/sh\nexit 1\n' > "${HOOKS}/post-checkout" \
    && chmod +x "${HOOKS}/post-checkout" && git config core.hooksPath "${HOOKS}" \
    || { note "FAIL: failing post-checkout hook setup"; fail=1; }
out="$(doc_checkout "${DOCS}/branch.md" 2>&1)"; rc=$?
git config --unset core.hooksPath
check "gh-pr.py doc-checkout branch.md with a failing post-checkout hook" 1 "${rc}"
[[ "$(git worktree list --porcelain)" != *creview-branch-* && ! -e "${MAIN}/.claude/worktrees" ]] \
    || { note "FAIL: gh-pr.py doc-checkout kept the worktree of a failed hook: '${out}'"; fail=1
        git worktree list --porcelain \
            | sed -n 's/^worktree \(.*\/creview-branch-[^/]*\)$/\1/p' \
            | while IFS= read -r p; do drop_worktree "${p}"; done; }
if [[ "$(GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=t.k GIT_CONFIG_VALUE_0=v \
    git config --get t.k 2>/dev/null)" == v ]]; then
    write_doc pr-branch.md "${PR_LINE}" "- **Branch:** pr-src"
    check_worktree pr-branch.md creview-pr-3- true off no
    write_doc pr-branch-off.md "${PR_LINE}" "- **Branch:** pr-src" "- **Trust:** off"
    check_worktree pr-branch-off.md creview-pr-3- true off no
    write_doc pr-branch-on.md "${PR_LINE}" "- **Branch:** pr-src" "- **Trust:** on"
    check_worktree pr-branch-on.md creview-pr-3- true on yes
else
    note "SKIP: gh-pr.py doc-checkout PR worktree cases (git does not apply GIT_CONFIG_COUNT)"
fi
git show-ref --verify --quiet refs/heads/pr-src \
    || { note "FAIL: gh-pr.py remove dropped the branch pr-src"; fail=1; }
git worktree add -q "${PR_SRC}" pr-src >/dev/null 2>&1 \
    || { note "FAIL: git worktree add for the busy-branch case"; fail=1; }
for name in branch.md pr-branch-on.md; do
    [[ -e "${DOCS}/${name}" ]] || continue
    out="$(doc_checkout "${DOCS}/${name}" 2>&1)"; rc=$?
    check "gh-pr.py doc-checkout ${name} on a branch checked out elsewhere" 1 "${rc}"
    [[ "${out}" == *"pr-src is checked out in the worktree"*"session started at"* ]] \
        || { note "FAIL: gh-pr.py doc-checkout ${name} on a busy branch printed '${out}'"; fail=1; }
done
out="$( (cd "${PR_SRC}" && doc_checkout "${DOCS}/pr-here.orig") 2>/dev/null)"; rc=$?
check "gh-pr.py doc-checkout on a child of the PR head" 0 "${rc}"
[[ "$(printf '%s' "${out}" | field in_place)" == true \
    && "$(printf '%s' "${out}" | field branch)" == pr-src \
    && "$(printf '%s' "${out}" | field worktree_path)" == null ]] \
    || { note "FAIL: gh-pr.py doc-checkout on a child of the PR head printed '${out}'"; fail=1; }
git worktree remove -- "${PR_SRC}" >/dev/null 2>&1
# A gh shim stands in for gh: PR #3 is open at GH_HEAD, which pr checkout checks out.
GHSHIM="${SANDBOX}/ghshim"
mkdir -p "${GHSHIM}"
cat > "${GHSHIM}/gh" <<'SH'
#!/bin/sh
case "$1 $2" in
    "pr view") printf '{"number":3,"state":"OPEN","headRefOid":"%s"}\n' "${GH_HEAD}" ;;
    "pr checkout") exec git checkout --quiet --detach "${GH_HEAD}" ;;
    *) exit 1 ;;
esac
SH
chmod +x "${GHSHIM}/gh" || { note "FAIL: gh-pr.py doc-checkout gh shim setup"; fail=1; }
shim_checkout() { # <doc> [option]: doc-checkout with the gh shim first on the PATH
    PATH="${GHSHIM}:${PATH}" GH_HEAD="${PR_HEAD}" python3 "${GHPR}" doc-checkout \
        "${DOCS}/$1" "${@:2}"
}
# pr_only_case <doc> <branch, empty for none> [option]: doc-checkout adds a PR worktree at
# PR_HEAD on that branch; its path is left in wt.
pr_only_case() {
    local out err="${SANDBOX}/doc-checkout.err"
    wt=""
    out="$(shim_checkout "$1" "${@:3}" 2>"${err}")" \
        || { note "FAIL: gh-pr.py doc-checkout $1${3:+ $3}: $(cat "${err}")"; fail=1; return; }
    wt="$(printf '%s' "${out}" | field worktree_path)"
    [[ "${wt}" == "${MAIN}/.claude/worktrees/creview-pr-3-"* \
        && "$(printf '%s' "${out}" | field in_place)" == false \
        && "$(printf '%s' "${out}" | field pr_worktree)" == true \
        && "$(printf '%s' "${out}" | field branch)" == "${2:-null}" \
        && "$(git -C "${wt}" rev-parse HEAD)" == "${PR_HEAD}" \
        && "$(git -C "${wt}" branch --show-current)" == "$2" \
        && -f "${wt}/sub/src.txt" && ! -e "${wt}/sub/CLAUDE.md" ]] \
        || { note "FAIL: gh-pr.py doc-checkout $1${3:+ $3} printed '${out}'"; fail=1; }
}
if [[ "$(python3 -c 'import os; print(os.name)')" == nt ]]; then
    note "SKIP: gh-pr.py doc-checkout PR-bullet-only cases (gh-pr.py runs gh.exe, not the shim)"
elif [[ "$(GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=t.k GIT_CONFIG_VALUE_0=v \
    git config --get t.k 2>/dev/null)" != v ]]; then
    note "SKIP: gh-pr.py doc-checkout PR-bullet-only cases (git does not apply GIT_CONFIG_COUNT)"
else
    PR_HEAD="$(git rev-parse pr-src)"
    git remote add origin https://github.com/o/r \
        || { note "FAIL: git remote add for the PR-bullet-only cases"; fail=1; }
    out="$(shim_checkout moved.md 2>&1)"; rc=$?
    check "gh-pr.py doc-checkout moved.md after the PR head moved" 1 "${rc}"
    [[ "${out}" == *"changed after the review"* ]] \
        || { note "FAIL: gh-pr.py doc-checkout moved.md via the gh shim printed '${out}'"; fail=1; }
    [[ "${rc}" -ne 0 ]] || drop_worktree "$(printf '%s' "${out}" | field worktree_path)"
    write_doc pr-only.md \
        "- **PR:** https://github.com/o/r/pull/3 (head ${PR_HEAD}, base ${HEAD_SHA})" \
        "- **Trust:** off"
    cp "${DOCS}/pr-only.md" "${DOCS}/pr-only.orig"
    cp "${DOCS}/pr-only.md" "${DOCS}/pr-only-fix.md"
    pr_only_case pr-only.md ""
    cmp -s "${DOCS}/pr-only.md" "${DOCS}/pr-only.orig" \
        || { note "FAIL: gh-pr.py doc-checkout pr-only.md changed the document"; fail=1; }
    drop_worktree "${wt}"
    pr_only_case pr-only-fix.md creview-pr-3 --fix-branch
    [[ "$(sed -n 4p "${DOCS}/pr-only-fix.md")" == "- **Branch:** creview-pr-3" ]] || {
        note "FAIL: gh-pr.py doc-checkout --fix-branch wrote $(cat "${DOCS}/pr-only-fix.md")"
        fail=1
    }
    out="$(shim_checkout pr-only.md --fix-branch 2>&1)"; rc=$?
    check "gh-pr.py doc-checkout --fix-branch with creview-pr-3 checked out" 1 "${rc}"
    [[ "${out}" == *"creview-pr-3 is checked out in the worktree"* ]] \
        || { note "FAIL: gh-pr.py doc-checkout on a busy creview-pr-3 printed '${out}'"; fail=1; }
    [[ "${rc}" -ne 0 ]] || drop_worktree "$(printf '%s' "${out}" | field worktree_path)"
    drop_worktree "${wt}"
    pr_only_case pr-only-fix.md creview-pr-3 --fix-branch
    [[ "$(grep -c '^- \*\*Branch:\*\*' "${DOCS}/pr-only-fix.md")" == 1 ]] || {
        note "FAIL: gh-pr.py doc-checkout --fix-branch rerun wrote $(cat "${DOCS}/pr-only-fix.md")"
        fail=1
    }
    drop_worktree "${wt}"
    git branch -D creview-pr-3 >/dev/null 2>&1
    git remote remove origin >/dev/null 2>&1
fi
[[ ! -e "${MAIN}/.claude/worktrees" ]] \
    || { note "FAIL: gh-pr.py doc-checkout left $(ls "${MAIN}/.claude/worktrees")"; fail=1; }
KEPT="${MAIN}/.claude/worktrees/creview-pr-3-20260101-000000"
if git worktree add -q "${KEPT}" pr-src >/dev/null 2>&1; then
    out="$(doc_checkout "${DOCS}/branch.md" 2>&1)"; rc=$?
    check "gh-pr.py doc-checkout branch.md on a branch a kept PR worktree holds" 1 "${rc}"
    want="$(shlex_join remove "${KEPT}") in $(shlex_join "${MAIN}") "
    [[ "${out}" == *"which a creview skill kept"*"/gh-pr.py"*" ${want}"* \
        && "${out}" == *"do not run git in it"* && "${out}" != *"commit or discard"* \
        && "${out}" != *\\* ]] \
        || { note "FAIL: gh-pr.py doc-checkout on a kept PR worktree's branch printed '${out}'"
             fail=1; }
    out="$( (cd "${KEPT}" && doc_checkout "${DOCS}/none.md") 2>&1)"; rc=$?
    check "gh-pr.py doc-checkout in a PR worktree" 1 "${rc}"
    [[ "${out}" == *"session started at the main working tree"* ]] \
        || { note "FAIL: gh-pr.py doc-checkout in a PR worktree printed '${out}'"; fail=1; }
    if [[ "$(GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=t.k GIT_CONFIG_VALUE_0=v \
        git config --get t.k 2>/dev/null)" == v ]]; then
        python3 -I -B - "${GHPR}" "${KEPT}" "${MAIN}" <<'PY' || fail=1
import contextlib
import importlib.util
import io
import os
import shlex
import sys

spec = importlib.util.spec_from_file_location("gh_pr", sys.argv[1])
g = importlib.util.module_from_spec(spec)
spec.loader.exec_module(g)
kept, main_root = sys.argv[2], sys.argv[3]
recovery = (f"{shlex.join(['git', 'worktree', 'remove', '--force', '--', kept])} in "
            f"{shlex.quote(main_root)}")
failed = False
for links, reason in (
        (([], ["x"]), "is kept: its symbolic links 'x', which it holds as plain files, could not "
                      "be examined"),
        ((["a"], [b"l\xe9"]), "is kept: it changes the symbolic links 'a', which it holds as "
                               "plain files that git status does not show, and its symbolic "
                               "links b'l\\xe9', which")):
    g.changed_links = lambda path, env, links=links: links
    err = io.StringIO()
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(err):
        rc = g.main(["remove", kept])
    out = err.getvalue()
    if rc != 1 or not os.path.isdir(kept) or not all(
            p in out for p in (reason, "do not run git in it", recovery)):
        print(f"FAIL: gh-pr.py remove a PR worktree whose links are {links} "
              f"(rc={rc}, printed {out!r:.600})")
        failed = True
sys.exit(1 if failed else 0)
PY
    else
        note "SKIP: gh-pr.py remove kept PR worktree cases (git does not apply GIT_CONFIG_COUNT)"
    fi
    git worktree remove --force -- "${KEPT}" >/dev/null 2>&1
    rmdir "${MAIN}/.claude/worktrees" 2>/dev/null
else
    note "FAIL: git worktree add for the kept PR worktree case"; fail=1
fi
KEPT_BRANCH="${MAIN}/.claude/worktrees/creview-branch-20260101-000000"
if git worktree add -q "${KEPT_BRANCH}" pr-src >/dev/null 2>&1; then
    out="$(doc_checkout "${DOCS}/branch.md" 2>&1)"; rc=$?
    check "gh-pr.py doc-checkout branch.md on a branch a kept branch worktree holds" 1 "${rc}"
    want="$(shlex_join remove "${KEPT_BRANCH}") in $(shlex_join "${MAIN}") "
    [[ "${out}" == *"which a creview skill kept"*"/gh-pr.py"*" ${want}"* \
        && "${out}" == *"review its changes, commit or discard them, and remove it by running"* \
        && "${out}" != *"do not run git in it"* && "${out}" != *\\* ]] \
        || { note "FAIL: gh-pr.py doc-checkout on a kept branch worktree's branch printed '${out}'"
             fail=1; }
    git worktree remove --force -- "${KEPT_BRANCH}" >/dev/null 2>&1
    rmdir "${MAIN}/.claude/worktrees" 2>/dev/null
else
    note "FAIL: git worktree add for the kept branch worktree case"; fail=1
fi

# --- render-review.py keeps each metadata value on one line -----------------------
RD="${SANDBOX}/render"
mkdir -p "${RD}"
printf '# Report\n\n<!-- /METADATA(mi-1) -->\n\n## Minor\n' > "${RD}/doc.md"
printf '%s\n' '{"id":"mi-1","field":"triage","value":"Will Fix\n- **Branch:** main"}' \
    '{"id":"mi-1","field":"estimate","value":"Maintain\r- **Branch:** main"}' \
    '{"id":"mi-9","field":"status","value":"Fixed\r\n- **Branch:** main"}' > "${RD}/events.jsonl"
printf '# Report\n\n%s\n%s\n<!-- /METADATA(mi-1) -->\n\n## Minor\n\n## Orphan Metadata\n\n%s\n' \
    '- **Triage:** Will Fix - **Branch:** main' '- **Estimate:** Maintain - **Branch:** main' \
    $'### mi-9\n\n- **Status:** Fixed - **Branch:** main' > "${RD}/want.md"
rc=0; python3 "${RR}" "${RD}/doc.md" "${RD}/events.jsonl" "${RD}/out.md" >/dev/null 2>&1 || rc=$?
check "render-review.py with line breaks in values" 0 "${rc}"
cmp -s "${RD}/out.md" "${RD}/want.md" \
    || { note "FAIL: render-review.py wrote '$(cat -v "${RD}/out.md")'"; fail=1; }

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
