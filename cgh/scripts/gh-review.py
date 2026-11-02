#!/usr/bin/env python3
"""gh-review.py — read and post the GitHub reviews of the cgh skills.

Usage:
    python3 gh-review.py own <pr_url> <tmp_dir>
    python3 gh-review.py ids <pr_url> <tmp_dir>
    python3 gh-review.py collect <pr_url> <tmp_dir> --kind review|gate
    python3 gh-review.py prior <pr_url> <tmp_dir> --kind review|gate --document <path>
        [--trust]
    python3 gh-review.py draft <pr_url> <tmp_dir> <document> --kind review|gate --lang en|ja
        [--prior-doc <path>]
    python3 gh-review.py wording <pr_url> <json_path>
    python3 gh-review.py comments <pr_url> <tmp_dir>
    python3 gh-review.py raised <pr_url> <tmp_dir> [--discussion]
    python3 gh-review.py participants <pr_url>
    python3 gh-review.py fixes <pr_url> <tmp_dir> <document>
    python3 gh-review.py pushed <pr_url> <fix_commits_json>
    python3 gh-review.py replies <pr_url> <tmp_dir> <document> --lang en|ja
    python3 gh-review.py preview <pr_url> <json_path>
    python3 gh-review.py post <pr_url> <json_path> [--commits <fix_commits_json>]

Every subcommand refuses a pull request whose repository on its host is not a remote of
this clone, before it calls gh.

Nothing this script reads is taken from HTML comments: it removes them, for everyone, from all it
hands on. What a comment means, finding IDs included, is judged from its visible text by whoever
reads the files this script writes. Text it posts goes out as written.

own: writes <tmp_dir>/own/batch-<n>.json and keys.json, {"batches": n}. A batch holds viewer, the
authenticated user, and comments, each comment of that user with visible text, outside pending
reviews and with dismissed reviews included, with its key (review:<id>, thread:<id of the thread's
first comment>, or issue_comment:<id>), location, and text. A batch with a review body or an issue
comment also holds others, other people's review bodies and issue comments, with key, author, and
text, and own_outside, that user's review bodies and issue comments, with key and text.

ids: reads what each batch of own comes to from <tmp_dir>/own/extract-<n>.json,
{"findings": [{"key", "ids"}], "used": [...]}, and names any file that is missing or malformed: a
key must be in that batch's comments, others, or own_outside. It removes a malformed file, so that
a writer run again can write it. Writes <tmp_dir>/finding-ids.json for collect, prior, draft, and
creview's compile-pr-comments.py: comments, the finding IDs by key, and used, every ID in the
extracts.

collect: writes <tmp_dir>/posted/batch-<n>.json and items.json. Each comment of the authenticated
user with visible text, outside pending and dismissed reviews, is an item, except that a reply in
one of that user's own threads stays a reply of that thread's item. Which of them hold findings
of --kind is judged by whoever reads the batches. An item has key (review:<id>, thread:<own id>, or
issue_comment:<id>), earlier_ids, the IDs finding-ids.json gives its comment or thread, location,
text, the replies in its thread, and, when it is in a thread, review_opening, the opening of its
review's visible body, and, for a reply in someone else's thread, thread_root, that thread's first
comment in the form of a reply. A batch also holds viewer and the pull request's author and
assignees, by
whom an answer is weighed, and kind, and, when it holds an item with no thread or kind is gate, the
conversation outside threads, with the key of each entry. items.json also records backed: whether
the user replied in the item's thread, or wrote a review body or an issue comment after it other
than the one holding it.

prior: reads the judgment of each batch from <tmp_dir>/posted/extract-<n>.json, and names any file
that is missing or malformed, removing a malformed one: a key must be an item of that batch. Writes
<tmp_dir>/prior.json with the findings not withdrawn, Info left out since creview's verification
skips it, and, when there are any, <document>: a review document creview's verification reads, with
a Source: pr-comments bullet and a Trust bullet: on at the pull request's head or with --trust,
otherwise off. A finding judged verified has a Verification line, so that the verification checks it
again; one with a reason not to change it has a Won't Fix triage. A comment the judgment left out
holds no finding. A finding keeps the earlier ID the judgment names, its comment's only earlier ID
when it is that comment's only finding, or else takes the next free number; an ID an earlier finding
took counts as none. A finding judged withdrawn that is not backed stays open, printed in demoted.
Stops when there are findings and the working tree holds what the pull request does not: commits
past its head, or uncommitted changes at its head. A finding judged withdrawn rests on that judgment
of the comments alone, with the code unchecked, so it is recorded with its reason: in prior.json's
waived, in a section of <document> no parser reads as a finding, and in the file printed as
waived_document, <tmp_dir>/waived.md, or with no <document>, <document minus .md>-waived.md, which
outlasts <tmp_dir>. Of the comments with earlier IDs and no judgment, prints in unjudged the key and
IDs of those the extracts do not skip, in other_kind the count skipped as another kind, and in
no_problem the key, IDs, and why of those skipped as raising nothing. Also writes
<tmp_dir>/pr-body.json, the pull request's title and description, and prints its path in
pr_body_path.

draft: reads a review document of the pull request, with or without findings, which must
still be at the document's head, and writes <tmp_dir>/draft.json: every finding, numbered after
every ID finding-ids.json lists as used on the pull request, with whether it is selected
and where it goes (inline: a line of the diff; file: a file of the diff; body: anywhere else).
Selected by default: a Will Fix finding other than Info, unless Downgrade leaves it at Minor;
Critical or Major with Downgrade stays a real problem. --prior-doc, which must be at the pull
request's head too,
adds the verification of earlier gate findings. A finding <tmp_dir>/prior.json has as verified
earlier is left out when that still holds, and printed in unchanged. The findings it has as waived
go into the draft's waived, which the preview lists and nothing posts. It also writes
<tmp_dir>/pr-body.json, the pull request's title and description.

wording: merges every wording-*.json next to <json_path> into it: comment_lang, the
language comments go out in, with, per finding, summary (the recommendation for people,
in the preview's language) and post_text, post_summary, post_note (the wording that goes
out, when it differs from the preview's), or, per reply by index, post_body. It changes
nothing else in the file, removes the merged files, so that a later run cannot undo an
edit to the file, and prints the selected findings and the earlier findings with a note
that no wording has covered yet. A wording file it cannot merge is removed and named in the
error, with nothing merged and the other files kept, so that a writer run again replaces it.

comments: writes <tmp_dir>/comments.json, the pull request's comments with their IDs, times,
and viewer, the authenticated user, and <tmp_dir>/pr-body.json.

raised: writes <tmp_dir>/raised/batch-<n>.json, the comments with visible text already on the
pull request by author and place, split into batches with each thread whole. Leaves out dismissed
reviews and their comments, and threads resolved on GitHub. With --discussion, it keeps those
threads, each comment has created_at and, in a thread, review_opening, and a batch also holds
viewer, author, assignees, and conversation, the review bodies and issue comments outside
dismissed reviews, oldest first, in the form of a reply.

participants: prints viewer, the authenticated user, and author and assignees, the pull
request's.

fixes: writes <tmp_dir>/fix-commits.json, the commits on the document's Branch bullet,
or HEAD without one, past the document's head. Prints head_ref, the pull request's branch,
as null when its name holds a character unsafe to show in a command.

pushed: says whether the pull request's head contains the newest of those commits.

replies: writes <tmp_dir>/replies.json from the verification in <document> and the
targets in <tmp_dir>/prior.json, and <tmp_dir>/pr-body.json. A finding verified earlier gets a
reply only when the verification no longer holds; otherwise it is printed in unchanged. A reply
outside threads quotes each finding.

preview: writes <json_path minus .json>-preview.md, what post would send in the preview's
language, and -post.md, the same in the wording that goes out. The JSON file is
draft.json, or a file with a "replies" list of {kind: thread|review|issue_comment|issue,
target_id, finding_ids, body, post_body, selected (default true), verified}. For a draft,
wording_missing holds what wording would print as missing, an empty recommendation or not.
post_differs holds the IDs of what goes out in other wording than the preview's, a reply with no
finding IDs by its kind and target. Findings not posted are listed with Critical and Major first,
marked. A reply shows a heading for each of its finding IDs its text does not hold, such as
**Major M-1**, and one that post would send with a mention names its target in a Mentions line.
For a gate draft, it first waits for GitHub to compute whether the pull request merges, and
records the verdict it shows as previewed_verdict.

post: sends it. A review needs its wording and its head unchanged, is sent as one pending
review, and cannot be sent twice. A gate draft also needs its verdict to match
previewed_verdict. When a call fails, the review's state decides: one that
went out anyway counts as posted, one still pending is deleted, and with the state
unknown the review counts as posted, so that a rerun cannot send it twice. The draft records the
review once it is created. A rerun of a draft that still holds one reads its state first: one that
went out counts as posted, one pending is deleted, one gone is forgotten, and with the state unknown
nothing goes out. Unsent replies need comment_lang, which wording records. A reply to a
review or an issue comment goes out as an issue comment that mentions its author. Replies sent
are marked in the file, so a rerun skips them. A reply is marked as attempted before it goes
out, and a rerun sends an attempted one only when the user has no comment with the same body on
the pull request, in the same thread for a thread reply. --commits refuses a file with findings or a
reply that marks a finding verified, and refuses to send anything until the pull request
contains those commits.

post then reads back what it sent: a reply's body, author, and thread, or a review's state, body,
and number of comments. A difference, or a failure to read, exits 1 and names the URL, with what
was sent marked in the file, so that a rerun does not send it again. A review a failed call still
submitted is not read back. The output's confirmed says how much was.

Prints a JSON object. Exits 1 with an error message on stderr on any failure.
"""

import argparse
import datetime
import glob
import json
import os
import re
import subprocess
import sys
import time
from collections import namedtuple

