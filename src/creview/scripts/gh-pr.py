#!/usr/bin/env python3
"""gh-pr.py — resolve a GitHub pull request for a creview PR review and check it out.

Usage:
    python3 gh-pr.py fetch <pr_url> <out_dir>
    python3 gh-pr.py checkout <pr_json>

fetch: resolves <pr_url> (https://<host>/<owner>/<repo>/pull/<number>) with gh,
requires <owner>/<repo> to be a remote of the current repository and the PR to
be open, and writes two files to <out_dir>:
  pr.json          url, head and base commits, merge base
  pr-context.json  title and body, CI check results (with a log excerpt for each
                   failed GitHub Actions job), and the conversation: issue
                   comments, submitted review bodies, and review comments
It prints a JSON object whose in_place is true when HEAD of the current working
tree is the PR head. An in-place working tree with uncommitted changes (outside
.claude/tmp and .claude/worktrees) is an error.

checkout: adds a detached worktree under .claude/worktrees/ of the current
working tree, checks the PR head out in it with git hooks disabled and Git LFS
smudging skipped, confirms its HEAD is the head fetch recorded, and prints a
JSON object with main_root and worktree_path. A failed checkout removes the
worktree it added.

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
# The owner and repository are the last two components of a remote URL in any
# of its forms (https://host/o/r.git, git@host:o/r.git, ssh://git@host/o/r).
REMOTE_REPO_RE = re.compile(r"[/:]([^/:]+)/([^/]+?)(?:\.git)?/*$")
SHA_RE = re.compile(r"[0-9a-f]{40}(?:[0-9a-f]{24})?")
# Scratch and worktree directories of the creview skills, not part of the review.
SCRATCH_EXCLUDES = [":(top,exclude).claude/tmp", ":(top,exclude).claude/worktrees"]
ACTIONS_JOB_RE = re.compile(r"/actions/runs/[0-9]+/job/([0-9]+)")
FAILED_CONCLUSIONS = {"FAILURE", "TIMED_OUT", "CANCELLED", "ACTION_REQUIRED", "STARTUP_FAILURE"}
MAX_JOB_LOGS = 10
LOG_LINES = 150
LOG_LINE_CHARS = 500
BODY_CHARS = 20000
COMMENT_CHARS = 4000
PAGE_SIZE = 100


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


def run(cmd, cwd=None, env=None):
    program = executable(cmd[0])
    if program is None:
        raise Error(f"{cmd[0]} not found on PATH")
    proc = subprocess.run(
        [program, *cmd[1:]], cwd=cwd, env=env, capture_output=True,
        text=True, encoding="utf-8", errors="replace",
    )
    if proc.returncode != 0:
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


def api_pages(endpoint, host):
    items, page = [], 1
    while True:
        batch = json.loads(run([
            "gh", "api", "--hostname", host, f"{endpoint}?per_page={PAGE_SIZE}&page={page}",
        ]))
        items.extend(batch)
        if len(batch) < PAGE_SIZE:
            return items
        page += 1


def job_log_excerpt(host, repo, job_id):
    # A failing step reports itself with an ##[error] line; the cause precedes it,
    # and the job's cleanup steps follow it.
    lines = run(["gh", "api", "--hostname", host, f"repos/{repo}/actions/jobs/{job_id}/logs"])
    lines = lines.splitlines()
    errors = [i for i, line in enumerate(lines) if "##[error]" in line]
    end = errors[-1] + 1 if errors else len(lines)
    return "\n".join(line[:LOG_LINE_CHARS] for line in lines[max(0, end - LOG_LINES):end])


def ci_checks(rollup, host, repo):
    checks, logs = [], 0
    for c in rollup or []:
        if c.get("__typename") == "StatusContext":
            checks.append({
                "name": c.get("context"),
                "state": c.get("state"),
                "description": c.get("description"),
                "url": c.get("targetUrl"),
            })
            continue
        check = {
            "name": c.get("name"),
            "workflow": c.get("workflowName"),
            "status": c.get("status"),
            "conclusion": c.get("conclusion"),
            "url": c.get("detailsUrl"),
        }
        job = ACTIONS_JOB_RE.search(check["url"] or "")
        if check["conclusion"] in FAILED_CONCLUSIONS and job and logs < MAX_JOB_LOGS:
            logs += 1
            try:
                check["log_excerpt"] = job_log_excerpt(host, repo, job.group(1))
            except Error as e:
                check["log_error"] = str(e)
        checks.append(check)
    return checks


def conversation(host, repo, number):
    reviews = api_pages(f"repos/{repo}/pulls/{number}/reviews", host)
    pending = {r.get("id") for r in reviews if r.get("state") == "PENDING"}
    return {
        "issue_comments": [
            {"author": login(c.get("user")), "created_at": c.get("created_at"),
             "body": clip(c.get("body"), COMMENT_CHARS)}
            for c in api_pages(f"repos/{repo}/issues/{number}/comments", host)
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
            for c in api_pages(f"repos/{repo}/pulls/{number}/comments", host)
            if c.get("pull_request_review_id") not in pending
        ],
    }


def remote_repos():
    try:
        listing = run(["git", "config", "--get-regexp", r"^remote\..*\.url$"])
    except Error:
        return set()
    repos = set()
    for line in listing.splitlines():
        m = REMOTE_REPO_RE.search(line.partition(" ")[2].strip())
        if m:
            repos.add((m.group(1).lower(), m.group(2).lower()))
    return repos


def cmd_fetch(pr_url, out_dir):
    m = PR_URL_RE.fullmatch(pr_url)
    if not m:
        raise Error(f"not a pull request URL: {pr_url}")
    host, owner, name, number = m.group(1).lower(), m.group(2), m.group(3), int(m.group(4))
    repo = f"{owner}/{name}"
    if (owner.lower(), name.lower()) not in remote_repos():
        raise Error(f"{repo} is not a remote of this repository")

    pr = json.loads(run([
        "gh", "pr", "view", f"https://{host}/{repo}/pull/{number}",
        "--json", "url,number,state,headRefOid,baseRefOid,title,body,statusCheckRollup",
    ]))
    if pr["state"] != "OPEN":
        raise Error(f"PR #{pr['number']} is {pr['state'].lower()}, not open")
    head_sha = sha(pr["headRefOid"], "head commit")
    base_sha = sha(pr["baseRefOid"], "base commit")
    merge_base = sha(run([
        "gh", "api", "--hostname", host,
        f"repos/{repo}/compare/{base_sha}...{head_sha}",
        "--jq", ".merge_base_commit.sha",
    ]).strip(), "merge base")

    in_place = run(["git", "rev-parse", "HEAD"]).strip() == head_sha
    if in_place and run(["git", "status", "--porcelain", "--", *SCRATCH_EXCLUDES]).strip():
        raise Error(
            "the working tree is at the PR head but has uncommitted changes; "
            "commit or stash them first"
        )

    write_json(os.path.join(out_dir, "pr.json"), {
        "url": pr["url"],
        "repo": repo,
        "number": pr["number"],
        "head_sha": head_sha,
        "base_sha": base_sha,
        "merge_base": merge_base,
    })
    write_json(os.path.join(out_dir, "pr-context.json"), {
        "title": pr["title"],
        "body": clip(pr["body"], BODY_CHARS),
        "checks": ci_checks(pr["statusCheckRollup"], host, repo),
        "conversation": conversation(host, repo, pr["number"]),
    })
    return {
        "url": pr["url"],
        "number": pr["number"],
        "head_sha": head_sha,
        "merge_base": merge_base,
        "in_place": in_place,
    }


def checkout_env(no_hooks):
    # A PR can add or change the hooks a relative core.hooksPath points at, and
    # gh runs git itself, so the override travels in the environment.
    env = dict(os.environ)
    try:
        n = int(env.get("GIT_CONFIG_COUNT") or 0)
    except ValueError:
        raise Error("GIT_CONFIG_COUNT is not a number") from None
    env.update({
        "GIT_CONFIG_COUNT": str(n + 1),
        f"GIT_CONFIG_KEY_{n}": "core.hooksPath",
        f"GIT_CONFIG_VALUE_{n}": no_hooks,
        "GIT_LFS_SKIP_SMUDGE": "1",
        "GH_PROMPT_DISABLED": "1",
    })
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


def cmd_checkout(pr_json):
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
        try:
            run(["git", "-c", f"core.hooksPath={no_hooks}",
                 "worktree", "add", "--quiet", "--detach", "--", path, "HEAD"])
        except Error:
            # git removes a worktree it failed to add, but not the parent directory it created.
            remove_empty_parent(path)
            raise
        try:
            env = checkout_env(no_hooks)
            # Git before 2.31 ignores GIT_CONFIG_COUNT; refuse rather than run hooks.
            hooks = run(["git", "config", "--get", "core.hooksPath"], cwd=path, env=env).strip()
            if hooks != no_hooks:
                raise Error("git does not apply GIT_CONFIG_COUNT (Git 2.31 or later is required)")
            run(["gh", "pr", "checkout", pr["url"], "--detach"], cwd=path, env=env)
            head = run(["git", "rev-parse", "HEAD"], cwd=path).strip()
            if head != head_sha:
                raise Error(
                    f"checked out {head}, but PR #{number} was fetched at {head_sha}; "
                    "the PR was updated after fetch"
                )
        except BaseException as e:
            message = str(e) if isinstance(e, Error) else f"{type(e).__name__}: {e}"
            raise Error(message + remove_worktree(path)) from None
    return {"main_root": main_root, "worktree_path": path}


COMMANDS = {"fetch": (cmd_fetch, 2), "checkout": (cmd_checkout, 1)}


def main(argv):
    if not argv or argv[0] not in COMMANDS or len(argv) - 1 != COMMANDS[argv[0]][1]:
        print(__doc__.split("\n\n")[1], file=sys.stderr)
        return 1
    func = COMMANDS[argv[0]][0]
    try:
        result = func(*argv[1:])
    except (Error, OSError, ValueError, KeyError, TypeError) as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
