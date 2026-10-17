#!/usr/bin/env python3
"""gh-pr.py — resolve a GitHub pull request for a creview PR review and check it out.

Usage:
    python3 gh-pr.py fetch <pr_url> <out_dir>
    python3 gh-pr.py checkout <pr_json> [--trust]
    python3 gh-pr.py remove <worktree_path>

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
                   were left out
It prints a JSON object whose in_place is true when HEAD of the current working
tree is the PR head.
An in-place working tree with uncommitted changes to tracked files (outside
.claude/tmp and .claude/worktrees) is an error.

checkout: adds a detached worktree under .claude/worktrees/ of the current
working tree, checks the PR head out in it with git hooks and the configured
filter drivers disabled, Git LFS smudging skipped, and symbolic links checked
out as plain files, confirms its HEAD is the head fetch recorded, and prints a
JSON object with main_root and worktree_path. Without --trust, the checkout
leaves out every file and directory named like one of AGENT_FILES, in any
letter case and at any depth, and fails when the file system still resolves one
of those names in a directory of the worktree.
A failed checkout removes the worktree it added.

remove: removes a worktree that checkout added
(<main_root>/.claude/worktrees/creview-pr-<number>-<timestamp>; any other path
is an error), with git hooks and the configured filter drivers disabled, and its
parent directory when left empty. A worktree with uncommitted changes is kept,
and the exit status is 1.

Exits 1 with an error message on stderr on any failure.
"""

import json
import os
import re
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
# The name of a worktree cmd_checkout adds under .claude/worktrees.
WORKTREE_NAME_RE = re.compile(r"creview-pr-[0-9]+-[0-9]{8}-[0-9]{6}")
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


def run(cmd, cwd=None, env=None, ok=(0,)):
    program = executable(cmd[0])
    if program is None:
        raise Error(f"{cmd[0]} not found on PATH")
    proc = subprocess.run(
        [program, *cmd[1:]], cwd=cwd, env=env, capture_output=True,
        text=True, encoding="utf-8", errors="replace",
    )
    if proc.returncode not in ok:
        raise Error(proc.stderr.strip() or f"{' '.join(cmd[:2])} exited with {proc.returncode}")
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


def conversation(host, repo, number):
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


def cmd_fetch(pr_url, out_dir):
    m = PR_URL_RE.fullmatch(pr_url)
    if not m:
        raise Error(f"not a pull request URL: {pr_url}")
    host, owner, name, number = m.group(1).lower(), m.group(2), m.group(3), int(m.group(4))
    repo = f"{owner}/{name}"
    if not is_remote(host, owner, name):
        raise Error(f"{repo} on {host} is not a remote of this repository")
    url = f"https://{host}/{repo}/pull/{number}"

    pr = json.loads(run([
        "gh", "pr", "view", url,
        "--json", "number,state,headRefOid,baseRefOid,headRepository,headRepositoryOwner,"
        "title,body,statusCheckRollup",
    ]))
    got = pr.get("number")
    if not isinstance(got, int) or isinstance(got, bool) or got != number:
        raise Error(f"gh did not return PR #{number}")
    if pr.get("state") != "OPEN":
        raise Error(f"PR #{number} is not open")
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


def cmd_checkout(pr_json, *options):
    if options not in ((), ("--trust",)):
        raise Error(f"unknown checkout option: {' '.join(options)}")
    with open(pr_json, encoding="utf-8") as f:
        pr = json.load(f)
    head_sha = sha(pr["head_sha"], "head commit")
    number = pr["number"]
    if not isinstance(number, int) or not PR_URL_RE.fullmatch(pr["url"]):
        raise Error(f"malformed {pr_json}")

    main_root = run(["git", "rev-parse", "--show-toplevel"]).strip()
    path = f"{main_root}/.claude/worktrees/creview-pr-{number}-{time.strftime('%Y%m%d-%H%M%S')}"
    if os.path.lexists(path):
        raise Error(f"worktree path already exists: {path}")

    with tempfile.TemporaryDirectory() as no_hooks:
        env = hook_free_env(no_hooks)
        try:
            run(["git", "-c", f"core.hooksPath={no_hooks}", "worktree", "add", "--quiet",
                 "--no-checkout", "--detach", "--", path, "HEAD"], env=env)
        except Error:
            # git removes a worktree it failed to add, but not the parent directory it created.
            remove_empty_parent(path)
            raise
        try:
            if not options:
                env = leave_out_agent_files(path, env)
            run(["gh", "pr", "checkout", pr["url"], "--detach"], cwd=path, env=env)
            head = run(["git", "rev-parse", "HEAD"], cwd=path).strip()
            if head != head_sha:
                raise Error(
                    f"checked out {head}, but PR #{number} was fetched at {head_sha}; "
                    "the PR was updated after fetch"
                )
            left = None if options else agent_file_left(path)
            if left:
                raise Error(
                    f"the checkout of PR #{number} still resolves the agent file {left!r}, "
                    "which the sparse checkout is meant to leave out, so the PR may be evading "
                    "that filter; review it only in a sandbox, either with --trust or with the "
                    "PR head checked out in the working tree"
                )
        except BaseException as e:
            message = str(e) if isinstance(e, Error) else f"{type(e).__name__}: {e}"
            raise Error(message + remove_worktree(path)) from None
    return {"main_root": main_root, "worktree_path": path}


def cmd_remove(path):
    main_root = run(["git", "rev-parse", "--show-toplevel"]).strip()
    parent, _, name = path.rpartition("/")
    if parent != f"{main_root}/.claude/worktrees" or not WORKTREE_NAME_RE.fullmatch(name):
        raise Error(f"not a worktree that checkout adds: {path}")
    with tempfile.TemporaryDirectory() as no_hooks:
        env = hook_free_env(no_hooks)
        # git checks that the worktree is clean with a git status that inherits the overrides.
        run(["git", "-c", f"core.hooksPath={no_hooks}", "worktree", "remove", "--", path], env=env)
    remove_empty_parent(path)
    return {"worktree_path": path}


# Each command with the least and the most arguments it takes.
COMMANDS = {
    "fetch": (cmd_fetch, 2, 2), "checkout": (cmd_checkout, 1, 2), "remove": (cmd_remove, 1, 1),
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