# A remote URL names its host and ends with the owner and repository, in URL form
# (https://host/o/r.git, ssh://git@host:22/o/r) or scp form (git@host:o/r.git).
# A local path has no host, and a file:// URL is left out by its scheme.
REMOTE_URL_RE = re.compile(
    r"(?:(?P<scheme>[A-Za-z][A-Za-z0-9+.-]*)://(?:[^@/]*@)?(?P<host>[^/@:]+)(?::[0-9]*)?/"
    r"|(?:[^@/:]+@)?(?P<scp_host>[^/@:]{2,}):(?!//))"
    r"(?:.*/)?(?P<owner>[^/]+)/(?P<repo>[^/]+?)(?:\.git)?/*"
)
SSH_SCHEMES = {"ssh", "git+ssh", "ssh+git"}
PR_URL_RE = re.compile(
    r"https://([A-Za-z0-9.-]+(?::[0-9]+)?)/([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+)"
    r"/pull/([0-9]+)(?:[/?#].*)?"
)
PR_BULLET_RE = re.compile(r"- \*\*PR:\*\* (\S+) \(head ([0-9a-f]+), base ([0-9a-f]+)\)")
BRANCH_BULLET_RE = re.compile(r"- \*\*Branch:\*\* ([\w./+@-]+)")
BRANCH_NAME_RE = re.compile(r"\w[\w./+@-]*")
FINDING_ID = r"(?:C|M|mi|I)-[0-9]+"
FINDING_ID_RE = re.compile(FINDING_ID)
HEADING_RE = re.compile(rf"### ({FINDING_ID})\s+[—-]\s+`?([^`]*?)`?(?:\s+\[.*\])?\s*")
FINDING_HEADING_RE = re.compile(rf"###\s+{FINDING_ID}")
METADATA_OPEN_RE = re.compile(rf"<!-- METADATA\(({FINDING_ID})\) -->")
METADATA_RE = re.compile(r"- \*\*(Triage|Estimate|Status|Verification):\*\* (.*)")
LABEL_LINE_RE = re.compile(r"\*\*[^*]+[:：]\*\*\s*")
PLAN_ITEM_RE = re.compile(r"(?:^|\s)\([0-9]+\)\s+")
LOCATION_RE = re.compile(r"(.+?):([0-9]+)(?:[-–,].*)?")
HUNK_RE = re.compile(r"@@ -[0-9]+(?:,[0-9]+)? \+([0-9]+)(?:,[0-9]+)? @@")
# What starts a Markdown block at the beginning of a paragraph of a review document.
BLOCK_START_RE = re.compile(r"#{1,6}(?:\s|$)|[-+*](?:\s|$)|>|`{3}|~{3}|<[A-Za-z/!?]")
# GitHub hides comments outside code: <!--> and <!---> are whole comments; a comment that starts a
# line crosses blank lines and, never closed, hides the rest; one opened mid-line ends at a blank
# line. Scanning from the left keeps code from hiding what a comment opened first, and a comment
# from hiding code; a code span ends at a blank line.
HTML_COMMENT_RE = re.compile(
    r"(?P<code>^ {0,3}(?P<fence>`{3,}(?=[^`\n]*$)|~{3,}).*?"
    r"(?:^ {0,3}(?P=fence)[`~]*[ \t]*\r?$|\Z)"
    r"|(?<![`\\])(?P<span>`+)(?!`)(?:(?!\n[ \t]*\r?\n).)+?(?<!`)(?P=span)(?!`))"
    r"|^ {0,3}<!--(?:-?>|.*?-->|.*\Z)"
    r"|<!--(?:-?>|(?:(?!\n[ \t]*\r?\n).)*?-->)",
    re.S | re.M,
)
PRIOR_VERIFIED = "✅ Verified — Verified at an earlier commit"
POSTED_STATES = ("open", "declined", "verified", "withdrawn")
SKIP_REASONS = ("other_kind", "no_problem")
COMMENT_LANG_RE = re.compile(r"[a-z]{2,3}(?:-[A-Za-z0-9]+)*")
FINDING_WORDING = ("summary", "post_text", "post_summary", "post_note")
SEVERITIES = {"C": "Critical", "M": "Major", "mi": "Minor", "I": "Info"}
BLOCKING = ("Critical", "Major")
ATTENTION = "⚠️"
SCRATCH_EXCLUDES = [":(top,exclude).claude/tmp", ":(top,exclude).claude/worktrees"]
REPLY_KINDS = ("thread", "review", "issue_comment", "issue")
SHORT_SHA = 10
PAGE_SIZE = 100
MAX_PAGES = 100
BODY_LIMIT = 65000
CONTEXT_LIMIT = 1000
QUOTE_LIMIT = 200
OPENING_LIMIT = 300
BATCH_CHARS = 40000
# GraphQL error types that refuse the caller rather than what the call asked for.
CALLER_ERRORS = {"RATE_LIMITED", "FORBIDDEN", "INSUFFICIENT_SCOPES"}
MERGEABLE_TRIES = 5
MERGEABLE_WAIT = 3
PR_QUERY = """
query($owner: String!, $name: String!, $number: Int!) {
  viewer { login }
  repository(owner: $owner, name: $name) {
    pullRequest(number: $number) {
      id number state title body headRefOid headRefName baseRefOid mergeable
      author { login }
      assignees(first: 100) { nodes { login } }
      headRepository { nameWithOwner }
    }
  }
}
"""
ADD_REVIEW = """
mutation($input: AddPullRequestReviewInput!) {
  addPullRequestReview(input: $input) { pullRequestReview { id } }
}
"""
ADD_THREAD = """
mutation($input: AddPullRequestReviewThreadInput!) {
  addPullRequestReviewThread(input: $input) { thread { id } }
}
"""
SUBMIT_REVIEW = """
mutation($input: SubmitPullRequestReviewInput!) {
  submitPullRequestReview(input: $input) { pullRequestReview { url } }
}
"""
REVIEW_STATE = """
query($id: ID!) {
  node(id: $id) { ... on PullRequestReview { state url body comments { totalCount } } }
}
"""
SUBMITTED_STATES = {"COMMENT": "COMMENTED", "REQUEST_CHANGES": "CHANGES_REQUESTED"}
REVIEW_THREADS = """
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
DELETE_REVIEW = """
mutation($input: DeletePullRequestReviewInput!) {
  deletePullRequestReview(input: $input) { clientMutationId }
}
"""
LABELS = {
    "en": {
        "recommendation": "Recommendation",
        "findings": "Findings",
        "out_of_diff": "Findings outside the diff",
        "gate": "Merge gate",
        "conflict": "The pull request has merge conflicts.",
        "prior": "Earlier findings",
        "not_verified": "not verified",
        "waived": "waived by the reviewer",
        "confirmed": "Confirmed at {sha}.",
        "not_resolved": "Not resolved at {sha}.",
        "event": "Event",
        "own_pr": "GitHub refuses Request Changes on your own pull request: sent as Comment.",
        "body": "Review body",
        "inline": "Inline comments",
        "file": "File-level comments",
        "excluded": "Not posted",
        "replies": "Replies",
        "not_triaged": "not triaged",
        "comment_lang": "Comments go out in",
        "withdrawn": "Judged withdrawn from comments, code not checked",
    },
    "ja": {
        "recommendation": "推奨",
        "findings": "指摘",
        "out_of_diff": "差分外の指摘",
        "gate": "マージゲート",
        "conflict": "プルリクエストにマージコンフリクトがあります。",
        "prior": "前回までの指摘",
        "not_verified": "未確認",
        "waived": "レビュアー判断により取り下げ",
        "confirmed": "{sha} で対応を確認しました。",
        "not_resolved": "{sha} では未解決です。",
        "event": "イベント",
        "own_pr": "自分の PR には Request Changes を送れないため、Comment として送ります。",
        "body": "レビュー本文",
        "inline": "インラインコメント",
        "file": "ファイルレベルコメント",
        "excluded": "投稿しない指摘",
        "replies": "返信",
        "not_triaged": "未トリアージ",
        "comment_lang": "投稿する言語",
        "withdrawn": "コメントから取り下げと判定された指摘（コードは未確認）",
    },
}

PullRequest = namedtuple("PullRequest", "host repo owner name number url")


class Error(Exception):
    stdout = ""


class Rejected(Error):
    """GitHub refused what a GraphQL call asked for, so the call changed nothing."""

    def __init__(self, message, types=()):
        super().__init__(message)
        self.types = set(types)


def executable(name):
    # Windows looks a bare program name up in the working directory before PATH.
    if os.name == "nt" and not name.lower().endswith(".exe"):
        name += ".exe"
    for entry in os.environ.get("PATH", "").split(os.pathsep):
        entry = entry.strip('"')
        path = os.path.join(entry, name)
        if os.path.isabs(entry) and os.path.isfile(path) and os.access(path, os.X_OK):
            return path
    return None


def run(cmd, input=None):
    program = executable(cmd[0])
    if program is None:
        raise Error(f"{cmd[0]} not found on PATH")
    proc = subprocess.run([program, *cmd[1:]], input=input, capture_output=True, text=True,
                          encoding="utf-8", errors="replace")
    if proc.returncode != 0:
        error = Error(proc.stderr.strip() or f"{' '.join(cmd[:2])} exited with {proc.returncode}")
        error.stdout = proc.stdout
        raise error
    return proc.stdout


def parse_pr_url(url):
    m = PR_URL_RE.fullmatch(url)
    if not m:
        raise Error(f"not a pull request URL: {url}")
    host, owner, name, number = m.group(1).lower(), m.group(2), m.group(3), int(m.group(4))
    return PullRequest(host, f"{owner}/{name}", owner, name, number,
                       f"https://{host}/{owner}/{name}/pull/{number}")


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


def checked_pr(url):
    pr = parse_pr_url(url)
    if not is_remote(pr.host, pr.owner, pr.name):
        raise Error(f"{pr.repo} on {pr.host} is not a remote of this repository")
    return pr


def rejection(error):
    """The Rejected of a failed gh api graphql, which prints GitHub's answer on stdout. An error
    with no type may not be a refusal: GitHub also answers so when its own execution fails.
    """
    try:
        types = {entry["type"] for entry in json.loads(error.stdout)["errors"]}
    except (ValueError, KeyError, TypeError):
        return None
    return Rejected(str(error), types) if types and not types & CALLER_ERRORS else None


def graphql(pr, query, **variables):
    body = json.dumps({"query": query, "variables": variables})
    try:
        answer = run(["gh", "api", "graphql", "--hostname", pr.host, "--input", "-"], input=body)
    except Error as e:
        raise rejection(e) or e
    return json.loads(answer)["data"]


def rest_get(pr, path):
    return json.loads(run(["gh", "api", "--hostname", pr.host, path]))


def rest_post(pr, path, body):
    return json.loads(run(["gh", "api", "--hostname", pr.host, "-X", "POST", path,
                           "--input", "-"], input=json.dumps(body)))


def rest_pages(pr, path):
    items = []
    for page in range(1, MAX_PAGES + 1):
        batch = rest_get(pr, f"{path}?per_page={PAGE_SIZE}&page={page}")
        items.extend(batch)
        if len(batch) < PAGE_SIZE:
            break
    return items


def view_pr(pr, require_open=True):
    data = graphql(pr, PR_QUERY, owner=pr.owner, name=pr.name, number=pr.number)
    view = (data.get("repository") or {}).get("pullRequest")
    if not view or view.get("number") != pr.number:
        raise Error(f"gh did not return PR #{pr.number}")
    if require_open and view.get("state") != "OPEN":
        raise Error(f"PR #{pr.number} is not open")
    view["viewer"] = data["viewer"]["login"]
    return view


def participants(view):
    assignees = (view.get("assignees") or {}).get("nodes") or []
    return {"viewer": view["viewer"], "author": (view.get("author") or {}).get("login"),
            "assignees": [a["login"] for a in assignees]}


def settled_view(pr):
    """The pull request once GitHub, which computes mergeable lazily, has settled it."""
    for attempt in range(MERGEABLE_TRIES):
        if attempt:
            time.sleep(MERGEABLE_WAIT)
        view = view_pr(pr)
        if view.get("mergeable") != "UNKNOWN":
            return view
    raise Error(f"GitHub has not computed whether PR #{pr.number} merges; try again shortly")


def view_for_draft(pr, draft):
    return settled_view(pr) if draft.get("kind") == "gate" else view_pr(pr)


def write_json(path, data):
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")


def read_json(path):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError) as e:
        raise Error(f"cannot read {path}: {e}") from None


def severity_of(fid):
    return SEVERITIES[fid.rpartition("-")[0]]


def has_label(value, label):
    """Whether a metadata value starts with the label, past the emoji and spaces before it."""
    return re.match(rf"[^\w\s]*\s*{re.escape(label)}\b", value) is not None


def labels_for(lang):
    return LABELS.get(lang, LABELS["en"])


def write_pr_body(tmp_dir, view):
    path = os.path.join(tmp_dir, "pr-body.json")
    write_json(path, {"title": without_comments(view.get("title") or ""),
                      "body": without_comments(view.get("body") or "")})
    return path


def diff_lines(patch):
    """The line numbers of the new file that a pull request comment can anchor at."""
    lines, current = set(), None
    for line in (patch or "").split("\n"):
        hunk = HUNK_RE.match(line)
        if hunk:
            current = int(hunk.group(1))
        elif current is not None and not line.startswith("-") and not line.startswith("\\"):
            lines.add(current)
            current += 1
    return lines


def split_location(location):
    m = LOCATION_RE.fullmatch(location)
    path, line = (m.group(1), int(m.group(2))) if m else (location, None)
    path = path.replace("\\", "/")
    return (path[2:] if path.startswith("./") else path), line


def parse_document(path):
    try:
        with open(path, encoding="utf-8") as f:
            lines = [line.rstrip() for line in f.read().split("\n")]
    except OSError as e:
        raise Error(f"cannot read {path}: {e}") from None
    header, findings, current, state = {}, [], None, None
    for index, line in enumerate(lines):
        if not findings and current is None:
            bullet = PR_BULLET_RE.fullmatch(line)
            if bullet:
                header.update(url=bullet.group(1), head_sha=bullet.group(2),
                              merge_base=bullet.group(3))
            branch = BRANCH_BULLET_RE.fullmatch(line)
            if branch:
                header["branch"] = branch.group(1)
        if line.startswith("## Orphan") and state != "text":
            break
        # A finding's text runs to its metadata block, so a heading before the block is quoted.
        quoted = state == "text" and f"<!-- METADATA({current['id']}) -->" in lines[index + 1:]
        heading = None if quoted else HEADING_RE.fullmatch(line)
        if not heading and not quoted and FINDING_HEADING_RE.match(line):
            raise Error(f"{path} has a malformed finding heading: {line}")
        opened = METADATA_OPEN_RE.fullmatch(line)
        if opened and (current is None or opened.group(1) != current["id"]):
            raise Error(f"{path} has a metadata block under no heading of its ID: {line}")
        if heading:
            current = {"id": heading.group(1), "severity": severity_of(heading.group(1)),
                       "location": heading.group(2).strip(), "text": [], "metadata": {}}
            findings.append(current)
            state = "text"
        elif current is None:
            continue
        elif line == f"<!-- METADATA({current['id']}) -->":
            state = "metadata"
        elif line == f"<!-- /METADATA({current['id']}) -->":
            state = None
        elif state == "metadata":
            field = METADATA_RE.fullmatch(line)
            if field:
                current["metadata"][field.group(1)] = field.group(2)
        elif state == "text":
            current["text"].append(line)
    for finding in findings:
        finding["text"] = finding_text(finding["text"])
    return header, findings


def finding_text(lines):
    while lines and (not lines[0].strip() or lines[0].startswith("- **")):
        lines = lines[1:]
    if lines:
        lines = [LABEL_LINE_RE.sub("", lines[0], count=1)] + lines[1:]
    return "\n".join(lines).strip()


def recommendation(finding):
    estimate = finding["metadata"].get("Estimate", "")
    if not estimate:
        return []
    _, marker, plan = estimate.partition(" — Plan: ")
    if marker:
        return [item.strip() for item in PLAN_ITEM_RE.split(plan) if item.strip()]
    if has_label(estimate, "Downgrade"):
        return [estimate.rsplit(" — ", 1)[-1].strip()]
    return []


def default_selection(finding, labels):
    """Whether a finding goes out by default and, when not, why."""
    meta = finding["metadata"]
    triage, estimate = meta.get("Triage", ""), meta.get("Estimate", "")
    if finding["severity"] == "Info":
        return False, "Info"
    if not has_label(triage, "Will Fix"):
        return False, triage.rsplit(" — ", 1)[-1].strip() or labels["not_triaged"]
    if has_label(estimate, "Downgrade") and finding["severity"] not in BLOCKING:
        return False, estimate.rsplit(" — ", 1)[-1].strip()
    return True, None


def finding_block(finding, lang, with_location):
    labels = labels_for(lang)
    location = finding["location"]
    head = f"**{severity_of(finding['id'])} {finding['id']}**"
    if with_location and location != "PR":
        head += f" `{location.replace('`', '')}`"
    parts = [head, "", finding["text"]]
    items = finding.get("recommendation") or []
    if items:
        parts += ["", f"**{labels['recommendation']}**", ""]
        if len(items) == 1:
            parts.append(items[0])
        else:
            parts += [f"{n}. {item}" for n, item in enumerate(items, 1)]
    return "\n".join(parts)


def comment_view(finding, post):
    """The finding as the preview (post False) or the pull request (post True) shows it."""
    text = (post and finding.get("post_text")) or finding["text"]
    summary = (post and finding.get("post_summary")) or finding.get("summary")
    return {**finding, "text": text,
            "recommendation": [summary] if summary else finding.get("recommendation") or []}


def comment_author(comment):
    return (comment.get("user") or {}).get("login") or "ghost"


def without_comments(text):
    """The text with HTML comments removed, including those the removal itself would form."""
    while True:
        stripped = HTML_COMMENT_RE.sub(lambda m: m.group("code") or "", text)
        if stripped == text:
            return text
        text = stripped


def visible_body(comment):
    return without_comments(comment.get("body") or "").strip()


def comment_time(entry):
    return entry.get("created_at") or entry.get("submitted_at") or ""


def by_time(entries):
    return sorted(entries, key=comment_time)


def batched(units, size_of):
    batches, size = [[]], 0
    for unit in units:
        length = size_of(unit)
        if batches[-1] and size + length > BATCH_CHARS:
            batches.append([])
            size = 0
        batches[-1].append(unit)
        size += length
    return batches if batches[0] else []


def visible_comments(pr):
    """Reviews, review comments, and issue comments, without those of pending reviews."""
    reviews = rest_pages(pr, f"repos/{pr.repo}/pulls/{pr.number}/reviews")
    comments = rest_pages(pr, f"repos/{pr.repo}/pulls/{pr.number}/comments")
    issue_comments = rest_pages(pr, f"repos/{pr.repo}/issues/{pr.number}/comments")
    pending = {r.get("id") for r in reviews if r.get("state") == "PENDING"}
    return ([r for r in reviews if r.get("id") not in pending],
            [c for c in comments if c.get("pull_request_review_id") not in pending],
            issue_comments)


def cmd_own(pr_url, tmp_dir):
    pr = checked_pr(pr_url)
    viewer = view_pr(pr, require_open=False)["viewer"]
    reviews, comments, issue_comments = visible_comments(pr)
    in_reviews = [(f"review:{r.get('id')}", r) for r in reviews]
    in_threads = [(f"thread:{c.get('in_reply_to_id') or c.get('id')}", c) for c in comments]
    in_issue = [(f"issue_comment:{c.get('id')}", c) for c in issue_comments]
    own = [{"key": key, "location": comment_place(entry) if key.startswith("thread:") else "PR",
            "text": visible_body(entry)}
           for key, entry in [*in_reviews, *in_threads, *in_issue]
           if comment_author(entry) == viewer and visible_body(entry)]
    others = [{"key": key, "author": comment_author(entry), "text": visible_body(entry)}
              for key, entry in [*in_reviews, *in_issue]
              if comment_author(entry) != viewer and visible_body(entry)]
    own_outside = [{"key": c["key"], "text": c["text"]} for c in own
                   if not c["key"].startswith("thread:")]
    batches = batched(own, lambda c: len(c["text"]))
    directory = os.path.join(tmp_dir, "own")
    os.makedirs(directory, exist_ok=True)
    write_json(os.path.join(directory, "keys.json"), {"batches": len(batches)})
    for n, batch in enumerate(batches, 1):
        data = {"viewer": viewer, "comments": batch}
        if any(not c["key"].startswith("thread:") for c in batch):
            data["others"] = others
            data["own_outside"] = own_outside
        write_json(os.path.join(directory, f"batch-{n}.json"), data)
    return {"directory": directory, "batches": len(batches)}


def discard(path):
    """Removes a malformed file, which a writer run again could not overwrite unread."""
    try:
        os.remove(path)
    except OSError:
        pass


def read_own_extracts(directory, batches):
    """The IDs by key and the IDs used in each batch's extract, naming any file that is missing or
    malformed.
    """
    comments, used, bad = {}, set(), []
    for n in range(1, batches + 1):
        name = os.path.join(directory, f"extract-{n}.json")
        try:
            batch = read_json(os.path.join(directory, f"batch-{n}.json"))
            keys = {c["key"] for group in ("comments", "others", "own_outside")
                    for c in batch.get(group, [])}
            extract = read_json(name)
            if not finding_ids_only(extract["used"]):
                raise ValueError(extract["used"])
            used.update(extract["used"])
            for entry in extract["findings"]:
                if entry["key"] not in keys or not finding_ids_only(entry["ids"]):
                    raise ValueError(entry)
                used.update(entry["ids"])
                if entry["ids"]:
                    held = comments.setdefault(entry["key"], [])
                    held.extend(fid for fid in entry["ids"] if fid not in held)
        except (Error, OSError, AttributeError, KeyError, TypeError, ValueError):
            discard(name)
            bad.append(name)
    if bad:
        raise Error(f"missing or malformed: {', '.join(bad)}")
    return comments, used


def cmd_ids(pr_url, tmp_dir):
    checked_pr(pr_url)
    directory = os.path.join(tmp_dir, "own")
    try:
        batches = read_json(os.path.join(directory, "keys.json"))["batches"]
    except (Error, KeyError, TypeError):
        raise Error(f"run own first: no comments listed in {directory}") from None
    comments, used = read_own_extracts(directory, batches)
    path = os.path.join(tmp_dir, "finding-ids.json")
    write_json(path, {"comments": comments, "used": sorted(used)})
    return {"path": path, "comments": len(comments)}


def known_ids(tmp_dir):
    """The IDs by key and the IDs used, from what ids wrote."""
    path = os.path.join(tmp_dir, "finding-ids.json")
    try:
        known = read_json(path)
        comments, used = known["comments"], known["used"]
        if not finding_ids_only(used) or not all(map(finding_ids_only, comments.values())):
            raise ValueError(known)
    except (Error, AttributeError, KeyError, TypeError, ValueError):
        raise Error(f"run ids first: no finding IDs in {path}") from None
    return comments, used


def spoken(comment, viewer):
    return {"author": comment_author(comment), "own": comment_author(comment) == viewer,
            "created_at": comment.get("created_at") or comment.get("submitted_at"),
            "text": visible_body(comment)}


def own_item(comment, target, key, location, replies, earlier_ids, holder):
    """A comment of the viewer, with `holder` the key of the review or comment that holds it."""
    return {"key": key, "id": None, "severity": None, "location": location,
            "text": visible_body(comment), "recommendation": [], "target": target,
            "replies": replies, "earlier_ids": earlier_ids, "holder": holder,
            "created_at": comment_time(comment)}


def comment_place(comment):
    line = comment.get("line") or comment.get("original_line")
    return f"{comment.get('path')}:{line}" if line else comment.get("path")


def is_backed(item, own_outside):
    """Whether the viewer wrote anything that could withdraw the item, beyond the item itself:
    `own_outside` holds the key and time of each of the viewer's review bodies and issue comments.
    """
    if any(reply["own"] for reply in item["replies"]):
        return True
    return bool(item["created_at"]) and any(
        key != item["holder"] and when > item["created_at"] for key, when in own_outside)


def posted_items(pr, viewer, earlier):
    """The viewer's comments with the replies in their threads, the conversation outside threads,
    and `earlier`, the finding IDs by key, on each comment.
    """
    reviews, comments, issue_comments = visible_comments(pr)
    dismissed = {r.get("id") for r in reviews if r.get("state") == "DISMISSED"}
    live = [c for c in comments if c.get("pull_request_review_id") not in dismissed]
    standing = [r for r in reviews if r.get("id") not in dismissed]
    review_of = {r.get("id"): r for r in reviews}
    threads = {}
    for comment in by_time(c for c in live if c.get("in_reply_to_id")):
        threads.setdefault(comment["in_reply_to_id"], []).append(comment)

    def own(entry):
        return comment_author(entry) == viewer and visible_body(entry)

    own_roots = {c.get("id") for c in live if own(c) and not c.get("in_reply_to_id")}
    by_id = {c.get("id"): c for c in live}
    items = []
    for review in filter(own, standing):
        key = f"review:{review.get('id')}"
        items.append(own_item(review, {"kind": "review", "id": review.get("id")}, key, "PR", [],
                              earlier.get(key, []), key))
    for comment in filter(own, live):
        cid, root = comment.get("id"), comment.get("in_reply_to_id")
        if root in own_roots:
            continue
        rid = comment.get("pull_request_review_id")
        replies = [spoken(c, viewer) for c in threads.get(root or cid, []) if c is not comment]
        item = own_item(comment, {"kind": "thread", "id": cid}, f"thread:{cid}",
                        comment_place(comment), replies, earlier.get(f"thread:{root or cid}", []),
                        f"review:{rid}")
        item["review_opening"] = visible_body(review_of.get(rid, {}))[:OPENING_LIMIT]
        if root in by_id:
            item["thread_root"] = spoken(by_id[root], viewer)
        items.append(item)
    for comment in filter(own, issue_comments):
        cid, key = comment.get("id"), f"issue_comment:{comment.get('id')}"
        items.append(own_item(comment, {"kind": "issue_comment", "id": cid}, key, "PR", [],
                              earlier.get(key, []), key))
    outside = [{"key": f"review:{r.get('id')}", **spoken(r, viewer)} for r in reviews]
    outside += [{"key": f"issue_comment:{c.get('id')}", **spoken(c, viewer)}
                for c in issue_comments]
    own_outside = [(f"review:{r.get('id')}", comment_time(r)) for r in filter(own, standing)]
    own_outside += [(f"issue_comment:{c.get('id')}", comment_time(c))
                    for c in filter(own, issue_comments)]
    for item in items:
        item["backed"] = is_backed(item, own_outside)
    return items, by_time(entry for entry in outside if entry["text"])


def cmd_collect(pr_url, tmp_dir, kind):
    pr = checked_pr(pr_url)
    earlier, _ = known_ids(tmp_dir)
    people = participants(view_pr(pr, require_open=False))
    items, outside = posted_items(pr, people["viewer"], earlier)
    directory = os.path.join(tmp_dir, "posted")
    os.makedirs(directory, exist_ok=True)
    batches = batched(items, lambda i: (len(i["text"]) + sum(len(r["text"]) for r in i["replies"])
                                        + len(i.get("thread_root", {}).get("text", ""))))
    write_json(os.path.join(directory, "items.json"), {"items": items, "batches": len(batches)})
    shown = ("key", "earlier_ids", "location", "text", "replies", "review_opening", "thread_root")
    for n, batch in enumerate(batches, 1):
        data = {**people, "kind": kind,
                "items": [{k: item[k] for k in shown if k in item} for item in batch]}
        if kind == "gate" or any(item["target"]["kind"] != "thread" for item in batch):
            data["conversation"] = outside
        write_json(os.path.join(directory, f"batch-{n}.json"), data)
    return {"directory": directory, "batches": len(batches), "items": len(items)}


def read_judgments(directory, batches, items):
    """Each batch's judgment by item key and its skips by key, naming any file that is missing or
    malformed.
    """
    keys = {item["key"]: item for item in items}
    judged, skipped, bad = {}, {}, []
    for n in range(1, batches + 1):
        name = os.path.join(directory, f"extract-{n}.json")
        try:
            batch = read_json(os.path.join(directory, f"batch-{n}.json"))
            own_keys = {listed["key"] for listed in batch["items"]}
            extract = read_json(name)
            entries = extract["findings"]
            for skip in extract.get("skipped", []):
                if (skip["key"] not in own_keys or skip["reason"] not in SKIP_REASONS
                        or not isinstance(skip.get("why"), (str, type(None)))):
                    raise ValueError(skip)
                skipped[skip["key"]] = skip
            for entry in entries:
                if entry["key"] not in own_keys:
                    raise ValueError(entry)
                item = keys[entry["key"]]
                if entry["state"] not in POSTED_STATES:
                    raise ValueError(entry["state"])
                if any(not isinstance(entry.get(field), (str, type(None)))
                       for field in ("reason", "context", "location", "recommendation")):
                    raise ValueError(entry)
                siblings = judged.setdefault(entry["key"], [])
                fid = entry.get("id")
                if (entry.get("severity") not in SEVERITIES.values()
                        or not isinstance(entry.get("text"), str)
                        or not entry["text"].strip()
                        or (fid is not None and fid not in item["earlier_ids"])
                        or (fid is not None and fid in [e.get("id") for e in siblings])):
                    raise ValueError(entry)
                siblings.append(entry)
        except (Error, OSError, KeyError, TypeError, ValueError):
            discard(name)
            bad.append(name)
    if bad:
        raise Error(f"missing or malformed: {', '.join(bad)}")
    return judged, skipped


def settled_findings(items, judged, used):
    """The findings with their judgment. Each takes the earlier ID the judgment names, the only
    earlier ID when its comment holds one finding, or else the next free number. An ID an earlier
    finding took counts as none. An ID gives the severity, which its prefix carries.
    """
    numbers = next_numbers(used)
    prefixes = {name: prefix for prefix, name in SEVERITIES.items()}
    findings, taken = [], set()
    for item in items:
        entries = judged.get(item["key"], [])
        earlier = item["earlier_ids"]
        for entry in entries:
            fid = entry.get("id")
            if fid in taken:
                fid = None
            if not fid and len(entries) == 1 and len(earlier) == 1 and earlier[0] not in taken:
                fid = earlier[0]
            if not fid:
                prefix = prefixes[entry["severity"]]
                numbers[prefix] = numbers.get(prefix, 0) + 1
                fid = f"{prefix}-{numbers[prefix]}"
            taken.add(fid)
            recommended = (entry.get("recommendation") or "").strip()
            findings.append({
                **item, "id": fid, "severity": severity_of(fid), "text": entry["text"],
                "location": entry.get("location") or item["location"],
                "state": entry["state"], "reason": entry.get("reason"),
                "context": entry.get("context"),
                "recommendation": [recommended] if recommended else []})
    for finding in findings:
        finding["verified"] = finding["state"] == "verified"
        if finding["state"] == "declined" and not finding.get("reason"):
            finding["state"] = "open"
        if finding["state"] not in ("declined", "verified", "withdrawn"):
            finding.pop("reason", None)
    return findings


def next_numbers(ids):
    numbers = {}
    for fid in ids:
        prefix, _, n = fid.rpartition("-")
        numbers[prefix] = max(numbers.get(prefix, 0), int(n))
    return numbers


def local_state(head_sha):
    head = run(["git", "rev-parse", "HEAD"]).strip()
    if head == head_sha:
        return "head"
    try:
        run(["git", "merge-base", "--is-ancestor", head_sha, "HEAD"])
    except Error:
        return "elsewhere"
    return "ahead"


def document_text(text):
    text = " ".join(text.split()).replace("<!--", "&lt;!--")
    return "\\" + text if BLOCK_START_RE.match(text) else text


def document_location(location):
    return " ".join(location.split()).replace("`", "").replace("<!--", "&lt;!--")


def withdrawn_line(finding):
    line = (f"- **{finding['id']}** `{document_location(finding['location'])}`: "
            f"{document_text(finding['text'])}")
    return f"{line} — {document_text(finding['reason'])}" if finding.get("reason") else line


def write_prior_document(path, pr, view, merge_base, viewer, findings, state, trust, waived):
    branch = None
    if state == "head":
        name = run(["git", "branch", "--show-current"]).strip()
        branch = name if BRANCH_NAME_RE.fullmatch(name) else None
    lines = ["# Posted Review Findings", "",
             f"- **Date:** {datetime.date.today().isoformat()}",
             f"- **PR:** {pr.url} (head {view['headRefOid']}, base {merge_base})"]
    if branch:
        lines.append(f"- **Branch:** {branch}")
    lines += [f"- **Trust:** {'on' if trust or state == 'head' else 'off'}",
              "- **Source:** pr-comments",
              f"- **Scope:** Findings posted to pull request #{pr.number}",
              f"- **Reviewers:** {viewer}", ""]
    for severity in ("Critical", "Major", "Minor", "Info"):
        lines += [f"## {severity}", ""]
        for f in (f for f in findings if f["severity"] == severity):
            text = document_text(f["text"])
            if f["recommendation"]:
                plan = " ".join(f"({n}) {item}" for n, item in enumerate(f["recommendation"], 1))
                text += " " + document_text(f"Recommended fix: {plan}")
            if f.get("context"):
                text += " " + document_text(f"Conversation: {f['context'][:CONTEXT_LIMIT]}")
            location = document_location(f["location"])
            lines += [f"### {f['id']} — `{location}`", "", f"- **Reviewers:** {viewer}", "",
                      "**Finding:**", "", text, "", f"<!-- METADATA({f['id']}) -->"]
            if f.get("reason"):
                lines.append(f"- **Triage:** 🚫 Won't Fix — {document_text(f['reason'])}")
            if f["verified"]:
                lines.append(f"- **Verification:** {PRIOR_VERIFIED}")
            lines += [f"<!-- /METADATA({f['id']}) -->", "", "---", ""]
    if waived:
        lines += ["## Withdrawn Findings", "",
                  "Judged withdrawn from the viewer's comments; the code was not checked.", ""]
        lines += [withdrawn_line(f) for f in waived] + [""]
    with open(path, "w", encoding="utf-8", newline="\n") as out:
        out.write("\n".join(lines))


def write_waived_document(path, pr, findings):
    lines = ["# Waived Findings", "",
             f"These findings of pull request #{pr.number} were judged withdrawn from the viewer's "
             "comments; the code was not checked.", ""]
    for f in findings:
        lines += [f"## {f['id']} — `{document_location(f['location'])}`", "",
                  document_text(f["text"]), ""]
        if f.get("reason"):
            lines += [f"Basis: {document_text(f['reason'])}", ""]
    with open(path, "w", encoding="utf-8", newline="\n") as out:
        out.write("\n".join(lines))


def merge_base_of(pr, view):
    compare = rest_get(
        pr, f"repos/{pr.repo}/compare/{view['baseRefOid']}...{view['headRefOid']}")
    return (compare.get("merge_base_commit") or {}).get("sha")


def cmd_prior(pr_url, tmp_dir, kind, document, trust=False):
    pr = checked_pr(pr_url)
    view = view_pr(pr)
    directory = os.path.join(tmp_dir, "posted")
    try:
        collected = read_json(os.path.join(directory, "items.json"))
    except (Error, OSError):
        raise Error(f"run collect first: no findings collected in {directory}") from None
    judged, skipped = read_judgments(directory, collected["batches"], collected["items"])
    unsettled = [i for i in collected["items"] if i["earlier_ids"] and i["key"] not in judged]
    skip_of = [(i, skipped.get(i["key"], {})) for i in unsettled]
    settled = settled_findings(collected["items"], judged, known_ids(tmp_dir)[1])
    demoted = [f for f in settled if f["state"] == "withdrawn" and not f["backed"]]
    for finding in demoted:
        finding["state"] = "open"
        finding.pop("reason", None)
    waived = [f for f in settled if f["state"] == "withdrawn"]
    findings = [f for f in settled if f["state"] != "withdrawn" and f["severity"] != "Info"]
    write_json(os.path.join(tmp_dir, "prior.json"), {
        "findings": findings,
        "waived": [{k: f.get(k) for k in ("id", "location", "text", "reason")} for f in waived]})
    state = local_state(view["headRefOid"])
    written = None
    if findings:
        if state == "ahead":
            raise Error("HEAD holds commits the pull request does not have; push them, or run "
                        "this from a checkout at the pull request's head")
        if state == "head" and run(["git", "status", "--porcelain", "--untracked-files=no", "--",
                                    *SCRATCH_EXCLUDES]).strip():
            raise Error("the working tree is at the pull request's head but has uncommitted "
                        "changes; commit or stash them first")
        write_prior_document(document, pr, view, merge_base_of(pr, view), view["viewer"],
                             findings, state, trust, waived)
        written = document
    waived_document = None
    if waived:
        waived_document = (os.path.join(tmp_dir, "waived.md") if written
                           else f"{os.path.splitext(document)[0]}-waived.md")
        write_waived_document(waived_document, pr, waived)
    return {
        "url": pr.url, "number": pr.number, "head_sha": view["headRefOid"],
        "pr_body_path": write_pr_body(tmp_dir, view),
        "open": [f["id"] for f in findings if not f["verified"]],
        "verified": [f["id"] for f in findings if f["verified"]],
        "waived": [f["id"] for f in waived], "demoted": [f["id"] for f in demoted],
        "document": written, "waived_document": waived_document,
        "unjudged": [{"key": i["key"], "ids": i["earlier_ids"]} for i, skip in skip_of if not skip],
        "other_kind": sum(skip.get("reason") == "other_kind" for _, skip in skip_of),
        "no_problem": [{"key": i["key"], "ids": i["earlier_ids"], "why": skip.get("why")}
                       for i, skip in skip_of if skip.get("reason") == "no_problem"],
    }


def changed_files(pr):
    return {f["filename"]: diff_lines(f.get("patch"))
            for f in rest_pages(pr, f"repos/{pr.repo}/pulls/{pr.number}/files")}


def placement(location, files):
    path, line = split_location(location)
    if path not in files:
        return "body"
    return "inline" if line in files[path] else "file"


def checked_document(pr, document):
    header, findings = parse_document(document)
    if (header.get("url") or "").casefold() != pr.url.casefold():
        raise Error(f"{document} is not a review document of {pr.url}")
    return header, findings


def earlier_verified(tmp_dir):
    path = os.path.join(tmp_dir, "prior.json")
    if not os.path.exists(path):
        return set()
    return {f["id"] for f in read_json(path)["findings"] if f.get("verified")}


def earlier_waived(tmp_dir):
    path = os.path.join(tmp_dir, "prior.json")
    return read_json(path).get("waived", []) if os.path.exists(path) else []


def prior_states(pr, prior_doc, head, earlier):
    if not prior_doc:
        return [], []
    header, findings = checked_document(pr, prior_doc)
    if header.get("head_sha") != head:
        raise Error(f"{prior_doc} was verified at {header.get('head_sha')}, but the pull request "
                    f"is at {head}; run /cgh:gate again")
    prior, unchanged = [], []
    for f in findings:
        verification = f["metadata"].get("Verification", "")
        checked = verification != PRIOR_VERIFIED
        verified = checked and has_label(verification, "Verified")
        if verified and f["id"] in earlier:
            unchanged.append(f["id"])
            continue
        prior.append({"id": f["id"], "severity": f["severity"],
                      "state": "verified" if verified else "open",
                      "note": verification.partition(" — ")[2].strip() if checked else ""})
    return prior, unchanged


def cmd_draft(pr_url, tmp_dir, document, kind, lang, prior_doc):
    pr = checked_pr(pr_url)
    header, findings = checked_document(pr, document)
    view = view_pr(pr)
    if view["headRefOid"] != header.get("head_sha"):
        raise Error(f"the pull request moved past the reviewed head {header.get('head_sha')} "
                    f"to {view['headRefOid']}; run the skill again")
    _, used = known_ids(tmp_dir)
    prior, unchanged = prior_states(pr, prior_doc, view["headRefOid"], earlier_verified(tmp_dir))
    numbers = next_numbers([*used, *(p["id"] for p in prior)])
    files = changed_files(pr)
    entries = []
    labels = labels_for(lang)
    for finding in findings:
        prefix, _, n = finding["id"].rpartition("-")
        base = numbers.get(prefix, 0)
        selected, reason = default_selection(finding, labels)
        entries.append({
            "id": f"{prefix}-{base + int(n)}", "doc_id": finding["id"],
            "severity": finding["severity"], "location": finding["location"],
            "placement": placement(finding["location"], files), "selected": selected,
            "excluded_reason": reason, "text": finding["text"],
            "recommendation": recommendation(finding),
        })
    write_json(os.path.join(tmp_dir, "draft.json"), {
        "url": pr.url, "head_sha": view["headRefOid"], "kind": kind, "lang": lang,
        "findings": entries, "prior": prior, "waived": earlier_waived(tmp_dir), "posted": False,
    })
    selected = [e for e in entries if e["selected"]]
    return {
        "path": os.path.join(tmp_dir, "draft.json"), "total": len(entries),
        "selected": len(selected),
        "selected_ids": [e["id"] for e in selected],
        "prior_ids": [p["id"] for p in prior], "unchanged": unchanged,
        "pr_body_path": write_pr_body(tmp_dir, view),
        "by_placement": {p: sum(e["placement"] == p for e in selected)
                         for p in ("inline", "file", "body")},
    }


def review_plan(draft, view):
    selected = [f for f in draft["findings"] if f["selected"]]
    open_prior = [p for p in draft["prior"]
                  if p["state"] == "open" and p["severity"] in BLOCKING]
    conflict = draft["kind"] == "gate" and view.get("mergeable") == "CONFLICTING"
    blocking = any(f["severity"] in BLOCKING for f in selected)
    verdict = None
    if draft["kind"] == "gate":
        verdict = "BLOCK" if blocking or open_prior or conflict else "PASS"
    own_pr = (view.get("author") or {}).get("login") == view["viewer"]
    wanted = "REQUEST_CHANGES" if blocking or verdict == "BLOCK" else "COMMENT"
    return {
        "event": "COMMENT" if own_pr else wanted, "wanted": wanted, "verdict": verdict,
        "own_pr": own_pr, "conflict": conflict, "selected": selected,
    }


def wording_missing(draft):
    missing = [f["id"] for f in draft["findings"] if f["selected"] and not f.get("worded")]
    return missing + [p["id"] for p in draft["prior"] if p["note"] and not p.get("worded")]


def review_body(draft, plan, body_findings, post):
    lang = draft.get("comment_lang", draft["lang"]) if post else draft["lang"]
    labels = labels_for(lang)
    lines = []
    short = draft["head_sha"][:SHORT_SHA]
    if plan["verdict"]:
        lines += [f"## {labels['gate']}: {plan['verdict']}", "", short, ""]
        if plan["conflict"]:
            lines += [labels["conflict"], ""]
    counts = [f"{name} {sum(f['severity'] == name for f in plan['selected'])}"
              for name in ("Critical", "Major", "Minor", "Info")
              if any(f["severity"] == name for f in plan["selected"])]
    if counts and not plan["verdict"]:
        lines += [f"{labels['findings']}: {' / '.join(counts)} ({short})", ""]
    elif counts:
        lines += [f"{labels['findings']}: {' / '.join(counts)}", ""]
    if draft["prior"]:
        lines += [f"### {labels['prior']}", ""]
        for p in draft["prior"]:
            icon = {"verified": "✅", "waived": "➖"}.get(p["state"], "💬")
            note = {"waived": labels["waived"]}.get(p["state"])
            note = note or (post and p.get("post_note")) or p["note"]
            lines.append(f"- {icon} **{p['id']}**: {note or labels['not_verified']}")
        lines.append("")
    if body_findings:
        lines += [f"### {labels['out_of_diff']}", ""]
        for f in body_findings:
            lines += [finding_block(comment_view(f, post), lang, True), ""]
    return "\n".join(lines).strip()


def checked_size(text, what):
    if len(text) > BODY_LIMIT:
        raise Error(f"{what} is {len(text)} characters, past GitHub's limit; select fewer "
                    "findings or shorten them")
    return text


def preview_review(draft, view, post):
    plan = review_plan(draft, view)
    lang = draft.get("comment_lang", draft["lang"]) if post else draft["lang"]
    labels = labels_for(lang)
    by_place = {p: [f for f in plan["selected"] if f["placement"] == p]
                for p in ("inline", "file", "body")}
    lines = []
    if plan["verdict"]:
        lines += [f"**{labels['gate']}: {plan['verdict']}**", ""]
    lines += [f"**{labels['event']}:** {plan['event']}", ""]
    if plan["own_pr"] and plan["wanted"] != plan["event"]:
        lines += [labels["own_pr"], ""]
    if draft.get("comment_lang"):
        lines += [f"**{labels['comment_lang']}:** {draft['comment_lang']}", ""]
    lines += [f"## {labels['body']}", "", review_body(draft, plan, by_place["body"], post), ""]
    for place, title in (("inline", labels["inline"]), ("file", labels["file"])):
        if by_place[place]:
            lines += [f"## {title}", ""]
            for f in by_place[place]:
                block = finding_block(comment_view(f, post), lang, place == "file")
                lines += [f"`{f['location']}`", "", block, ""]
    excluded = [f for f in draft["findings"] if not f["selected"]]
    if excluded and not post:
        lines += [f"## {labels['excluded']}", ""]
        for blocking in (True, False):
            mark = f"{ATTENTION} " if blocking else ""
            lines += [f"- {mark}**{f['id']}** `{f['location']}`: {f['excluded_reason'] or ''}"
                      for f in excluded if (f["severity"] in BLOCKING) == blocking]
    if draft.get("waived") and not post:
        lines += ["", f"## {labels['withdrawn']}", ""]
        lines += [withdrawn_line(f) for f in draft["waived"]]
    return "\n".join(lines) + "\n", {
        "event": plan["event"], "verdict": plan["verdict"], "own_pr": plan["own_pr"],
        "selected": len(plan["selected"]), "comment_lang": draft.get("comment_lang"),
        "wording_missing": wording_missing(draft),
    }


def finding_ids_only(value):
    return isinstance(value, list) and all(
        isinstance(fid, str) and FINDING_ID_RE.fullmatch(fid) for fid in value)


def validated_replies(data):
    replies = data.get("replies")
    if not isinstance(replies, list):
        raise Error("the replies file has no replies list")
    for entry in replies:
        if not isinstance(entry, dict) or entry.get("kind") not in REPLY_KINDS:
            raise Error(f"malformed reply: {entry!r}")
        target = entry.get("target_id")
        valid_target = target is None if entry["kind"] == "issue" else (
            isinstance(target, int) and not isinstance(target, bool))
        body = entry.get("body")
        if not valid_target or not isinstance(body, str) or not body.strip():
            raise Error(f"malformed reply: {entry!r}")
        entry.setdefault("selected", True)
        entry.setdefault("posted", False)
        ids = entry.setdefault("finding_ids", [])
        verified = entry.setdefault("verified", [])
        if not finding_ids_only(ids) or not finding_ids_only(verified) or set(verified) - set(ids):
            raise Error(f"malformed reply: {entry!r}")
    return replies


def reply_text(entry, post):
    return (post and entry.get("post_body")) or entry["body"]


def shown_reply(entry, post):
    """The reply's wording, with a heading for each finding ID it does not show."""
    text = reply_text(entry, post)
    headings = [f"**{severity_of(fid)} {fid}**" for fid in dict.fromkeys(entry["finding_ids"])]
    missing = [heading for heading in headings if heading not in text]
    return f"{', '.join(missing)}: {text}" if missing else text


