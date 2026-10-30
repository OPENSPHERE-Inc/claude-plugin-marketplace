#!/usr/bin/env python3
"""gh-pr.py — resolve a GitHub pull request for a creview PR review and check it out,
and check out the code a creview review document names.

Usage:
    python3 gh-pr.py fetch <pr_url> <out_dir>
    python3 gh-pr.py checkout <pr_json> [--trust]
    python3 gh-pr.py doc-checkout <document> [--fix-branch]
    python3 gh-pr.py remove <worktree_path> [--discard]

fetch: resolves <pr_url> (https://<host>/<owner>/<repo>/pull/<number>) with gh,
requires <owner>/<repo> on <host> to be a remote of the current repository and
the PR to be open, and writes two files to <out_dir>:
  pr.json          url, head and base commits, merge base
  pr-context.json  title and body, CI check results (the latest attempt of each
                   check in each workflow run; the first MAX_JOB_LOGS failed
                   GitHub Actions jobs carry a log excerpt, or log_error when
                   it could not be fetched), and the conversation: issue
                   comments, submitted review bodies, and review comments, at
                   most MAX_COMMENTS of each kind, with omitted set when any
                   were left out; a review comment says whether its line is
                   outdated and, when known, whether its thread is resolved
It prints a JSON object whose in_place is true when HEAD of the current working
tree is the PR head.
An in-place working tree with uncommitted changes to tracked files (outside
.claude/tmp and .claude/worktrees) is an error.

checkout: adds a detached worktree under .claude/worktrees/ of the current
working tree, checks the PR head out in it with git hooks and the configured
filter drivers disabled, Git LFS smudging skipped, and symbolic links checked
out as plain files marked skip-worktree (so that git under core.symlinks=true
sees no type change in them), confirms its HEAD is the head fetch recorded, and
prints a JSON object with main_root and worktree_path. Without --trust, the
checkout leaves out every file and directory named like one of AGENT_FILES, in
any letter case and at any depth, and fails when the file system still resolves
one of those names in a directory of the worktree.
A failed checkout removes the worktree it added.

doc-checkout: reads the header bullets of a review document (the lines before
its first "## " heading): "- **PR:** <url> (head <sha>, base <sha>)",
"- **Branch:** <branch>", and "- **Trust:** on|off" (off when absent). A
malformed value is an error. It decides where the document's code is:
  Branch bullet  in place when <branch> is checked out here, otherwise a
                 worktree on that local branch: with a PR bullet, a PR worktree
                 checked out like checkout, with the agent files only when Trust
                 is on; without one, a plain worktree (creview-branch-<timestamp>)
  PR bullet only in place when HEAD contains the head commit, otherwise a PR
                 worktree at the head commit, which the open PR must still have;
                 with --fix-branch, on local branch creview-pr-<number> (created
                 there, or used when it points there)
  neither        in place
A branch checked out in another worktree is an error naming that worktree,
which for a worktree checkout or doc-checkout added says to remove it first.
doc-checkout fails when the current working tree is a PR worktree that checkout
or doc-checkout added.
With --fix-branch, a document with a PR bullet and no Branch bullet gets
"- **Branch:** <branch>" after its PR bullet when the work is on a branch whose
name a Branch bullet can hold (letters, digits, and _ . / + @ -).
It prints a JSON object: in_place, pr_worktree, trust, main_root and
worktree_path (null in place), branch (the branch worked on, null on a detached
HEAD), and merge_base (the PR bullet's, or null).

remove: removes a worktree that checkout or doc-checkout added
(<main_root>/.claude/worktrees/creview-pr-<number>-<timestamp> or
creview-branch-<timestamp>; any other path is an error), a PR worktree with git
hooks and the configured filter drivers disabled, and its parent directory when
left empty. With --discard, a PR worktree is removed with --force, keeping
nothing in it and examining neither its changes nor its symbolic links; when
that fails, the error says not to run git in it and to remove it with git
worktree remove --force. --discard does nothing to a creview-branch worktree.
Otherwise a worktree with uncommitted changes, including changes to the
symbolic links a PR worktree holds as plain files, is kept, and the exit status
is 1. So is a PR worktree with such a link it cannot examine (on Windows, a path
that is not UTF-8 or is past MAX_PATH), and so is a worktree with initialized
submodules, which git refuses to remove; its error then says to check the
worktree and remove it with git worktree remove --force. A kept PR worktree's
error says instead not to run git in it, to copy out what to keep, and to
remove it with git worktree remove --force.

Exits 1 with an error message on stderr on any failure.
"""

import hashlib
import json
import os
import re
import shlex
import stat
import subprocess
import sys
import tempfile
import time

