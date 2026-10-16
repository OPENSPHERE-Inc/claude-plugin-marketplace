#!/usr/bin/env python3
"""gh-pr.py — resolve a GitHub pull request for a creview PR review and check it out.

Usage:
    python3 gh-pr.py fetch <pr_url> <pr_json>
    python3 gh-pr.py checkout <pr_json>

fetch: resolves <pr_url> (https://<host>/<owner>/<repo>/pull/<number>) with gh,
requires <owner>/<repo> to be a remote of the current repository, writes
<pr_json> (url, head and base commits, merge base), and prints a JSON object
whose in_place is true when HEAD of the current working tree is the PR head.
An in-place working tree with uncommitted changes (outside .claude/tmp and
.claude/worktrees) is an error.

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


def cmd_fetch(pr_url, pr_json):
    m = PR_URL_RE.fullmatch(pr_url)
    if not m:
        raise Error(f"not a pull request URL: {pr_url}")
    host, owner, name, number = m.group(1).lower(), m.group(2), m.group(3), int(m.group(4))
    if (owner.lower(), name.lower()) not in remote_repos():
        raise Error(f"{owner}/{name} is not a remote of this repository")

    pr = json.loads(run([
        "gh", "pr", "view", f"https://{host}/{owner}/{name}/pull/{number}",
        "--json", "url,number,headRefOid,baseRefOid",
    ]))
    head_sha = sha(pr["headRefOid"], "head commit")
    base_sha = sha(pr["baseRefOid"], "base commit")
    merge_base = sha(run([
        "gh", "api", "--hostname", host,
        f"repos/{owner}/{name}/compare/{base_sha}...{head_sha}",
        "--jq", ".merge_base_commit.sha",
    ]).strip(), "merge base")

    in_place = run(["git", "rev-parse", "HEAD"]).strip() == head_sha
    if in_place and run(["git", "status", "--porcelain", "--", *SCRATCH_EXCLUDES]).strip():
        raise Error(
            "the working tree is at the PR head but has uncommitted changes; "
            "commit or stash them first"
        )

    with open(pr_json, "w", encoding="utf-8", newline="\n") as f:
        json.dump({
            "url": pr["url"],
            "repo": f"{owner}/{name}",
            "number": pr["number"],
            "head_sha": head_sha,
            "base_sha": base_sha,
            "merge_base": merge_base,
        }, f, indent=2)
        f.write("\n")
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


def remove_worktree(path):
    try:
        run(["git", "worktree", "remove", "--force", "--", path])
    except Error as e:
        return f"; the worktree {path} could not be removed: {e}"
    try:
        os.rmdir(os.path.dirname(path))
    except OSError:
        pass
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
        run(["git", "-c", f"core.hooksPath={no_hooks}",
             "worktree", "add", "--quiet", "--detach", "--", path, "HEAD"])
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