def preview_replies(pr, data, viewer, post):
    replies = validated_replies(data)
    lines = []
    for entry in replies:
        state = "" if entry["selected"] else " (not selected)"
        target = "" if entry["target_id"] is None else f" {entry['target_id']}"
        ids = ", ".join(entry["finding_ids"])
        lines += [f"## {entry['kind']}{target}{state}", "", f"Findings: {ids}", ""]
        if entry["verified"]:
            lines += [f"Verified: {', '.join(entry['verified'])}", ""]
        goes_out = entry["selected"] and not entry["posted"]
        author = reply_author(pr, entry, viewer) if goes_out else None
        if author:
            lines += [f"Mentions: @{author}", ""]
        lines += [shown_reply(entry, post), ""]
    return "\n".join(lines), {"replies": sum(e["selected"] and not e["posted"] for e in replies),
                              "comment_lang": data.get("comment_lang")}


def post_differs(data):
    """The IDs of what goes out in other wording than the preview's."""
    if "findings" in data:
        ids = [f["id"] for f in data["findings"]
               if f["selected"] and comment_view(f, True) != comment_view(f, False)]
        ids += [p["id"] for p in data["prior"] if p["state"] != "waived" and p.get("post_note")
                and p["post_note"] != p["note"]]
        return ids
    ids = []
    for entry in data["replies"]:
        if entry["selected"] and not entry["posted"] and reply_text(entry, True) != entry["body"]:
            ids += entry["finding_ids"] or [f"{entry['kind']} {entry['target_id']}"]
    return list(dict.fromkeys(ids))