PR_URL_RE = re.compile(
    r"https://([A-Za-z0-9.-]+(?::[0-9]+)?)/([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+)"
    r"/pull/([0-9]+)(?:[/?#].*)?"
)
# A remote URL names its host and ends with the owner and repository, in URL form
# (https://host/o/r.git, ssh://git@host:22/o/r) or scp form (git@host:o/r.git).
# A local path has no host, and a file:// URL is left out by its scheme.
REMOTE_URL_RE = re.compile(
    r"(?:(?P<scheme>[A-Za-z][A-Za-z0-9+.-]*)://(?:[^@/]*@)?(?P<host>[^/@:]+)(?::[0-9]*)?/"
    r"|(?:[^@/:]+@)?(?P<scp_host>[^/@:]{2,}):(?!//))"
    r"(?:.*/)?(?P<owner>[^/]+)/(?P<repo>[^/]+?)(?:\.git)?/*"
)
SSH_SCHEMES = {"ssh", "git+ssh", "ssh+git"}
SHA_RE = re.compile(r"[0-9a-f]{40}(?:[0-9a-f]{24})?")
# Scratch and worktree directories of the creview skills, not part of the review.
SCRATCH_EXCLUDES = [":(top,exclude).claude/tmp", ":(top,exclude).claude/worktrees"]
# The names of the worktrees add_checkout and branch_worktree add under .claude/worktrees.
PR_WORKTREE_RE = re.compile(r"creview-pr-[0-9]+-[0-9]{8}-[0-9]{6}")
BRANCH_WORKTREE_RE = re.compile(r"creview-branch-[0-9]{8}-[0-9]{6}")
HEADER_BULLET_RE = re.compile(r"- \*\*(PR|Branch|Trust):\*\* (.*)")
PR_BULLET_RE = re.compile(r"(\S+) \(head (\S+), base (\S+)\)")
# Characters a branch name in a review document header may hold, none special to a shell.
BRANCH_NAME_RE = re.compile(r"[\w./+@-]+")
# Names of the files and directories Claude Code, or another agent for AGENTS.md, loads
# from a project on its own.
AGENT_FILES = ("CLAUDE.md", "CLAUDE.local.md", "AGENTS.md", ".mcp.json", ".claude")
ACTIONS_JOB_RE = re.compile(
    r"https://([^/]+)/([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)/actions/runs/([0-9]+)/job/([0-9]+)"
    r"(?:[/?#].*)?"
)
FAILED_CONCLUSIONS = {"FAILURE", "TIMED_OUT", "CANCELLED", "ACTION_REQUIRED", "STARTUP_FAILURE"}
MAX_JOB_LOGS = 10
LOG_LINES = 150
LOG_LINE_CHARS = 500
BODY_CHARS = 20000
COMMENT_CHARS = 4000
PAGE_SIZE = 100
MAX_PAGES = 10
MAX_COMMENTS = 50
REVIEW_THREADS_QUERY = """
query($owner: String!, $name: String!, $number: Int!, $cursor: String) {
  repository(owner: $owner, name: $name) {
    pullRequest(number: $number) {
      reviewThreads(first: 100, after: $cursor) {
        nodes { isResolved comments(first: 1) { nodes { databaseId } } }
        pageInfo { hasNextPage endCursor }
      }
    }
  }
}
"""


class Error(Exception):
    pass


def executable(name):
    # Windows looks a bare program name up in the working directory before
    # PATH, and the working directory can hold untrusted checked-out files.
    if os.name == "nt" and not name.lower().endswith(".exe"):
        name += ".exe"
    for entry in os.environ.get("PATH", "").split(os.pathsep):
        entry = entry.strip('"')
        path = os.path.join(entry, name)
        if os.path.isabs(entry) and os.path.isfile(path) and os.access(path, os.X_OK):
            return path
    return None


def run(cmd, cwd=None, env=None, ok=(0,), input=None, text=True):
    program = executable(cmd[0])
    if program is None:
        raise Error(f"{cmd[0]} not found on PATH")
    decoding = {"text": True, "encoding": "utf-8", "errors": "replace"} if text else {}
    proc = subprocess.run(
        [program, *cmd[1:]], cwd=cwd, env=env, input=input, capture_output=True, **decoding,
    )
    if proc.returncode not in ok:
        stderr = proc.stderr if text else proc.stderr.decode("utf-8", "replace")
        raise Error(stderr.strip() or f"{' '.join(cmd[:2])} exited with {proc.returncode}")
    return proc.stdout


def sha(value, what):
    if not isinstance(value, str) or not SHA_RE.fullmatch(value):
        raise Error(f"unexpected {what}: {value!r}")
    return value


def clip(text, limit):
    text = text or ""
    return text if len(text) <= limit else text[:limit] + "\n[truncated]"


def login(user):
    return (user or {}).get("login") or "ghost"


def write_json(path, data):
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")


def api_pages(endpoint, host, max_pages=MAX_PAGES):
    items = []
    for page in range(1, max_pages + 1):
        batch = json.loads(run([
            "gh", "api", "--hostname", host, f"{endpoint}?per_page={PAGE_SIZE}&page={page}",
        ]))
        items.extend(batch)
        if len(batch) < PAGE_SIZE:
            return items, True
    return items, False


def job_log_excerpt(host, repo, job_id):
    # A failing step reports itself with an ##[error] line; the cause precedes it,
    # and the job's cleanup steps follow it.
    lines = run(["gh", "api", "--hostname", host, f"repos/{repo}/actions/jobs/{job_id}/logs"])
    lines = lines.splitlines()
    errors = [i for i, line in enumerate(lines) if "##[error]" in line]
    end = errors[-1] + 1 if errors else len(lines)
    return "\n".join(line[:LOG_LINE_CHARS] for line in lines[max(0, end - LOG_LINES):end])


