#!/usr/bin/env python3
"""gh-pr.py — Fetch a GitHub pull request for /creview:pr and post its review.

Usage:
    python3 gh-pr.py fetch [<pr>] <out_dir>
    python3 gh-pr.py checkout <pr_json>
    python3 gh-pr.py post <pr_json> <payload_json> [--dry-run]

fetch: resolves <pr> (a number or URL; the current branch's PR when omitted)
with gh, requires it to be open and to belong to the repository gh resolves for
the working directory, and writes <out_dir>/pr.json (metadata, description,
merge base) and <out_dir>/conversation.json (issue comments, submitted review
bodies, and review threads with their resolved / outdated state and diff hunk).
Prints a summary JSON object.

checkout: checks the PR head out, detached, in the working directory with git
hooks disabled, and confirms HEAD is the head fetch recorded.

post: places each payload comment inline (its line is commentable in the PR
diff), at file level (its file is in the diff), or in the review body
(otherwise), then submits one review: REQUEST_CHANGES when a Critical / Major
comment is posted, COMMENT otherwise or on the viewer's own PR. It never
approves. Refuses when the PR is closed, its head moved since fetch, or the
viewer already has a pending review on it. --dry-run prints the plan without
posting.

payload_json:
    {"body": str, "outside_diff_heading": str,
     "comments": [{"id": str, "severity": "Critical|Major|Minor|Info",
                   "location": str, "path": str|null, "line": int|null,
                   "body": str}]}
"""

import json
import os
import re
import subprocess
import sys
import tempfile
from urllib.parse import urlparse

PAGE_SIZE = 100
HUNK_RE = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@")
PR_URL_RE = re.compile(r"/([^/]+)/([^/]+)/pull/(\d+)")
SEVERITIES = ("Critical", "Major", "Minor", "Info")
BLOCKING = ("Critical", "Major")
PR_FIELDS = ",".join((
    "number", "url", "title", "body", "state", "isDraft", "author",
    "baseRefName", "baseRefOid", "headRefName", "headRefOid", "isCrossRepository",
))

THREADS_QUERY = """
query($owner: String!, $name: String!, $number: Int!, $after: String) {
  repository(owner: $owner, name: $name) {
    pullRequest(number: $number) {
      reviewThreads(first: 100, after: $after) {
        pageInfo { hasNextPage endCursor }
        nodes {
          isResolved
          isOutdated
          path
          line
          originalLine
          subjectType
          resolvedBy { login }
          comments(first: 100) {
            nodes { author { __typename login } body createdAt url state diffHunk }
          }
        }
      }
    }
  }
}
"""

ADD_FILE_THREAD = """
mutation($review: ID!, $path: String!, $body: String!) {
  addPullRequestReviewThread(input: {
    pullRequestReviewId: $review, path: $path, body: $body, subjectType: FILE
  }) {
    thread { id }
  }
}
"""


class GhError(Exception):
    pass


def run(cmd, stdin=None, env=None):
    try:
        proc = subprocess.run(
            cmd, input=stdin, capture_output=True, text=True, encoding="utf-8", env=env,
        )
    except FileNotFoundError:
        raise GhError(f"{cmd[0]} not found on PATH")
    if proc.returncode != 0:
        raise GhError(proc.stderr.strip() or f"{' '.join(cmd[:3])} exited with {proc.returncode}")
    return proc.stdout


def api(endpoint, host, method="GET", body=None):
    cmd = ["gh", "api", "--hostname", host, "--method", method, endpoint]
    if body is not None:
        cmd += ["--input", "-"]
    out = run(cmd, None if body is None else json.dumps(body))
    return json.loads(out) if out.strip() else None


def api_pages(endpoint, host):
    items, page = [], 1
    while True:
        batch = api(f"{endpoint}?per_page={PAGE_SIZE}&page={page}", host)
        items.extend(batch)
        if len(batch) < PAGE_SIZE:
            return items
        page += 1