def cmd_preview(pr_url, path):
    pr = checked_pr(pr_url)
    data = read_json(path)
    if "findings" in data:
        view = view_for_draft(pr, data)
        text, summary = preview_review(data, view, False)
        post_text, _ = preview_review(data, view, True)
        if summary["verdict"]:
            data["previewed_verdict"] = summary["verdict"]
            write_json(path, data)
    else:
        viewer = view_pr(pr, require_open=False)["viewer"]
        text, summary = preview_replies(pr, data, viewer, False)
        post_text, _ = preview_replies(pr, data, viewer, True)
    stem = re.sub(r"\.json$", "", path)
    paths = {"preview_path": stem + "-preview.md", "post_preview_path": stem + "-post.md"}
    for name, content in (("preview_path", text), ("post_preview_path", post_text)):
        with open(paths[name], "w", encoding="utf-8", newline="\n") as f:
            f.write(content)
    return {**paths, **summary, "post_differs": post_differs(data)}


def merge_wording(data, wording):
    for entry in wording.get("findings", []):
        if not isinstance(entry, dict):
            raise Error(f"malformed wording: {entry!r}")
        known = [e for e in [*data["findings"], *data["prior"]] if e["id"] == entry.get("id")]
        values = {k: entry[k] for k in FINDING_WORDING if k in entry}
        if not known or not all(isinstance(v, str) for v in values.values()):
            raise Error(f"malformed wording: {entry!r}")
        known[0].update(values, worded=True)