def started_at(check):
    return check.get("startedAt") or ""


def check_key(check):
    # A rerun keeps its workflow run's ID; a run for another event on the same head has its own.
    job = ACTIONS_JOB_RE.fullmatch(check.get("detailsUrl") or "")
    return check.get("workflowName"), check.get("name"), job.group(3) if job else None


def ci_checks(rollup, host, repos):
    rollup = rollup or []
    # Reruns leave the earlier runs of a check in the rollup; a status context comes once.
    latest = {}
    for c in rollup:
        if c.get("__typename") != "StatusContext":
            key = check_key(c)
            if key not in latest or started_at(c) > started_at(latest[key]):
                latest[key] = c
    checks, logs = [], 0
    for c in rollup:
        if c.get("__typename") == "StatusContext":
            checks.append({
                "name": c.get("context"),
                "state": c.get("state"),
                "description": c.get("description"),
                "url": c.get("targetUrl"),
            })
            continue
        if latest[check_key(c)] is not c:
            continue
        check = {
            "name": c.get("name"),
            "workflow": c.get("workflowName"),
            "status": c.get("status"),
            "conclusion": c.get("conclusion"),
            "url": c.get("detailsUrl"),
        }
        job = ACTIONS_JOB_RE.fullmatch(check["url"] or "")
        if (check["conclusion"] in FAILED_CONCLUSIONS and job and job.group(1).lower() == host
                and job.group(2).lower() in repos and logs < MAX_JOB_LOGS):
            logs += 1
            try:
                check["log_excerpt"] = job_log_excerpt(host, job.group(2), job.group(4))
            except Error as e:
                check["log_error"] = str(e)
        checks.append(check)
    return checks


def resolved_threads(host, repo, number):
    # Only GraphQL reports a thread's state, keyed here by the ID of its first comment. A thread
    # this cannot read stays out of the result: its state is not known.
    owner, name = repo.split("/")
    states, cursor = {}, None
    for _ in range(MAX_PAGES):
        cmd = ["gh", "api", "graphql", "--hostname", host, "-f", f"query={REVIEW_THREADS_QUERY}",
               "-f", f"owner={owner}", "-f", f"name={name}", "-F", f"number={number}"]
        if cursor:
            cmd += ["-f", f"cursor={cursor}"]
        try:
            threads = json.loads(run(cmd))["data"]["repository"]["pullRequest"]["reviewThreads"]
            for thread in threads["nodes"]:
                states[thread["comments"]["nodes"][0]["databaseId"]] = thread["isResolved"]
            cursor = threads["pageInfo"]["endCursor"]
            if not threads["pageInfo"]["hasNextPage"]:
                break
        except (Error, ValueError, KeyError, IndexError, TypeError):
            break
    return states


def conversation(host, repo, number):
    states = resolved_threads(host, repo, number)
    reviews, complete = api_pages(f"repos/{repo}/pulls/{number}/reviews", host)
    pending = {r.get("id") for r in reviews if r.get("state") == "PENDING"}
    issue_comments, issue_complete = api_pages(f"repos/{repo}/issues/{number}/comments", host)
    review_comments, comments_complete = api_pages(f"repos/{repo}/pulls/{number}/comments", host)
    lists = {
        "issue_comments": [
            {"author": login(c.get("user")), "created_at": c.get("created_at"),
             "body": clip(c.get("body"), COMMENT_CHARS)}
            for c in issue_comments
        ],
        "reviews": [
            {"author": login(r.get("user")), "state": r.get("state"),
             "submitted_at": r.get("submitted_at"), "body": clip(r.get("body"), COMMENT_CHARS)}
            for r in reviews if r.get("body") and r.get("state") != "PENDING"
        ],
        "review_comments": [
            {"id": c.get("id"), "in_reply_to": c.get("in_reply_to_id"),
             "author": login(c.get("user")), "created_at": c.get("created_at"),
             "path": c.get("path"), "line": c.get("line") or c.get("original_line"),
             "outdated": c.get("line") is None and c.get("original_line") is not None,
             "thread_resolved": states.get(c.get("in_reply_to_id") or c.get("id")),
             "body": clip(c.get("body"), COMMENT_CHARS)}
            for c in review_comments
            if c.get("pull_request_review_id") not in pending
        ],
    }
    omitted = not (complete and issue_complete and comments_complete) or any(
        len(entries) > MAX_COMMENTS for entries in lists.values()
    )
    result = {kind: entries[-MAX_COMMENTS:] for kind, entries in lists.items()}
    result["omitted"] = omitted
    return result


def normalize_host(host):
    # gh treats every *.github.com host, such as ssh.github.com, as github.com.
    host = host.lower()
    return "github.com" if host.endswith(".github.com") else host


def remote_repos():
    try:
        names = run(["git", "remote"]).splitlines()
    except Error:
        return set()
    repos = set()
    for name in names:
        try:
            url = run(["git", "remote", "get-url", "--", name]).strip()
        except Error:
            continue
        m = REMOTE_URL_RE.fullmatch(url)
        scheme = (m.group("scheme") or "").lower() if m else ""
        if not m or scheme == "file":
            continue
        ssh = scheme in SSH_SCHEMES or m.group("scp_host") is not None
        host = (m.group("host") or m.group("scp_host")).lower()
        repos.add((host, m.group("owner").lower(), m.group("repo").lower(), ssh))
    return repos