def graphql(query, variables, host):
    result = api("graphql", host, "POST", {"query": query, "variables": variables})
    if result.get("errors"):
        raise GhError("; ".join(e.get("message", str(e)) for e in result["errors"]))
    return result["data"]


def login_of(actor):
    return (actor or {}).get("login") or "ghost"


def write_json(path, data):
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")


def read_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def fetch_threads(owner, name, number, host):
    threads, after = [], None
    while True:
        data = graphql(THREADS_QUERY, {
            "owner": owner, "name": name, "number": number, "after": after,
        }, host)
        conn = data["repository"]["pullRequest"]["reviewThreads"]
        for node in conn["nodes"]:
            comments = [c for c in node["comments"]["nodes"] if c["state"] != "PENDING"]
            if not comments:
                continue
            threads.append({
                "path": node["path"],
                "line": node["line"],
                "original_line": node["originalLine"],
                "subject_type": node["subjectType"],
                "resolved": node["isResolved"],
                "outdated": node["isOutdated"],
                "resolved_by": login_of(node["resolvedBy"]) if node["resolvedBy"] else None,
                "diff_hunk": comments[0]["diffHunk"],
                "comments": [
                    {
                        "author": login_of(c["author"]),
                        "author_type": (c["author"] or {}).get("__typename"),
                        "created_at": c["createdAt"],
                        "url": c["url"],
                        "body": c["body"],
                    }
                    for c in comments
                ],
            })
        if not conn["pageInfo"]["hasNextPage"]:
            return threads
        after = conn["pageInfo"]["endCursor"]


def cmd_fetch(argv):
    if len(argv) not in (1, 2):
        raise GhError("usage: fetch [<pr>] <out_dir>")
    pr_arg, out_dir = (None, argv[0]) if len(argv) == 1 else argv

    pr = json.loads(run(["gh", "pr", "view", *([pr_arg] if pr_arg else []), "--json", PR_FIELDS]))
    m = PR_URL_RE.search(pr["url"])
    if not m:
        raise GhError(f"cannot parse the repository from {pr['url']}")
    owner, name, number = m.group(1), m.group(2), pr["number"]
    repo, host = f"{owner}/{name}", urlparse(pr["url"]).netloc
    local = run(["gh", "repo", "view", "--json", "nameWithOwner", "--jq", ".nameWithOwner"]).strip()
    if local.lower() != repo.lower():
        raise GhError(f"{pr['url']} belongs to {repo}, not to this repository ({local})")
    if pr["state"] != "OPEN":
        raise GhError(f"PR #{number} is {pr['state'].lower()}, not open")

    compare = api(f"repos/{repo}/compare/{pr['baseRefOid']}...{pr['headRefOid']}", host)
    write_json(os.path.join(out_dir, "pr.json"), {
        "host": host,
        "repo": repo,
        "number": number,
        "url": pr["url"],
        "title": pr["title"],
        "body": pr["body"],
        "author": login_of(pr["author"]),
        "is_draft": pr["isDraft"],
        "is_cross_repository": pr["isCrossRepository"],
        "base_ref": pr["baseRefName"],
        "base_sha": pr["baseRefOid"],
        "head_ref": pr["headRefName"],
        "head_sha": pr["headRefOid"],
        "merge_base": compare["merge_base_commit"]["sha"],
    })

    issue_comments = [
        {
            "author": login_of(c.get("user")),
            "author_type": (c.get("user") or {}).get("type"),
            "created_at": c["created_at"],
            "url": c["html_url"],
            "body": c["body"],
        }
        for c in api_pages(f"repos/{repo}/issues/{number}/comments", host)
    ]
    reviews = [
        {
            "author": login_of(r.get("user")),
            "author_type": (r.get("user") or {}).get("type"),
            "state": r["state"],
            "submitted_at": r.get("submitted_at"),
            "url": r["html_url"],
            "body": r["body"],
        }
        for r in api_pages(f"repos/{repo}/pulls/{number}/reviews", host)
        if r.get("body") and r["state"] != "PENDING"
    ]
    threads = fetch_threads(owner, name, number, host)
    write_json(os.path.join(out_dir, "conversation.json"), {
        "issue_comments": issue_comments,
        "reviews": reviews,
        "review_threads": threads,
    })

    return {
        "repo": repo,
        "number": number,
        "url": pr["url"],
        "title": pr["title"],
        "head_sha": pr["headRefOid"],
        "merge_base": compare["merge_base_commit"]["sha"],
        "issue_comments": len(issue_comments),
        "reviews": len(reviews),
        "review_threads": len(threads),
        "unresolved_threads": sum(1 for t in threads if not t["resolved"]),
    }