def merge_reply_wording(data, wording):
    replies = validated_replies(data)
    for entry in wording.get("replies", []):
        index = entry.get("index") if isinstance(entry, dict) else None
        valid = type(index) is int and 0 <= index < len(replies)
        if not valid or not isinstance(entry.get("post_body"), str):
            raise Error(f"malformed wording: {entry!r}")
        replies[index]["post_body"] = entry["post_body"]


def merge_wording_file(data, name):
    wording = read_json(name)
    lang = wording.get("comment_lang") if isinstance(wording, dict) else None
    if not isinstance(lang, str) or not COMMENT_LANG_RE.fullmatch(lang):
        raise Error(f"{name} has no valid comment_lang")
    if data.get("comment_lang", lang) != lang:
        raise Error(f"{name} names another comment language than {data['comment_lang']}")
    data["comment_lang"] = lang
    for key in ("findings", "replies"):
        if not isinstance(wording.get(key, []), list):
            raise Error(f"malformed wording in {name}: {key} is not a list")
    if "findings" in data:
        merge_wording(data, wording)
    else:
        merge_reply_wording(data, wording)


def cmd_wording(pr_url, path):
    checked_pr(pr_url)
    data = read_json(path)
    if "findings" not in data:
        validated_replies(data)
    directory = glob.escape(os.path.dirname(path) or ".")
    names = sorted(glob.glob(os.path.join(directory, "wording-*.json")))
    for name in names:
        try:
            merge_wording_file(data, name)
        except Error as e:
            os.remove(name)
            raise Error(f"{os.path.basename(name)}: {e}") from None
    write_json(path, data)
    for name in names:
        os.remove(name)
    missing = wording_missing(data) if "findings" in data else []
    return {"path": path, "comment_lang": data.get("comment_lang"), "missing": missing}