def ssh_hostname(alias):
    if alias.startswith("-"):
        return alias
    try:
        config = run(["ssh", "-G", alias])
    except Error:
        return alias
    for line in config.splitlines():
        key, _, value = line.partition(" ")
        if key == "hostname" and value.strip():
            return value.strip()
    return alias


def is_remote(host, owner, name):
    want = normalize_host(host.partition(":")[0])
    for r_host, r_owner, r_name, ssh in remote_repos():
        if (r_owner, r_name) != (owner.lower(), name.lower()):
            continue
        if normalize_host(r_host) == want:
            return True
        if ssh and normalize_host(ssh_hostname(r_host)) == want:
            return True
    return False


def view_pr(pr_url, fields=""):
    m = PR_URL_RE.fullmatch(pr_url)
    if not m:
        raise Error(f"not a pull request URL: {pr_url}")
    host, owner, name, number = m.group(1).lower(), m.group(2), m.group(3), int(m.group(4))
    repo = f"{owner}/{name}"
    if not is_remote(host, owner, name):
        raise Error(f"{repo} on {host} is not a remote of this repository")
    url = f"https://{host}/{repo}/pull/{number}"

    pr = json.loads(run(["gh", "pr", "view", url, "--json", "number,state,headRefOid" + fields]))
    got = pr.get("number")
    if not isinstance(got, int) or isinstance(got, bool) or got != number:
        raise Error(f"gh did not return PR #{number}")
    if pr.get("state") != "OPEN":
        raise Error(f"PR #{number} is not open")
    return host, repo, number, url, pr


def cmd_fetch(pr_url, out_dir):
    host, repo, number, url, pr = view_pr(
        pr_url, ",baseRefOid,headRepository,headRepositoryOwner,title,body,statusCheckRollup")
    head_sha = sha(pr["headRefOid"], "head commit")
    base_sha = sha(pr["baseRefOid"], "base commit")
    # A check's detailsUrl can name any repository; job logs are read only from the PR's own.
    job_repos = {repo.lower()}
    head_owner = (pr.get("headRepositoryOwner") or {}).get("login")
    head_name = (pr.get("headRepository") or {}).get("name")
    if isinstance(head_owner, str) and isinstance(head_name, str):
        job_repos.add(f"{head_owner}/{head_name}".lower())
    compare = json.loads(run([
        "gh", "api", "--hostname", host, f"repos/{repo}/compare/{base_sha}...{head_sha}",
    ]))
    merge_base = sha((compare.get("merge_base_commit") or {}).get("sha"), "merge base")

    in_place = run(["git", "rev-parse", "HEAD"]).strip() == head_sha
    if in_place and run([
        "git", "status", "--porcelain", "--untracked-files=no", "--", *SCRATCH_EXCLUDES,
    ]).strip():
        raise Error(
            "the working tree is at the PR head but has uncommitted changes; "
            "commit or stash them first"
        )

    write_json(os.path.join(out_dir, "pr.json"), {
        "url": url,
        "repo": repo,
        "number": number,
        "head_sha": head_sha,
        "base_sha": base_sha,
        "merge_base": merge_base,
    })
    write_json(os.path.join(out_dir, "pr-context.json"), {
        "title": pr["title"],
        "body": clip(pr["body"], BODY_CHARS),
        "checks": ci_checks(pr["statusCheckRollup"], host, job_repos),
        "conversation": conversation(host, repo, number),
    })
    return {
        "url": url,
        "number": number,
        "head_sha": head_sha,
        "merge_base": merge_base,
        "in_place": in_place,
    }


def filter_overrides():
    # git skips a filter whose command is empty; required=false keeps that from failing.
    keys = run([
        "git", "config", "--name-only", "--get-regexp", r"^filter\..+\.(clean|smudge|process)$",
    ], ok=(0, 1))
    overrides = []
    for name in dict.fromkeys(k[len("filter."):k.rindex(".")] for k in keys.splitlines() if k):
        overrides += [(f"filter.{name}.{cmd}", "") for cmd in ("clean", "smudge", "process")]
        overrides.append((f"filter.{name}.required", "false"))
    return overrides


def checkout_env(overrides, base=None):
    # A PR can add or change the hooks a relative core.hooksPath or core.fsmonitor points
    # at, its .gitattributes picks which of the user's filter drivers run on its files, and
    # its symbolic links can point outside the worktree; gh runs git itself, so the
    # overrides travel in the environment.
    env = dict(os.environ if base is None else base)
    try:
        n = int(env.get("GIT_CONFIG_COUNT") or 0)
    except ValueError:
        raise Error("GIT_CONFIG_COUNT is not a number") from None
    for i, (key, value) in enumerate(overrides, n):
        env[f"GIT_CONFIG_KEY_{i}"] = key
        env[f"GIT_CONFIG_VALUE_{i}"] = value
    env.update({
        "GIT_CONFIG_COUNT": str(n + len(overrides)),
        "GIT_LFS_SKIP_SMUDGE": "1",
        "GH_PROMPT_DISABLED": "1",
    })
    return env