def cmd_checkout(argv):
    if len(argv) != 1:
        raise GhError("usage: checkout <pr_json>")
    pr = read_json(argv[0])
    # A PR can add or change the hooks a relative core.hooksPath points at; an
    # empty hooks directory keeps the checkout from running any of them.
    with tempfile.TemporaryDirectory() as no_hooks:
        env = dict(os.environ)
        n = int(env.get("GIT_CONFIG_COUNT") or 0)
        env.update({
            "GIT_CONFIG_COUNT": str(n + 1),
            f"GIT_CONFIG_KEY_{n}": "core.hooksPath",
            f"GIT_CONFIG_VALUE_{n}": no_hooks,
        })
        run(["gh", "pr", "checkout", str(pr["number"]), "--detach"], env=env)
    head = run(["git", "rev-parse", "HEAD"]).strip()
    if head != pr["head_sha"]:
        raise GhError(
            f"checked out {head}, but PR #{pr['number']} was fetched at {pr['head_sha']}; "
            "the PR was updated since fetch"
        )
    return {"head_sha": head}


def commentable_lines(patch):
    """Return the new-side line numbers of a unified-diff patch that a review comment can target."""
    lines, new_line = set(), None
    for raw in patch.split("\n"):
        m = HUNK_RE.match(raw)
        if m:
            new_line = int(m.group(1))
            continue
        if new_line is None or not raw or raw[0] in "-\\":
            continue
        lines.add(new_line)
        new_line += 1
    return lines


def normalize_path(path):
    path = path.replace("\\", "/")
    while path.startswith("./"):
        path = path[2:]
    return path


def validate_payload(payload):
    comments = payload.get("comments")
    if not isinstance(comments, list) or not comments:
        raise GhError("payload has no comments")
    for key in ("body", "outside_diff_heading"):
        if not isinstance(payload.get(key), str) or not payload[key].strip():
            raise GhError(f"payload {key} must be a non-empty string")
    for c in comments:
        cid = c.get("id")
        if c.get("severity") not in SEVERITIES:
            raise GhError(f"comment {cid}: severity must be one of {', '.join(SEVERITIES)}")
        for key in ("id", "location", "body"):
            if not isinstance(c.get(key), str) or not c[key].strip():
                raise GhError(f"comment {cid}: {key} must be a non-empty string")
        if c.get("path") is not None and not isinstance(c["path"], str):
            raise GhError(f"comment {cid}: path must be a string or null")
        line = c.get("line")
        if line is not None and (isinstance(line, bool) or not isinstance(line, int)):
            raise GhError(f"comment {cid}: line must be an integer or null")
    return comments


def place(comment, files):
    path = comment.get("path")
    if not path or normalize_path(path) not in files:
        return "body"
    if comment.get("line") in files[normalize_path(path)]:
        return "inline"
    return "file"


def file_comment_body(comment):
    if comment.get("line") is None:
        return comment["body"]
    return f"**{comment['location']}**\n\n{comment['body']}"


def review_body(payload, body_comments):
    parts = [payload["body"].strip()]
    if body_comments:
        parts.append(f"### {payload['outside_diff_heading'].strip()}")
        parts.extend(f"**{c['location']}**\n\n{c['body'].strip()}" for c in body_comments)
    return "\n\n".join(parts)