def add_thread(pr, review_id, finding, draft, as_file):
    body = finding_block(comment_view(finding, True), draft["comment_lang"], as_file)
    path, line = split_location(finding["location"])
    fields = {"pullRequestReviewId": review_id, "path": path,
              "body": checked_size(body, f"{finding['id']}")}
    if as_file:
        fields["subjectType"] = "FILE"
    else:
        fields.update(subjectType="LINE", line=line, side="RIGHT")
    graphql(pr, ADD_THREAD, input=fields)


def settle_failed_review(pr, review_id, path, draft, error):
    """Returns the URL of a review a failed call still submitted; raises otherwise."""
    try:
        node = graphql(pr, REVIEW_STATE, id=review_id).get("node") or {}
        if not node.get("state"):
            raise Error("GitHub did not report its state")
    except Exception as e:
        draft["posted"] = True
        write_json(path, draft)
        raise Error(f"{error}; whether the review went out is unknown ({e}): check {pr.url} "
                    "before running the skill again") from None
    if node["state"] != "PENDING":
        return node.get("url")
    try:
        graphql(pr, DELETE_REVIEW, input={"pullRequestReviewId": review_id})
    except Error as e:
        raise Error(f"{error}; the pending review could not be deleted ({e}): submit or discard "
                    "it on GitHub before running the skill again") from None
    draft.pop("review_id", None)
    write_json(path, draft)
    raise error