def hook_free_env(no_hooks):
    # Git before 2.36 takes core.fsmonitor=false as a hook command; an empty value disables it.
    env = checkout_env([
        ("core.hooksPath", no_hooks), ("core.fsmonitor", ""), ("core.symlinks", "false"),
        *filter_overrides(),
    ])
    # Git before 2.31 ignores GIT_CONFIG_COUNT; refuse rather than run hooks.
    hooks = run(["git", "config", "--get", "core.hooksPath"], env=env, ok=(0, 1)).strip()
    if hooks != no_hooks:
        raise Error("git does not apply GIT_CONFIG_COUNT (Git 2.31 or later is required)")
    return env


def remove_empty_parent(path):
    try:
        os.rmdir(os.path.dirname(path))
    except OSError:
        pass


def remove_worktree(path):
    try:
        run(["git", "worktree", "remove", "--force", "--", path])
    except Error as e:
        return f"; the worktree {path} could not be removed: {e}"
    remove_empty_parent(path)
    return ""


def any_case(name):
    return "".join(f"[{c.lower()}{c.upper()}]" if c.isalpha() else c for c in name)


def leave_out_agent_files(path, env):
    # A per-worktree sparse-checkout file, enabled only through the environment, leaves the
    # repository's own configuration as it is.
    git_dir = run(["git", "rev-parse", "--absolute-git-dir"], cwd=path, env=env).strip()
    os.makedirs(os.path.join(git_dir, "info"), exist_ok=True)
    with open(os.path.join(git_dir, "info", "sparse-checkout"), "w", encoding="utf-8",
              newline="\n") as f:
        f.write("/*\n" + "".join(f"!{any_case(name)}\n" for name in AGENT_FILES))
    return checkout_env([("core.sparseCheckout", "true"), ("core.sparseCheckoutCone", "false")],
                        env)


def skip_worktree_links(path, env):
    # Under core.symlinks=true, the default outside Windows, git status, diff, add, and commit
    # take a symbolic link checked out as a plain file for a type change; the skip-worktree
    # bit keeps them from seeing one. Set it without core.sparseCheckout, under which git
    # clears the bit from the files present in the worktree. Paths stay bytes, so that one
    # that is not UTF-8 still matches its index entry.
    entries = run(["git", "ls-files", "--stage", "-z"], cwd=path, env=env, text=False)
    links = [entry.partition(b"\t")[2] for entry in entries.split(b"\0")
             if entry.startswith(b"120000 ")]
    if links:
        run(["git", "update-index", "--skip-worktree", "-z", "--stdin"], cwd=path, env=env,
            input=b"".join(link + b"\0" for link in links), text=False)


def changed_links(path, env):
    # Returns the changed links and, apart, those it cannot compare, as bytes when they do not
    # decode.
    git_dir = run(["git", "rev-parse", "--absolute-git-dir"], cwd=path, env=env).strip()
    sparse = os.path.isfile(os.path.join(git_dir, "info", "sparse-checkout"))
    agent_names = {name.lower().encode() for name in AGENT_FILES}
    changed, unexamined = [], []
    entries = run(["git", "ls-files", "-v", "--stage", "-z"], cwd=path, env=env, text=False)
    for entry in entries.split(b"\0"):
        info, _, name = entry.partition(b"\t")
        fields = info.split(b" ")
        if len(fields) != 4 or fields[0] not in (b"S", b"s") or fields[1] != b"120000":
            continue
        # The sparse checkout of a worktree without the agent files leaves those out.
        left_out = sparse and any(part.lower() in agent_names for part in name.split(b"/"))
        try:
            link = os.fsdecode(name)
        except UnicodeDecodeError:
            # Windows decodes a path as strict UTF-8, and Git for Windows checks out one that
            # is not UTF-8 under another name.
            if not left_out:
                unexamined.append(name)
            continue
        file = os.path.join(path, link)
        try:
            mode = os.lstat(file).st_mode
        except (FileNotFoundError, NotADirectoryError) as e:
            if left_out:
                continue
            # On Windows a path past MAX_PATH also fails as FileNotFoundError, with another
            # winerror.
            if getattr(e, "winerror", None) in (None, 2):
                changed.append(link)
            else:
                unexamined.append(link)
            continue
        if not stat.S_ISREG(mode):
            changed.append(link)
            continue
        with open(file, "rb") as f:
            data = f.read()
        # The blob ID git hash-object --no-filters computes; a 40-digit ID is SHA-1.
        oid = fields[2].decode("ascii")
        blob = hashlib.new("sha1" if len(oid) == 40 else "sha256",
                           b"blob %d\0" % len(data) + data, usedforsecurity=False)
        if blob.hexdigest() != oid:
            changed.append(link)
    return changed, unexamined


def quoted(names, limit=3):
    shown = ", ".join(repr(name) for name in names[:limit])
    return shown + (f" and {len(names) - limit} more" if len(names) > limit else "")


def reraise(e):
    raise e