def settle_failed_review(repo, number, review_id, exc, host):
    """Return the review if GitHub already submitted it; otherwise delete it and return None."""
    endpoint = f"repos/{repo}/pulls/{number}/reviews/{review_id}"
    try:
        review = api(endpoint, host)
        if review["state"] != "PENDING":
            return review
        api(endpoint, host, "DELETE")
    except GhError as cleanup:
        raise GhError(
            f"{exc}; cleaning up the pending review {review_id} also failed: {cleanup}"
        ) from None
    return None


def cmd_post(argv):
    dry_run = "--dry-run" in argv
    args = [a for a in argv if a != "--dry-run"]
    if len(args) != 2:
        raise GhError("usage: post <pr_json> <payload_json> [--dry-run]")
    pr, payload = read_json(args[0]), read_json(args[1])
    comments = validate_payload(payload)
    repo, number, host = pr["repo"], pr["number"], pr["host"]

    live = api(f"repos/{repo}/pulls/{number}", host)
    if live["state"] != "open":
        raise GhError(f"PR #{number} is {live['state']}, not open")
    if live["head"]["sha"] != pr["head_sha"]:
        raise GhError(
            f"PR #{number} head moved from {pr['head_sha']} to {live['head']['sha']} since fetch; "
            "the reviewed lines may no longer match"
        )
    viewer = api("user", host)["login"].lower()
    own_pr = viewer == login_of(live.get("user")).lower()
    for r in api_pages(f"repos/{repo}/pulls/{number}/reviews", host):
        if r["state"] == "PENDING" and login_of(r.get("user")).lower() == viewer:
            raise GhError(
                f"you already have a pending review on PR #{number} ({r['html_url']}); "
                "submit or discard it on GitHub, then retry"
            )

    files = {
        f["filename"]: commentable_lines(f["patch"]) if f.get("patch") else set()
        for f in api_pages(f"repos/{repo}/pulls/{number}/files", host)
    }
    placed = {"inline": [], "file": [], "body": []}
    placements = {}
    for c in comments:
        where = place(c, files)
        placed[where].append(c)
        placements[c["id"]] = where

    blocking = any(c["severity"] in BLOCKING for c in comments)
    event = "REQUEST_CHANGES" if blocking and not own_pr else "COMMENT"
    result = {
        "event": event,
        "own_pr": own_pr,
        "counts": {k: len(v) for k, v in placed.items()},
        "placements": placements,
        "review_url": None,
    }
    if dry_run:
        return result

    request = {"commit_id": pr["head_sha"]}
    if placed["inline"]:
        request["comments"] = [
            {
                "path": normalize_path(c["path"]), "line": c["line"], "side": "RIGHT",
                "body": c["body"],
            }
            for c in placed["inline"]
        ]
    pending = api(f"repos/{repo}/pulls/{number}/reviews", host, "POST", request)
    try:
        for c in placed["file"]:
            data = graphql(ADD_FILE_THREAD, {
                "review": pending["node_id"], "path": normalize_path(c["path"]),
                "body": file_comment_body(c),
            }, host)
            if not (data.get("addPullRequestReviewThread") or {}).get("thread"):
                raise GhError(f"GitHub created no file-level thread for comment {c['id']}")
        submitted = api(
            f"repos/{repo}/pulls/{number}/reviews/{pending['id']}/events", host, "POST",
            {"event": event, "body": review_body(payload, placed["body"])},
        )
    except BaseException as exc:
        submitted = settle_failed_review(repo, number, pending["id"], exc, host)
        if submitted is None:
            raise
    result["review_url"] = submitted["html_url"]
    return result


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    commands = {"fetch": cmd_fetch, "checkout": cmd_checkout, "post": cmd_post}
    if len(sys.argv) < 2 or sys.argv[1] not in commands:
        sys.exit(
            f"Usage: {sys.argv[0]} fetch [<pr>] <out_dir> | checkout <pr_json>"
            " | post <pr_json> <payload_json> [--dry-run]"
        )
    try:
        result = commands[sys.argv[1]](sys.argv[2:])
    except GhError as exc:
        sys.exit(f"Error: {exc}")
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