def settle_earlier_review(pr, path, draft):
    """Settles the review an interrupted run of this draft created, before anything goes out."""
    review_id = draft.get("review_id")
    if not review_id:
        return
    try:
        node = graphql(pr, REVIEW_STATE, id=review_id).get("node")
        if node is not None and not node.get("state"):
            raise Error("GitHub did not report its state")
    except Exception as e:
        if isinstance(e, Rejected) and e.types == {"NOT_FOUND"}:
            node = None
        else:
            raise Error(f"whether the review of an earlier run went out is unknown ({e}): nothing "
                        f"was sent; check {pr.url} and try again") from None
    if node and node["state"] != "PENDING":
        draft["posted"] = True
        write_json(path, draft)
        url = node.get("url") or pr.url
        raise Error(f"this review was already posted by an earlier run: {url}")
    if node:
        try:
            graphql(pr, DELETE_REVIEW, input={"pullRequestReviewId": review_id})
        except Error as e:
            raise Error(f"the pending review of an earlier run could not be deleted ({e}): submit "
                        "or discard it on GitHub before running the skill again") from None
    draft.pop("review_id")
    write_json(path, draft)


def same_text(left, right):
    normalized = [(text or "").replace("\r\n", "\n").strip() for text in (left, right)]
    return normalized[0] == normalized[1]


def confirm_review(pr, review_id, url, event, body, threads):
    try:
        node = graphql(pr, REVIEW_STATE, id=review_id).get("node") or {}
    except Error as e:
        raise Error(f"the review at {url} went out but could not be read back: {e}") from None
    problems = []
    if node.get("state") != SUBMITTED_STATES.get(event):
        problems.append(f"state {node.get('state')} for {event}")
    if not same_text(node.get("body"), body):
        problems.append("another body")
    found = (node.get("comments") or {}).get("totalCount")
    if found != threads:
        problems.append(f"{found} comments of {threads}")
    if problems:
        raise Error(f"the review at {url} went out but reads back with {', '.join(problems)}")


def post_review(pr, path, draft):
    if draft.get("posted"):
        raise Error("this review was already posted")
    view = view_for_draft(pr, draft)
    if (draft.get("url") or "").casefold() != pr.url.casefold():
        raise Error(f"{path} is not a draft of {pr.url}")
    settle_earlier_review(pr, path, draft)
    if view["headRefOid"] != draft["head_sha"]:
        raise Error(f"the pull request moved past the reviewed head {draft['head_sha']} to "
                    f"{view['headRefOid']}; run the skill again")
    plan = review_plan(draft, view)
    if not plan["selected"] and draft["kind"] != "gate":
        raise Error("no finding is selected")
    missing = wording_missing(draft)
    if not draft.get("comment_lang") or missing:
        raise Error(f"the wording is not complete, run gh-review.py wording first: {missing}")
    previewed = draft.get("previewed_verdict")
    if draft["kind"] == "gate" and previewed != plan["verdict"]:
        shown = f"the preview showed {previewed}" if previewed else "no preview was made"
        raise Error(f"{shown}, but the verdict is now {plan['verdict']}; preview it again")
    try:
        created = graphql(pr, ADD_REVIEW, input={"pullRequestId": view["id"],
                                                 "commitOID": draft["head_sha"]})
    except Error as e:
        raise Error(f"{e}; a pending review of yours may be in the way: submit or discard it on "
                    "GitHub before running the skill again") from None
    review_id = created["addPullRequestReview"]["pullRequestReview"]["id"]
    to_body, fallbacks = [], []
    counts = {"inline": 0, "file": 0}
    recovered = None
    try:
        draft["review_id"] = review_id
        write_json(path, draft)
        for finding in plan["selected"]:
            place = finding["placement"]
            if place == "body":
                to_body.append(finding)
                continue
            if place == "inline":
                try:
                    add_thread(pr, review_id, finding, draft, False)
                    counts["inline"] += 1
                    continue
                except Rejected:
                    fallbacks.append(finding["id"])
            try:
                add_thread(pr, review_id, finding, draft, True)
                counts["file"] += 1
            except Rejected:
                if place == "file":
                    fallbacks.append(finding["id"])
                to_body.append(finding)
        body = checked_size(review_body(draft, plan, to_body, True), "the review body")
        submitted = graphql(pr, SUBMIT_REVIEW, input={
            "pullRequestReviewId": review_id, "event": plan["event"], "body": body})
        url = submitted["submitPullRequestReview"]["pullRequestReview"]["url"]
    except Exception as e:
        # GitHub can apply a submit whose response fails.
        url = settle_failed_review(pr, review_id, path, draft, e)
        recovered = str(e)
    draft["posted"] = True
    write_json(path, draft)
    if not recovered:
        confirm_review(pr, review_id, url, plan["event"], body, counts["inline"] + counts["file"])
    return {
        "review_url": url,
        "event": plan["event"], "verdict": plan["verdict"], "own_pr": plan["own_pr"],
        "inline": counts["inline"], "file": counts["file"], "body": len(to_body),
        "fallbacks": fallbacks, "recovered_from": recovered, "confirmed": not recovered,
    }


def belongs(pr, url, kind):
    tail = f"/repos/{pr.repo}/{kind}/{pr.number}"
    return (url or "").rstrip("/").casefold().endswith(tail.casefold())


def not_on_pr(pr, comment_id):
    return Error(f"comment {comment_id} is not on PR #{pr.number}; "
                 "for a renamed repository, use its current URL")


def reply_author(pr, entry, viewer):
    if entry["kind"] == "review":
        target = rest_get(pr, f"repos/{pr.repo}/pulls/{pr.number}/reviews/{entry['target_id']}")
    elif entry["kind"] == "issue_comment":
        target = rest_get(pr, f"repos/{pr.repo}/issues/comments/{entry['target_id']}")
        if not belongs(pr, target.get("issue_url"), "issues"):
            raise not_on_pr(pr, entry["target_id"])
    else:
        return None
    login = (target.get("user") or {}).get("login") or ""
    login = login[:-len("[bot]")] if login.endswith("[bot]") else login
    return login if login and login != viewer else None


def reply_request(pr, entry, viewer):
    """Where a reply is sent, the comment it answers, the comments it joins there, and its body."""
    body = shown_reply(entry, True)
    if entry["kind"] == "thread":
        comment = rest_get(pr, f"repos/{pr.repo}/pulls/comments/{entry['target_id']}")
        if not belongs(pr, comment.get("pull_request_url"), "pulls"):
            raise not_on_pr(pr, entry["target_id"])
        answered = comment.get("in_reply_to_id") or entry["target_id"]
        collection = f"repos/{pr.repo}/pulls/{pr.number}/comments"
        path = f"{collection}/{answered}/replies"
    else:
        author = reply_author(pr, entry, viewer)
        if author:
            body = f"@{author} {body}"
        answered = entry["target_id"]
        collection = path = f"repos/{pr.repo}/issues/{pr.number}/comments"
    return path, answered, collection, checked_size(body, "a reply")


def sent_reply(pr, entry, collection, answered, body, viewer):
    """The URL of the viewer's comment with this body in the collection, in the answered thread for
    a thread reply, or None.
    """
    for comment in rest_pages(pr, collection):
        same = same_text(comment.get("body"), body)
        in_place = entry["kind"] != "thread" or comment.get("in_reply_to_id") == answered
        if same and in_place and comment_author(comment) == viewer:
            return comment.get("html_url") or pr.url
    return None


def confirm_reply(pr, entry, sent, answered, body, viewer):
    """Reads a reply back and returns its URL."""
    url = sent.get("html_url") or pr.url
    kind = "pulls" if entry["kind"] == "thread" else "issues"
    try:
        comment = rest_get(pr, f"repos/{pr.repo}/{kind}/comments/{sent.get('id')}")
    except Error as e:
        raise Error(f"the reply at {url} went out but could not be read back: {e}") from None
    problems = []
    if not same_text(comment.get("body"), body):
        problems.append("another body")
    if comment_author(comment) != viewer:
        problems.append(f"author {comment_author(comment)}")
    if entry["kind"] == "thread" and comment.get("in_reply_to_id") != answered:
        problems.append(f"thread {comment.get('in_reply_to_id')} for {answered}")
    if problems:
        raise Error(f"the reply at {url} went out but reads back with {', '.join(problems)}")
    return comment.get("html_url") or url


def post_replies(pr, path, data):
    replies = validated_replies(data)
    if not data.get("comment_lang") and any(e["selected"] and not e["posted"] for e in replies):
        raise Error("the wording is not complete, run gh-review.py wording first")
    viewer = view_pr(pr, require_open=False)["viewer"]
    urls = []
    for entry in replies:
        if not entry["selected"] or entry["posted"]:
            continue
        target, answered, collection, body = reply_request(pr, entry, viewer)
        # GitHub can apply a post whose response fails.
        url = None
        if entry.get("attempted"):
            url = sent_reply(pr, entry, collection, answered, body, viewer)
        sent = None
        if not url:
            entry["attempted"] = True
            write_json(path, data)
            sent = rest_post(pr, target, {"body": body})
        entry["posted"] = True
        write_json(path, data)
        urls.append(confirm_reply(pr, entry, sent, answered, body, viewer) if sent else url)
    return {"posted": len(urls), "urls": urls, "confirmed": len(urls)}


def commit_on_pr(pr, sha, head):
    if sha == head:
        return True
    try:
        compare = rest_get(pr, f"repos/{pr.repo}/compare/{sha}...{head}")
    except Error as e:
        if "(HTTP 404)" not in str(e):
            raise
        return False
    return compare.get("status") in ("ahead", "identical")


def pushed_state(pr, commits_path):
    commits = read_json(commits_path).get("commits") or []
    head = view_pr(pr, require_open=False)["headRefOid"]
    tip = commits[0]["sha"] if commits else None
    return {"pushed": tip is None or commit_on_pr(pr, tip, head), "head_sha": head, "tip": tip}


def cmd_pushed(pr_url, commits_path):
    return pushed_state(checked_pr(pr_url), commits_path)


def cmd_post(pr_url, path, commits_path):
    pr = checked_pr(pr_url)
    data = read_json(path)
    if commits_path:
        if "findings" in data or any(e["verified"] for e in validated_replies(data)):
            raise Error(f"--commits sends only replies that mark nothing verified: {path} holds "
                        "findings or a verified reply")
        if not pushed_state(pr, commits_path)["pushed"]:
            raise Error("the pull request does not contain the fix commits yet; push them first")
    return post_review(pr, path, data) if "findings" in data else post_replies(pr, path, data)