def agent_file_left(root):
    # The file system, not the sparse patterns, decides which names it resolves to these.
    # On Windows a path past MAX_PATH also fails as FileNotFoundError, with another winerror.
    for dirpath, _, _ in os.walk(root, onerror=reraise):
        for name in AGENT_FILES:
            path = os.path.join(dirpath, name)
            try:
                os.lstat(path)
            except FileNotFoundError as e:
                if getattr(e, "winerror", None) in (None, 2):
                    continue
                raise
            return os.path.relpath(path, root).replace(os.sep, "/")
    return None


def check_agent_files_left_out(root, number):
    advice = ("review it only in a sandbox, either with --trust or with the PR head checked out "
              "in the working tree")
    try:
        left = agent_file_left(root)
    except OSError as e:
        raise Error(
            f"the checkout of PR #{number} could not be examined for the agent files the sparse "
            f"checkout leaves out ({type(e).__name__}: {e}); {advice}"
        ) from None
    if left:
        raise Error(
            f"the checkout of PR #{number} still resolves the agent file {left!r}, which the "
            "sparse checkout is meant to leave out, so the PR may be evading that filter; "
            + advice
        )


def valid_branch(name):
    # A leading "-" would be parsed as an option by check-ref-format.
    if not name.startswith("-"):
        try:
            return run(["git", "check-ref-format", "--branch", name]).strip()
        except Error:
            pass
    raise Error(f"invalid branch name: {name!r}")


def header_branch(name):
    try:
        return bool(BRANCH_NAME_RE.fullmatch(name)) and valid_branch(name) == name
    except Error:
        return False


def branch_tip(branch, cwd=None):
    return run(["git", "rev-parse", "--verify", "--quiet", f"refs/heads/{branch}"],
               cwd=cwd, ok=(0, 1)).strip()


def attach_branch(path, branch, head_sha, env):
    # The worktree is at head_sha, so checking out a branch there changes no file, and git
    # refuses a branch checked out in another worktree.
    tip = branch_tip(branch, cwd=path)
    if tip and tip != head_sha:
        raise Error(
            f"branch {branch} already exists at {tip}, not at the PR head {head_sha}, and may "
            "hold fixes an earlier /creview:respond committed; rename it "
            f"(git branch -m {branch} <new-name>) to keep them, then run the skill again"
        )
    run(["git", "checkout", "--quiet", *([] if tip else ["-b"]), branch], cwd=path, env=env)


def add_checkout(number, trust, populate, branch=None):
    # populate(path, env) fills the worktree git adds with --no-checkout.
    main_root = run(["git", "rev-parse", "--show-toplevel"]).strip()
    path = f"{main_root}/.claude/worktrees/creview-pr-{number}-{time.strftime('%Y%m%d-%H%M%S')}"
    if os.path.lexists(path):
        raise Error(f"worktree path already exists: {path}")
    target = ["--", path, branch] if branch else ["--detach", "--", path, "HEAD"]

    with tempfile.TemporaryDirectory() as no_hooks:
        base = env = hook_free_env(no_hooks)
        try:
            run(["git", "-c", f"core.hooksPath={no_hooks}", "worktree", "add", "--quiet",
                 "--no-checkout", *target], env=env)
        except Error:
            # git removes a worktree it failed to add, but not the parent directory it created.
            remove_empty_parent(path)
            raise
        try:
            if not trust:
                env = leave_out_agent_files(path, env)
            populate(path, env)
            skip_worktree_links(path, base)
            if not trust:
                check_agent_files_left_out(path, number)
        except BaseException as e:
            message = str(e) if isinstance(e, Error) else f"{type(e).__name__}: {e}"
            raise Error(message + remove_worktree(path)) from None
    return {"main_root": main_root, "worktree_path": path}


def checkout_pr(url, number, head_sha, trust, branch=None):
    def populate(path, env):
        run(["gh", "pr", "checkout", url, "--detach"], cwd=path, env=env)
        head = run(["git", "rev-parse", "HEAD"], cwd=path).strip()
        if head != head_sha:
            raise Error(
                f"checked out {head}, but PR #{number} was fetched at {head_sha}; "
                "the PR was updated after fetch"
            )
        if branch is not None:
            attach_branch(path, branch, head_sha, env)

    return add_checkout(number, trust, populate)


def checkout_branch(number, branch, trust):
    def populate(path, env):
        # read-tree fills the empty index and the files the sparse patterns keep, and runs
        # no hook.
        run(["git", "read-tree", "-mu", "HEAD"], cwd=path, env=env)

    return add_checkout(number, trust, populate, branch=branch)


def branch_worktree(branch):
    main_root = run(["git", "rev-parse", "--show-toplevel"]).strip()
    path = f"{main_root}/.claude/worktrees/creview-branch-{time.strftime('%Y%m%d-%H%M%S')}"
    if os.path.lexists(path):
        raise Error(f"worktree path already exists: {path}")
    try:
        run(["git", "worktree", "add", "--quiet", "--", path, branch])
    except Error as e:
        # git keeps a worktree whose post-checkout hook fails.
        if os.path.lexists(path):
            raise Error(str(e) + remove_worktree(path)) from None
        remove_empty_parent(path)
        raise
    return {"main_root": main_root, "worktree_path": path}


def cmd_checkout(pr_json, *options):
    if options not in ((), ("--trust",)):
        raise Error(f"unknown checkout option: {' '.join(options)}")
    with open(pr_json, encoding="utf-8") as f:
        pr = json.load(f)
    head_sha = sha(pr["head_sha"], "head commit")
    number = pr["number"]
    if not isinstance(number, int) or not PR_URL_RE.fullmatch(pr["url"]):
        raise Error(f"malformed {pr_json}")
    return checkout_pr(pr["url"], number, head_sha, bool(options))


def malformed(label, value, note=None):
    return Error(f"malformed review document header: {label} bullet {value!r}"
                 + (f"; {note}" if note else ""))


def parse_header(document):
    with open(document, encoding="utf-8", newline="") as f:
        lines = f.readlines()
    found = {}
    for i, line in enumerate(lines):
        if line.startswith("## "):
            break
        m = HEADER_BULLET_RE.fullmatch(line.rstrip())
        if m:
            if m.group(1) in found:
                raise Error(f"malformed review document header: more than one {m.group(1)} bullet")
            found[m.group(1)] = (i, m.group(2))
    header = {"pr": None, "branch": None, "trust": "off"}
    if "PR" in found:
        i, value = found["PR"]
        m = PR_BULLET_RE.fullmatch(value)
        url = m and PR_URL_RE.fullmatch(m.group(1))
        if not url or url.end(4) != len(m.group(1)) \
                or not all(SHA_RE.fullmatch(s) for s in m.group(2, 3)):
            raise malformed("PR", value)
        header["pr"] = {"url": m.group(1), "number": int(url.group(4)), "head_sha": m.group(2),
                        "merge_base": m.group(3), "line": i}
    if "Branch" in found:
        value = found["Branch"][1]
        if not header_branch(value):
            raise malformed("Branch", value, "a Branch bullet names a branch of letters, digits, "
                            "and _ . / + @ - only")
        header["branch"] = value
    if "Trust" in found:
        value = found["Trust"][1]
        if value not in ("on", "off"):
            raise malformed("Trust", value)
        header["trust"] = value
    return header


def record_branch(document, line, branch):
    with open(document, encoding="utf-8", newline="") as f:
        lines = f.readlines()
    eol = lines[line][len(lines[line].rstrip("\r\n")):]
    if not eol:
        eol = "\n"
        lines[line] += eol
    lines.insert(line + 1, f"- **Branch:** {branch}{eol}")
    with open(document, "w", encoding="utf-8", newline="") as f:
        f.writelines(lines)


def checked_out_at(branch):
    path = None
    for line in run(["git", "worktree", "list", "--porcelain"]).splitlines():
        if line.startswith("worktree "):
            path = line[len("worktree "):]
        elif line == f"branch refs/heads/{branch}":
            return path
    return None


def added_worktree(path, *names):
    parent, _, name = path.rpartition("/")
    return parent.endswith("/.claude/worktrees") and any(n.fullmatch(name) for n in names)


def check_free(branch):
    busy = checked_out_at(branch)
    if busy and added_worktree(busy, PR_WORKTREE_RE, BRANCH_WORKTREE_RE):
        script = os.path.abspath(__file__).replace(os.sep, "/")
        command = shlex.join(["python3", script, "remove", busy])
        if added_worktree(busy, PR_WORKTREE_RE):
            steps, note = "", "; it holds a pull request's code, so do not run git in it"
        else:
            steps, note = "review its changes, commit or discard them, and ", ""
        raise Error(
            f"branch {branch} is checked out in the worktree {busy}, which a creview skill kept "
            f"for uncommitted changes or initialized submodules; {steps}remove it by running "
            f"{command} in {shlex.quote(busy.rsplit('/', 3)[0])} "
            f"(follow its error when it refuses{note}) before running the skill again"
        )
    if busy:
        raise Error(
            f"branch {branch} is checked out in the worktree {busy}; run the skill in a session "
            "started at that worktree's root"
        )


def contains(commit):
    try:
        run(["git", "merge-base", "--is-ancestor", commit, "HEAD"])
    except Error:
        return False
    return True


def cmd_doc_checkout(document, *options):
    if options not in ((), ("--fix-branch",)):
        raise Error(f"unknown doc-checkout option: {' '.join(options)}")
    top = run(["git", "rev-parse", "--show-toplevel"]).strip()
    if added_worktree(top, PR_WORKTREE_RE):
        raise Error(
            f"this session is in {top}, a worktree holding a pull request's code; run the skill "
            "in a session started at the main working tree"
        )
    header = parse_header(document)
    pr, branch = header["pr"], header["branch"]
    trust = header["trust"] == "on"
    current = run(["git", "branch", "--show-current"]).strip() or None
    result = {
        "in_place": True, "pr_worktree": False, "trust": header["trust"], "main_root": None,
        "worktree_path": None, "branch": current, "merge_base": pr and pr["merge_base"],
    }
    if branch is not None:
        if branch != current:
            if not branch_tip(branch):
                raise Error(f"no local branch {branch}")
            check_free(branch)
            added = checkout_branch(pr["number"], branch, trust) if pr else branch_worktree(branch)
            result.update(added, in_place=False, pr_worktree=pr is not None, branch=branch)
    elif pr is not None:
        if not contains(pr["head_sha"]):
            _, _, number, url, view = view_pr(pr["url"])
            head = sha(view["headRefOid"], "head commit")
            if head != pr["head_sha"]:
                raise Error(
                    f"PR #{number} changed after the review (reviewed at {pr['head_sha']}, now "
                    f"at {head}); review it again with /creview:start"
                )
            name = f"creview-pr-{number}" if options else None
            if name:
                check_free(name)
            added = checkout_pr(url, number, head, trust, name)
            result.update(added, in_place=False, pr_worktree=True, branch=name)
        if options and result["branch"] and header_branch(result["branch"]):
            try:
                record_branch(document, pr["line"], result["branch"])
            except OSError as e:
                if result["in_place"]:
                    raise
                raise Error(f"the review document could not be updated ({e})"
                            + remove_worktree(result["worktree_path"])) from None
    return result