def cmd_comments(pr_url, tmp_dir):
    pr = checked_pr(pr_url)
    view = view_pr(pr, require_open=False)
    viewer = view["viewer"]
    reviews, comments, issue_comments = visible_comments(pr)
    path = os.path.join(tmp_dir, "comments.json")
    write_json(path, {
        "viewer": viewer,
        "review_comments": [
            {"id": c.get("id"), "in_reply_to": c.get("in_reply_to_id"),
             "author": comment_author(c), "path": c.get("path"),
             "line": c.get("line") or c.get("original_line"), "created_at": c.get("created_at"),
             "body": visible_body(c)}
            for c in comments],
        "reviews": [{"id": r.get("id"), "author": comment_author(r), "state": r.get("state"),
                     "submitted_at": r.get("submitted_at"), "body": visible_body(r)}
                    for r in reviews if visible_body(r)],
        "issue_comments": [
            {"id": c.get("id"), "author": comment_author(c), "created_at": c.get("created_at"),
             "body": visible_body(c)}
            for c in issue_comments],
    })
    return {"path": path, "pr_body_path": write_pr_body(tmp_dir, view)}


def resolved_roots(pr):
    """The IDs of the first comments of the threads resolved on GitHub."""
    roots, cursor = set(), None
    for _ in range(MAX_PAGES):
        data = graphql(pr, REVIEW_THREADS, owner=pr.owner, name=pr.name, number=pr.number,
                       cursor=cursor)
        threads = data["repository"]["pullRequest"]["reviewThreads"]
        for thread in threads["nodes"]:
            first = thread["comments"]["nodes"]
            if thread["isResolved"] and first:
                roots.add(first[0]["databaseId"])
        if not threads["pageInfo"]["hasNextPage"]:
            break
        cursor = threads["pageInfo"]["endCursor"]
    return roots


def cmd_raised(pr_url, tmp_dir, discussion=False):
    pr = checked_pr(pr_url)
    reviews, comments, issue_comments = visible_comments(pr)
    dismissed = {r.get("id") for r in reviews if r.get("state") == "DISMISSED"}
    resolved = set() if discussion else resolved_roots(pr)
    review_of = {r.get("id"): r for r in reviews}

    def entry(comment, location, **fields):
        text = visible_body(comment)
        if not text:
            return None
        if discussion:
            fields["created_at"] = comment_time(comment)
        return {"author": comment_author(comment), "location": location, "text": text, **fields}

    units = [[entry(review, "PR")] for review in reviews if review.get("id") not in dismissed]
    threads = {}
    for comment in comments:
        root = comment.get("in_reply_to_id") or comment.get("id")
        if comment.get("pull_request_review_id") in dismissed or root in resolved:
            continue
        if root not in threads:
            threads[root] = []
            units.append(threads[root])
        opening = {"review_opening": visible_body(
            review_of.get(comment.get("pull_request_review_id"), {}))[:OPENING_LIMIT]
        } if discussion else {}
        threads[root].append(entry(comment, comment_place(comment),
                                   in_reply_to=comment.get("in_reply_to_id"), **opening))
    units += [[entry(comment, "PR")] for comment in issue_comments]
    units = [[c for c in unit if c] for unit in units]
    batches = batched([unit for unit in units if unit],
                      lambda unit: sum(len(c["text"]) for c in unit))
    shared = {}
    if discussion:
        people = participants(view_pr(pr, require_open=False))
        outside = [r for r in reviews if r.get("id") not in dismissed] + issue_comments
        spoken_outside = [spoken(c, people["viewer"]) for c in outside]
        shared = {**people, "conversation": by_time(c for c in spoken_outside if c["text"])}
    directory = os.path.join(tmp_dir, "raised")
    os.makedirs(directory, exist_ok=True)
    for n, batch in enumerate(batches, 1):
        write_json(os.path.join(directory, f"batch-{n}.json"),
                   {**shared, "comments": [c for unit in batch for c in unit]})
    return {"directory": directory, "batches": len(batches),
            "comments": sum(len(unit) for batch in batches for unit in batch)}


def cmd_participants(pr_url):
    return participants(view_pr(checked_pr(pr_url), require_open=False))


def cmd_fixes(pr_url, tmp_dir, document):
    pr = checked_pr(pr_url)
    header, _ = checked_document(pr, document)
    branch = header.get("branch")
    log = run(["git", "-c", "core.quotePath=off", "log", "--format=%H%x00%s", "--name-only",
               f"{header['head_sha']}..{branch or 'HEAD'}"])
    commits = []
    for line in log.split("\n"):
        sha, separator, subject = line.partition("\x00")
        if separator:
            commits.append({"sha": sha, "subject": subject, "files": []})
        elif line.strip() and commits:
            commits[-1]["files"].append(line.strip())
    path = os.path.join(tmp_dir, "fix-commits.json")
    write_json(path, {"commits": commits})
    view = view_pr(pr, require_open=False)
    head_ref = view.get("headRefName") or ""
    return {
        "path": path, "commits": len(commits), "tip": commits[0]["sha"] if commits else None,
        "branch": branch, "head_ref": head_ref if BRANCH_NAME_RE.fullmatch(head_ref) else None,
        "head_repo": (view.get("headRepository") or {}).get("nameWithOwner"),
    }


def quoted_finding(finding):
    """The place and text of a finding, by which a reply outside a thread names it."""
    location = (finding.get("location") or "").replace("`", "")
    parts = [f"`{location}`"] if location and location != "PR" else []
    text = " ".join((finding.get("text") or "").split())[:QUOTE_LIMIT]
    if text:
        parts.append(text)
    return "\n\n> " + " ".join(parts) if parts else ""


def cmd_replies(pr_url, tmp_dir, document, lang):
    pr = checked_pr(pr_url)
    header, findings = checked_document(pr, document)
    labels = labels_for(lang)
    short = header["head_sha"][:SHORT_SHA]
    prior = read_json(os.path.join(tmp_dir, "prior.json"))["findings"]
    posted = {f["id"]: f for f in prior}
    earlier = {f["id"] for f in prior if f.get("verified")}
    replies, body_lines, body_ids, body_verified, unverified = [], [], [], [], []
    unchanged = []
    for finding in findings:
        fid, verification = finding["id"], finding["metadata"].get("Verification", "")
        source = posted.get(fid)
        if not source:
            continue
        target = source["target"]
        if not verification or verification == PRIOR_VERIFIED:
            unverified.append(fid)
            continue
        note = verification.partition(" — ")[2].strip()
        verified = has_label(verification, "Verified")
        if verified and fid in earlier:
            unchanged.append(fid)
            continue
        as_recommended = note.startswith("[as-recommended]")
        note = re.sub(r"^\[(?:as-recommended|differs)\]\s*", "", note)
        if verified:
            text = f"✅ **{severity_of(fid)} {fid}**: {labels['confirmed'].format(sha=short)}"
            if not as_recommended and note:
                text += f" {note}"
        else:
            result = labels["not_resolved"].format(sha=short)
            text = f"💬 **{severity_of(fid)} {fid}**: {result} {note}"
        if target["kind"] == "thread":
            replies.append({"kind": "thread", "target_id": target["id"], "finding_ids": [fid],
                            "body": text, "verified": [fid] if verified else []})
        else:
            body_lines.append(text + quoted_finding(source))
            body_ids.append(fid)
            if verified:
                body_verified.append(fid)
    if body_lines:
        replies.append({"kind": "issue", "target_id": None, "finding_ids": body_ids,
                        "body": "\n\n".join(body_lines), "verified": body_verified})
    path = os.path.join(tmp_dir, "replies.json")
    write_json(path, {"replies": replies})
    return {"path": path, "replies": len(replies), "unverified": unverified,
            "unchanged": unchanged,
            "pr_body_path": write_pr_body(tmp_dir, view_pr(pr, require_open=False))}


def parser():
    top = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    commands = top.add_subparsers(dest="command", required=True)

    def command(name, *positional):
        sub = commands.add_parser(name)
        for arg in positional:
            sub.add_argument(arg)
        return sub

    command("own", "pr_url", "tmp_dir")
    command("ids", "pr_url", "tmp_dir")
    collect = command("collect", "pr_url", "tmp_dir")
    collect.add_argument("--kind", required=True, choices=("review", "gate"))
    prior = command("prior", "pr_url", "tmp_dir")
    prior.add_argument("--kind", required=True, choices=("review", "gate"))
    prior.add_argument("--document", required=True)
    prior.add_argument("--trust", action="store_true")
    draft = command("draft", "pr_url", "tmp_dir", "document")
    draft.add_argument("--kind", required=True, choices=("review", "gate"))
    draft.add_argument("--lang", required=True, choices=sorted(LABELS))
    draft.add_argument("--prior-doc")
    command("wording", "pr_url", "path")
    command("comments", "pr_url", "tmp_dir")
    raised = command("raised", "pr_url", "tmp_dir")
    raised.add_argument("--discussion", action="store_true")
    command("participants", "pr_url")
    command("fixes", "pr_url", "tmp_dir", "document")
    command("pushed", "pr_url", "commits")
    replies = command("replies", "pr_url", "tmp_dir", "document")
    replies.add_argument("--lang", required=True, choices=sorted(LABELS))
    command("preview", "pr_url", "path")
    post = command("post", "pr_url", "path")
    post.add_argument("--commits")
    return top


def dispatch(args):
    if args.command == "own":
        return cmd_own(args.pr_url, args.tmp_dir)
    if args.command == "ids":
        return cmd_ids(args.pr_url, args.tmp_dir)
    if args.command == "collect":
        return cmd_collect(args.pr_url, args.tmp_dir, args.kind)
    if args.command == "prior":
        return cmd_prior(args.pr_url, args.tmp_dir, args.kind, args.document, args.trust)
    if args.command == "draft":
        return cmd_draft(args.pr_url, args.tmp_dir, args.document, args.kind, args.lang,
                         args.prior_doc)
    if args.command == "wording":
        return cmd_wording(args.pr_url, args.path)
    if args.command == "comments":
        return cmd_comments(args.pr_url, args.tmp_dir)
    if args.command == "raised":
        return cmd_raised(args.pr_url, args.tmp_dir, args.discussion)
    if args.command == "participants":
        return cmd_participants(args.pr_url)
    if args.command == "fixes":
        return cmd_fixes(args.pr_url, args.tmp_dir, args.document)
    if args.command == "pushed":
        return cmd_pushed(args.pr_url, args.commits)
    if args.command == "replies":
        return cmd_replies(args.pr_url, args.tmp_dir, args.document, args.lang)
    if args.command == "preview":
        return cmd_preview(args.pr_url, args.path)
    return cmd_post(args.pr_url, args.path, args.commits)


def main():
    args = parser().parse_args()
    try:
        print(json.dumps(dispatch(args)))
    except (Error, OSError, KeyError, TypeError, ValueError) as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