def submodules_note(path, env=None):
    # git refuses to remove a worktree whose git directory has a modules directory, which git
    # submodule deinit leaves in place; only --force skips that check.
    try:
        top, git_dir = run(["git", "rev-parse", "--show-toplevel", "--absolute-git-dir"],
                           cwd=path, env=env).splitlines()
    except (Error, OSError, ValueError):
        return ""
    if top != path or not os.path.isdir(os.path.join(git_dir, "modules")):
        return ""
    command = shlex.join(["git", "worktree", "remove", "--force", "--", path])
    return (f"; the worktree {path} has initialized submodules, which git worktree remove "
            "refuses: check that neither it nor its submodules hold changes or commits to keep, "
            f"then remove it with {command}")


def pr_worktree_note(path, main_root, keep=True):
    command = shlex.join(["git", "worktree", "remove", "--force", "--", path])
    return (f"; {path} holds a pull request's code, and git run in it can run the pull "
            "request's hooks and filters: do not run git in it; "
            + ("copy out what to keep, then " if keep else "")
            + f"remove it by running {command} in {shlex.quote(main_root)}")


def worktree_remove(path, *config, env=None, note=None):
    try:
        run(["git", *config, "worktree", "remove", "--", path], env=env)
    except Error as e:
        raise Error(f"{e}{submodules_note(path, env) if note is None else note}") from None


def discard_pr_worktree(path, main_root, no_hooks, env):
    # --force skips the clean check, which runs git status in the worktree.
    try:
        run(["git", "-c", f"core.hooksPath={no_hooks}", "worktree", "remove", "--force", "--",
             path], cwd=main_root, env=env)
    except Error as e:
        raise Error(f"{e}{pr_worktree_note(path, main_root, keep=False)}") from None


def cmd_remove(path, *options):
    if options not in ((), ("--discard",)):
        raise Error(f"unknown remove option: {' '.join(options)}")
    main_root = run(["git", "rev-parse", "--show-toplevel"]).strip()
    parent, _, name = path.rpartition("/")
    if parent != f"{main_root}/.claude/worktrees":
        name = ""
    if BRANCH_WORKTREE_RE.fullmatch(name):
        worktree_remove(path)
    elif PR_WORKTREE_RE.fullmatch(name) and options:
        with tempfile.TemporaryDirectory() as no_hooks:
            discard_pr_worktree(path, main_root, no_hooks, hook_free_env(no_hooks))
    elif PR_WORKTREE_RE.fullmatch(name):
        with tempfile.TemporaryDirectory() as no_hooks:
            env = hook_free_env(no_hooks)
            note, changed, unexamined = "", [], []
            if os.path.isdir(path):
                note = pr_worktree_note(path, main_root)
                try:
                    changed, unexamined = changed_links(path, env)
                except (Error, OSError) as e:
                    raise Error(f"the worktree {path} is kept: its symbolic links could not be "
                                f"examined for changes ({e}){note}") from None
            reasons = []
            if changed:
                reasons.append(f"it changes the symbolic links {quoted(changed)}, which it holds "
                               "as plain files that git status does not show")
            if unexamined:
                reasons.append(f"its symbolic links {quoted(unexamined)}, which it holds as "
                               "plain files, could not be examined for changes (a path that is "
                               "not UTF-8, or one Windows cannot open, such as one past "
                               "MAX_PATH)")
            if reasons:
                raise Error(f"the worktree {path} is kept: {', and '.join(reasons)}{note}")
            # git checks that the worktree is clean with a git status that inherits the
            # overrides and skips the skip-worktree links, which changed_links compares.
            worktree_remove(path, "-c", f"core.hooksPath={no_hooks}", env=env, note=note)
    else:
        raise Error(f"not a worktree that checkout or doc-checkout adds: {path}")
    remove_empty_parent(path)
    return {"worktree_path": path}


# Each command with the least and the most arguments it takes.
COMMANDS = {
    "fetch": (cmd_fetch, 2, 2), "checkout": (cmd_checkout, 1, 2),
    "doc-checkout": (cmd_doc_checkout, 1, 2), "remove": (cmd_remove, 1, 2),
}


def main(argv):
    command = COMMANDS.get(argv[0]) if argv else None
    if command is None or not command[1] <= len(argv) - 1 <= command[2]:
        print(__doc__.split("\n\n")[1], file=sys.stderr)
        return 1
    func = command[0]
    try:
        result = func(*argv[1:])
    except (Error, OSError, ValueError, KeyError, TypeError) as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
