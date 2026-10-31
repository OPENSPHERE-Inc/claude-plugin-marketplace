#!/usr/bin/env python3
"""gh-review.py — read and post the GitHub reviews of the cgh skills.

Usage:
    python3 gh-review.py prior <pr_url> <tmp_dir> --kind review|gate --document <path>
        [--trust]
    python3 gh-review.py draft <pr_url> <tmp_dir> <document> --kind review|gate --lang en|ja
        [--prior-doc <path>]
    python3 gh-review.py wording <pr_url> <json_path>
    python3 gh-review.py comments <pr_url> <tmp_dir>
    python3 gh-review.py fixes <pr_url> <tmp_dir> <document>
    python3 gh-review.py pushed <pr_url> <fix_commits_json>
    python3 gh-review.py replies <pr_url> <tmp_dir> <document> --lang en|ja
    python3 gh-review.py preview <pr_url> <json_path>
    python3 gh-review.py post <pr_url> <json_path> [--commits <fix_commits_json>]

prior: finds the findings the authenticated user posted with this script, from the
markers in their comments, leaving out those of a dismissed review. Writes
<tmp_dir>/prior.json with the findings of --kind not yet marked verified or waived, Info
left out since creview's verification skips it, and, when there are any, <document>: a
review document creview's verification reads, with a Source: pr-comments bullet and a
Trust bullet: on at the pull request's head or with --trust, otherwise off. Stops when
there are any and the working tree holds what the pull request does not: commits past
its head, or uncommitted changes at its head. When findings of --kind are waived, writes
them to <tmp_dir>/waived.md and prints its path as waived_document.

draft: reads a review document of the pull request, with or without findings, which must
still be at the document's head, and writes <tmp_dir>/draft.json: every finding, numbered after
every ID already used on the pull request, with whether it is selected and where it goes
(inline: a line of the diff; file: a file of the diff; body: anywhere else). Selected by
default: Will Fix with Maintain or Alternative, and Will Fix with Downgrade at Critical or
Major, which stays a real problem. --prior-doc, which must be at the pull request's head too,
adds the verification of earlier gate findings. It also writes <tmp_dir>/pr-body.json, the pull
request's title and description.

wording: merges every wording-*.json next to <json_path> into it: comment_lang, the
language comments go out in, with, per finding, summary (the recommendation for people,
in the preview's language) and post_text, post_summary, post_note (the wording that goes
out, when it differs from the preview's), or, per reply by index, post_body. It changes
nothing else in the file, removes the merged files, so that a later run cannot undo an
edit to the file, and prints the selected findings and the earlier findings with a note
that no wording has covered yet.

comments: writes <tmp_dir>/comments.json, the pull request's comments with their IDs and
answered, whether a reply of the authenticated user already marks them, and
<tmp_dir>/pr-body.json.

fixes: writes <tmp_dir>/fix-commits.json, the commits on the document's Branch bullet,
or HEAD without one, past the document's head. Prints head_ref, the pull request's branch,
as null when its name holds a character unsafe to show in a command.

pushed: says whether the pull request's head contains the newest of those commits.

replies: writes <tmp_dir>/replies.json from the verification in <document> and the
targets in <tmp_dir>/prior.json, and <tmp_dir>/pr-body.json.

preview: writes <json_path minus .json>-preview.md, what post would send in the preview's
language, and -post.md, the same in the wording that goes out. The JSON file is
draft.json, or a file with a "replies" list of {kind: thread|review|issue_comment|issue,
target_id, finding_ids, body, post_body, selected (default true), verified}. For a draft,
wording_missing holds what wording would print as missing, an empty recommendation or not.
For a gate draft, it first waits for GitHub to compute whether the pull request merges, and
records the verdict it shows as previewed_verdict.

post: sends it. A review needs its wording and its head unchanged, is sent as one pending
review, and cannot be sent twice. A gate draft also needs its verdict to match
previewed_verdict. When a call fails, the review's state decides: one that
went out anyway counts as posted, one still pending is deleted, and with the state
unknown the review counts as posted, so that a rerun cannot send it twice. A reply to a
review or an issue comment goes out as an issue comment that mentions its author. Replies sent
are marked in the file, so a rerun skips them. --commits refuses a file with findings or a
reply that marks a finding verified, and refuses to send anything until the pull request
contains those commits.

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
import urllib.parse
from collections import namedtuple

PR_URL_RE = re.compile(
    r"https://([A-Za-z0-9.-]+(?::[0-9]+)?)/([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+)"
    r"/pull/([0-9]+)(?:[/?#].*)?"
)
PR_BULLET_RE = re.compile(r"- \*\*PR:\*\* (\S+) \(head ([0-9a-f]+), base ([0-9a-f]+)\)")
BRANCH_BULLET_RE = re.compile(r"- \*\*Branch:\*\* ([\w./+@-]+)")
BRANCH_NAME_RE = re.compile(r"[\w./+@-]+")
FINDING_ID = r"(?:C|M|mi|I)-[0-9]+"
FINDING_IDS = rf"{FINDING_ID}(?:,{FINDING_ID})*"
FINDING_ID_RE = re.compile(FINDING_ID)
HEADING_RE = re.compile(rf"### ({FINDING_ID})\s+[—-]\s+`?([^`]*?)`?(?:\s+\[.*\])?\s*")
FINDING_HEADING_RE = re.compile(rf"###\s+{FINDING_ID}")
METADATA_OPEN_RE = re.compile(rf"<!-- METADATA\(({FINDING_ID})\) -->")
METADATA_RE = re.compile(r"- \*\*(Triage|Estimate|Status|Verification):\*\* (.*)")
LABEL_LINE_RE = re.compile(r"\*\*[^*]+[:：]\*\*\s*")
PLAN_ITEM_RE = re.compile(r"(?:^|\s)\([0-9]+\)\s+")
LOCATION_RE = re.compile(r"(.+?):([0-9]+)(?:[-–,].*)?")
HUNK_RE = re.compile(r"@@ -[0-9]+(?:,[0-9]+)? \+([0-9]+)(?:,[0-9]+)? @@")
# Only what GitHub is sure to render as code: a closed fence, or a closed span on one line.
CODE_RE = re.compile(
    r"^ {0,3}(?P<fence>`{3,})[^`\n]*\n(?:.*\n)*? {0,3}(?P=fence)`*[ \t\r]*$"
    r"|(?<![\\`])(?P<ticks>`+)(?!`)[^\n]*?(?<!`)(?P=ticks)(?!`)", re.M)
# An escape, an active backtick, or a mention, with the backslash that would hide its quote.
OUTSIDE_CODE_RE = re.compile(
    r"\\[^@]|`|\\?(?P<mention>(?<![A-Za-z0-9/@])@[A-Za-z0-9][\w/-]*)", re.S)
# What starts a Markdown block at the beginning of a paragraph of a review document.
BLOCK_START_RE = re.compile(r"#{1,6}(?:\s|$)|[-+*](?:\s|$)|>|`{3}|~{3}|<[A-Za-z/!?]")
FINDING_RE = re.compile(
    rf"<!-- cgh:finding (?P<id>{FINDING_ID}) (?P<kind>review|gate) (?P<loc>\S+) -->"
    r"(?P<body>.*?)<!-- /cgh:finding (?P=id) -->", re.S)
VERIFIED_RE = re.compile(rf"<!-- cgh:verified ({FINDING_IDS}) -->")
WAIVED_RE = re.compile(rf"<!-- cgh:waived ({FINDING_IDS}) -->")
REPLY_RE = re.compile(r"<!-- cgh:reply (thread|review|issue_comment) ([0-9]+) -->")
REC_MARKER = "<!-- cgh:rec -->"
COMMENT_LANG_RE = re.compile(r"[a-z]{2,3}(?:-[A-Za-z0-9]+)*")
FINDING_WORDING = ("summary", "post_text", "post_summary", "post_note")
SEVERITIES = {"C": "Critical", "M": "Major", "mi": "Minor", "I": "Info"}
BLOCKING = ("Critical", "Major")
SCRATCH_EXCLUDES = [":(top,exclude).claude/tmp", ":(top,exclude).claude/worktrees"]
REPLY_KINDS = ("thread", "review", "issue_comment", "issue")
SHORT_SHA = 10
PAGE_SIZE = 100
MAX_PAGES = 100
BODY_LIMIT = 65000
MERGEABLE_TRIES = 5
MERGEABLE_WAIT = 3
PR_QUERY = """
query($owner: String!, $name: String!, $number: Int!) {
  viewer { login }
  repository(owner: $owner, name: $name) {
    pullRequest(number: $number) {
      id number state title body headRefOid headRefName baseRefOid mergeable
      author { login }
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
  node(id: $id) { ... on PullRequestReview { state url } }
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
    },
}

PullRequest = namedtuple("PullRequest", "host repo owner name number url")
Posted = namedtuple("Posted", "findings verified waived used")


class Error(Exception):
    pass


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
        raise Error(proc.stderr.strip() or f"{' '.join(cmd[:2])} exited with {proc.returncode}")
    return proc.stdout


def parse_pr_url(url):
    m = PR_URL_RE.fullmatch(url)
    if not m:
        raise Error(f"not a pull request URL: {url}")
    host, owner, name, number = m.group(1).lower(), m.group(2), m.group(3), int(m.group(4))
    return PullRequest(host, f"{owner}/{name}", owner, name, number,
                       f"https://{host}/{owner}/{name}/pull/{number}")


def graphql(pr, query, **variables):
    body = json.dumps({"query": query, "variables": variables})
    return json.loads(run(["gh", "api", "graphql", "--hostname", pr.host, "--input", "-"],
                          input=body))["data"]


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
    write_json(path, {"title": view.get("title") or "", "body": view.get("body") or ""})
    return path


def safe_text(text):
    # Posted text comes from reviewers that read pull request content: it must not notify
    # anyone or hide anything in an HTML comment, such as a marker of this script.
    text = text.replace("<!--", "&lt;!--")
    kept, last = [], 0
    for code in CODE_RE.finditer(text):
        kept += [quiet_outside_code(text[last:code.start()]), code.group(0)]
        last = code.end()
    return "".join([*kept, quiet_outside_code(text[last:])])


def quiet_outside_code(text):
    # An active backtick left here could pair with an added quote and leave the mention outside it.
    def quiet(match):
        if match.group("mention"):
            return f"`{match.group('mention')}`"
        return "\\`" if match.group(0) == "`" else match.group(0)

    return OUTSIDE_CODE_RE.sub(quiet, text)


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
            lines = f.read().split("\n")
    except OSError as e:
        raise Error(f"cannot read {path}: {e}") from None
    header, findings, current, state = {}, [], None, None
    for line in lines:
        line = line.rstrip()
        if not findings and current is None:
            bullet = PR_BULLET_RE.fullmatch(line)
            if bullet:
                header.update(url=bullet.group(1), head_sha=bullet.group(2),
                              merge_base=bullet.group(3))
            branch = BRANCH_BULLET_RE.fullmatch(line)
            if branch:
                header["branch"] = branch.group(1)
        if line.startswith("## ") and line.startswith("## Orphan"):
            break
        heading = HEADING_RE.fullmatch(line)
        if not heading and FINDING_HEADING_RE.match(line):
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


def finding_block(finding, kind, lang, with_location):
    labels = labels_for(lang)
    location = finding["location"]
    head = f"**{severity_of(finding['id'])} {finding['id']}**"
    if with_location and location != "PR":
        head += f" `{location.replace('`', '').replace('<!--', '&lt;!--')}`"
    quoted = urllib.parse.quote(location, safe="/:._-()[]@+$~,")
    parts = [f"<!-- cgh:finding {finding['id']} {kind} {quoted} -->", head, "",
             safe_text(finding["text"])]
    items = finding.get("recommendation") or []
    if items:
        parts += ["", REC_MARKER, f"**{labels['recommendation']}**", ""]
        if len(items) == 1:
            parts.append(safe_text(items[0]))
        else:
            parts += [f"{n}. {safe_text(item)}" for n, item in enumerate(items, 1)]
    parts += ["", f"<!-- /cgh:finding {finding['id']} -->"]
    return "\n".join(parts)


def comment_view(finding, post):
    """The finding as the preview (post False) or the pull request (post True) shows it."""
    text = (post and finding.get("post_text")) or finding["text"]
    summary = (post and finding.get("post_summary")) or finding.get("summary")
    return {**finding, "text": text,
            "recommendation": [summary] if summary else finding.get("recommendation") or []}


def read_block(body):
    text, _, rec = body.partition(REC_MARKER)
    lines = text.strip().split("\n")[1:]
    items = [re.sub(r"^[0-9]+\.\s+", "", line) for line in rec.strip().split("\n")[1:]
             if line.strip()]
    return "\n".join(lines).strip(), items


def posted_findings(pr, viewer):
    """The viewer's findings and verified and waived IDs outside pending and dismissed reviews,
    and every ID the viewer has used, dismissed reviews included.
    """
    reviews = rest_pages(pr, f"repos/{pr.repo}/pulls/{pr.number}/reviews")
    comments = rest_pages(pr, f"repos/{pr.repo}/pulls/{pr.number}/comments")
    issue_comments = rest_pages(pr, f"repos/{pr.repo}/issues/{pr.number}/comments")
    pending = {r.get("id") for r in reviews if r.get("state") == "PENDING"}
    dismissed = {r.get("id") for r in reviews if r.get("state") == "DISMISSED"}
    skipped = pending | dismissed

    def own(entry):
        return (entry.get("user") or {}).get("login") == viewer

    posted, verified, waived, used = {}, set(), set(), set()

    def add(match, target):
        text, items = read_block(match.group("body"))
        posted[match.group("id")] = {
            "id": match.group("id"), "kind": match.group("kind"),
            "severity": severity_of(match.group("id")),
            "location": urllib.parse.unquote(match.group("loc")),
            "text": text, "recommendation": items, "target": target,
        }

    for review in reviews:
        if own(review) and review.get("id") not in skipped:
            for match in FINDING_RE.finditer(review.get("body") or ""):
                add(match, {"kind": "review", "id": review.get("id")})
    for comment in comments:
        if own(comment) and comment.get("pull_request_review_id") not in skipped:
            if not comment.get("in_reply_to_id"):
                for match in FINDING_RE.finditer(comment.get("body") or ""):
                    add(match, {"kind": "thread", "id": comment.get("id")})
    entries = [*((r, r.get("id")) for r in reviews),
               *((c, c.get("pull_request_review_id")) for c in comments),
               *((c, None) for c in issue_comments)]
    for entry, review in entries:
        if not own(entry) or review in pending:
            continue
        body = entry.get("body") or ""
        used.update(match.group("id") for match in FINDING_RE.finditer(body))
        for marker_re, marked in ((VERIFIED_RE, verified), (WAIVED_RE, waived)):
            for match in marker_re.finditer(body):
                ids = match.group(1).split(",")
                used.update(ids)
                if review not in dismissed:
                    marked.update(ids)
    return Posted(posted, verified, waived, used)


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


def write_prior_document(path, pr, view, merge_base, viewer, findings, state, trust):
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
            location = f["location"].replace("`", "")
            lines += [f"### {f['id']} — `{location}`", "", f"- **Reviewers:** {viewer}", "",
                      "**Finding:**", "", text, "", f"<!-- METADATA({f['id']}) -->",
                      f"<!-- /METADATA({f['id']}) -->", "", "---", ""]
    with open(path, "w", encoding="utf-8", newline="\n") as out:
        out.write("\n".join(lines))


def write_waived_document(path, pr, findings):
    lines = ["# Waived Findings", "",
             f"The user accepted these findings of pull request #{pr.number} without a fix.", ""]
    for f in findings:
        location = f["location"].replace("`", "").replace("<!--", "&lt;!--")
        lines += [f"## {f['id']} — `{location}`", "", document_text(f["text"]), ""]
    with open(path, "w", encoding="utf-8", newline="\n") as out:
        out.write("\n".join(lines))


def merge_base_of(pr, view):
    compare = rest_get(
        pr, f"repos/{pr.repo}/compare/{view['baseRefOid']}...{view['headRefOid']}")
    return (compare.get("merge_base_commit") or {}).get("sha")


def cmd_prior(pr_url, tmp_dir, kind, document, trust=False):
    pr = parse_pr_url(pr_url)
    view = view_pr(pr)
    posted = posted_findings(pr, view["viewer"])
    mine = [f for f in posted.findings.values() if f["kind"] == kind]
    closed = posted.verified | posted.waived
    findings = [f for f in mine if f["id"] not in closed and f["severity"] != "Info"]
    waived = [f for f in mine if f["id"] in posted.waived - posted.verified]
    waived_document = None
    if waived:
        waived_document = os.path.join(tmp_dir, "waived.md")
        write_waived_document(waived_document, pr, waived)
    write_json(os.path.join(tmp_dir, "prior.json"), {"findings": findings})
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
                             findings, state, trust)
        written = document
    return {
        "url": pr.url, "number": pr.number, "head_sha": view["headRefOid"],
        "open": [f["id"] for f in findings],
        "verified": [f["id"] for f in mine if f["id"] in posted.verified],
        "waived": [f["id"] for f in waived],
        "document": written, "waived_document": waived_document,
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


def prior_states(pr, prior_doc, head):
    if not prior_doc:
        return []
    header, findings = checked_document(pr, prior_doc)
    if header.get("head_sha") != head:
        raise Error(f"{prior_doc} was verified at {header.get('head_sha')}, but the pull request "
                    f"is at {head}; run /cgh:gate again")
    prior = []
    for f in findings:
        verification = f["metadata"].get("Verification", "")
        state = "verified" if has_label(verification, "Verified") else "open"
        prior.append({"id": f["id"], "severity": f["severity"], "state": state,
                      "note": verification.partition(" — ")[2].strip()})
    return prior


def cmd_draft(pr_url, tmp_dir, document, kind, lang, prior_doc):
    pr = parse_pr_url(pr_url)
    header, findings = checked_document(pr, document)
    view = view_pr(pr)
    if view["headRefOid"] != header.get("head_sha"):
        raise Error(f"the pull request moved past the reviewed head {header.get('head_sha')} "
                    f"to {view['headRefOid']}; run the skill again")
    used = posted_findings(pr, view["viewer"]).used
    prior = prior_states(pr, prior_doc, view["headRefOid"])
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
        "findings": entries, "prior": prior, "posted": False,
    })
    selected = [e for e in entries if e["selected"]]
    return {
        "path": os.path.join(tmp_dir, "draft.json"), "total": len(entries),
        "selected": len(selected),
        "selected_ids": [e["id"] for e in selected],
        "prior_ids": [p["id"] for p in prior],
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
            lines.append(f"- {icon} **{p['id']}**: {safe_text(note or labels['not_verified'])}")
        lines.append("")
    if body_findings:
        lines += [f"### {labels['out_of_diff']}", ""]
        for f in body_findings:
            lines += [finding_block(comment_view(f, post), draft["kind"], lang, True), ""]
    for state in ("verified", "waived"):
        done = [p["id"] for p in draft["prior"] if p["state"] == state]
        if done:
            lines.append(f"<!-- cgh:{state} {','.join(done)} -->")
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
                block = finding_block(comment_view(f, post), draft["kind"], lang, place == "file")
                lines += [f"`{f['location']}`", "", block, ""]
    excluded = [f for f in draft["findings"] if not f["selected"]]
    if excluded and not post:
        lines += [f"## {labels['excluded']}", ""]
        lines += [f"- **{f['id']}** `{f['location']}`: {f['excluded_reason'] or ''}"
                  for f in excluded]
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


def preview_replies(data, post):
    replies = validated_replies(data)
    lines = []
    for entry in replies:
        state = "" if entry["selected"] else " (not selected)"
        target = "" if entry["target_id"] is None else f" {entry['target_id']}"
        ids = ", ".join(entry["finding_ids"])
        lines += [f"## {entry['kind']}{target}{state}", "", f"Findings: {ids}", ""]
        if entry["verified"]:
            lines += [f"Verified: {', '.join(entry['verified'])}", ""]
        lines += [safe_text(reply_text(entry, post)), ""]
    return "\n".join(lines), {"replies": sum(e["selected"] and not e["posted"] for e in replies),
                              "comment_lang": data.get("comment_lang")}


def cmd_preview(pr_url, path):
    pr = parse_pr_url(pr_url)
    data = read_json(path)
    if "findings" in data:
        view = view_for_draft(pr, data)
        text, summary = preview_review(data, view, False)
        post_text, _ = preview_review(data, view, True)
        if summary["verdict"]:
            data["previewed_verdict"] = summary["verdict"]
            write_json(path, data)
    else:
        text, summary = preview_replies(data, False)
        post_text, _ = preview_replies(data, True)
    stem = re.sub(r"\.json$", "", path)
    paths = {"preview_path": stem + "-preview.md", "post_preview_path": stem + "-post.md"}
    for name, content in (("preview_path", text), ("post_preview_path", post_text)):
        with open(paths[name], "w", encoding="utf-8", newline="\n") as f:
            f.write(content)
    return {**paths, **summary}


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


def cmd_wording(pr_url, path):
    parse_pr_url(pr_url)
    data = read_json(path)
    directory = glob.escape(os.path.dirname(path) or ".")
    names = sorted(glob.glob(os.path.join(directory, "wording-*.json")))
    for name in names:
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
    write_json(path, data)
    for name in names:
        os.remove(name)
    missing = wording_missing(data) if "findings" in data else []
    return {"path": path, "comment_lang": data.get("comment_lang"), "missing": missing}


def add_thread(pr, review_id, finding, draft, as_file):
    body = finding_block(comment_view(finding, True), draft["kind"], draft["comment_lang"], as_file)
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
    except Error as e:
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
    raise error


def post_review(pr, path, draft):
    if draft.get("posted"):
        raise Error("this review was already posted")
    view = view_for_draft(pr, draft)
    if (draft.get("url") or "").casefold() != pr.url.casefold():
        raise Error(f"{path} is not a draft of {pr.url}")
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
    if previewed and previewed != plan["verdict"]:
        raise Error(f"the preview showed {previewed}, but the verdict is now {plan['verdict']}; "
                    "preview it again")
    created = graphql(pr, ADD_REVIEW, input={"pullRequestId": view["id"],
                                             "commitOID": draft["head_sha"]})
    review_id = created["addPullRequestReview"]["pullRequestReview"]["id"]
    to_body, fallbacks = [], []
    counts = {"inline": 0, "file": 0}
    recovered = None
    try:
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
                except Error:
                    fallbacks.append(finding["id"])
            try:
                add_thread(pr, review_id, finding, draft, True)
                counts["file"] += 1
            except Error:
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
    return {
        "review_url": url,
        "event": plan["event"], "verdict": plan["verdict"], "own_pr": plan["own_pr"],
        "inline": counts["inline"], "file": counts["file"], "body": len(to_body),
        "fallbacks": fallbacks, "recovered_from": recovered,
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


def send_reply(pr, entry, viewer):
    body = safe_text(reply_text(entry, True))
    if entry["verified"]:
        body += f"\n\n<!-- cgh:verified {','.join(entry['verified'])} -->"
    if entry["kind"] == "thread":
        comment = rest_get(pr, f"repos/{pr.repo}/pulls/comments/{entry['target_id']}")
        if not belongs(pr, comment.get("pull_request_url"), "pulls"):
            raise not_on_pr(pr, entry["target_id"])
        answered = comment.get("in_reply_to_id") or entry["target_id"]
        path = f"repos/{pr.repo}/pulls/{pr.number}/comments/{answered}/replies"
    else:
        author = reply_author(pr, entry, viewer)
        if author:
            body = f"@{author} {body}"
        answered = entry["target_id"]
        path = f"repos/{pr.repo}/issues/{pr.number}/comments"
    if answered is not None:
        body += f"\n\n<!-- cgh:reply {entry['kind']} {answered} -->"
    return rest_post(pr, path, {"body": checked_size(body, "a reply")}).get("html_url")


def post_replies(pr, path, data):
    replies = validated_replies(data)
    viewer = view_pr(pr, require_open=False)["viewer"]
    urls = []
    for entry in replies:
        if entry["selected"] and not entry["posted"]:
            urls.append(send_reply(pr, entry, viewer))
            entry["posted"] = True
            write_json(path, data)
    return {"posted": len(urls), "urls": urls}


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
    return pushed_state(parse_pr_url(pr_url), commits_path)


def cmd_post(pr_url, path, commits_path):
    pr = parse_pr_url(pr_url)
    data = read_json(path)
    if commits_path:
        if "findings" in data or any(e["verified"] for e in validated_replies(data)):
            raise Error(f"--commits sends only replies that mark nothing verified: {path} holds "
                        "findings or a verified reply")
        if not pushed_state(pr, commits_path)["pushed"]:
            raise Error("the pull request does not contain the fix commits yet; push them first")
    return post_review(pr, path, data) if "findings" in data else post_replies(pr, path, data)


def cmd_comments(pr_url, tmp_dir):
    pr = parse_pr_url(pr_url)
    reviews = rest_pages(pr, f"repos/{pr.repo}/pulls/{pr.number}/reviews")
    pending = {r.get("id") for r in reviews if r.get("state") == "PENDING"}
    comments = [c for c in rest_pages(pr, f"repos/{pr.repo}/pulls/{pr.number}/comments")
                if c.get("pull_request_review_id") not in pending]
    issue_comments = rest_pages(pr, f"repos/{pr.repo}/issues/{pr.number}/comments")
    view = view_pr(pr, require_open=False)

    def author(entry):
        return (entry.get("user") or {}).get("login") or "ghost"

    answered = {(match.group(1), int(match.group(2)))
                for c in [*comments, *issue_comments] if author(c) == view["viewer"]
                for match in REPLY_RE.finditer(c.get("body") or "")}
    path = os.path.join(tmp_dir, "comments.json")
    write_json(path, {
        "review_comments": [
            {"id": c.get("id"), "in_reply_to": c.get("in_reply_to_id"), "author": author(c),
             "path": c.get("path"), "line": c.get("line") or c.get("original_line"),
             "body": c.get("body") or "",
             "answered": ("thread", c.get("in_reply_to_id") or c.get("id")) in answered}
            for c in comments],
        "reviews": [{"id": r.get("id"), "author": author(r), "state": r.get("state"),
                     "body": r.get("body") or "", "answered": ("review", r.get("id")) in answered}
                    for r in reviews if r.get("body") and r.get("id") not in pending],
        "issue_comments": [
            {"id": c.get("id"), "author": author(c), "body": c.get("body") or "",
             "answered": ("issue_comment", c.get("id")) in answered}
            for c in issue_comments],
    })
    return {"path": path, "pr_body_path": write_pr_body(tmp_dir, view)}


def cmd_fixes(pr_url, tmp_dir, document):
    pr = parse_pr_url(pr_url)
    header, _ = checked_document(pr, document)
    branch = header.get("branch")
    log = run(["git", "log", "--format=%H%x00%s", "--name-only",
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
        "head_repo":(view.get("headRepository") or {}).get("nameWithOwner"),
    }


def cmd_replies(pr_url, tmp_dir, document, lang):
    pr = parse_pr_url(pr_url)
    header, findings = checked_document(pr, document)
    labels = labels_for(lang)
    short = header["head_sha"][:SHORT_SHA]
    prior = read_json(os.path.join(tmp_dir, "prior.json"))["findings"]
    targets = {f["id"]: f["target"] for f in prior}
    replies, body_lines, body_ids, body_verified, unverified = [], [], [], [], []
    for finding in findings:
        fid, verification = finding["id"], finding["metadata"].get("Verification", "")
        target = targets.get(fid)
        if not target:
            continue
        if not verification:
            unverified.append(fid)
            continue
        note = verification.partition(" — ")[2].strip()
        verified = has_label(verification, "Verified")
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
            body_lines.append(text)
            body_ids.append(fid)
            if verified:
                body_verified.append(fid)
    if body_lines:
        replies.append({"kind": "issue", "target_id": None, "finding_ids": body_ids,
                        "body": "\n\n".join(body_lines), "verified": body_verified})
    path = os.path.join(tmp_dir, "replies.json")
    write_json(path, {"replies": replies})
    return {"path": path, "replies": len(replies), "unverified": unverified,
            "pr_body_path": write_pr_body(tmp_dir, view_pr(pr, require_open=False))}


def parser():
    top = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    commands = top.add_subparsers(dest="command", required=True)

    def command(name, *positional):
        sub = commands.add_parser(name)
        for arg in positional:
            sub.add_argument(arg)
        return sub

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
    command("fixes", "pr_url", "tmp_dir", "document")
    command("pushed", "pr_url", "commits")
    replies = command("replies", "pr_url", "tmp_dir", "document")
    replies.add_argument("--lang", required=True, choices=sorted(LABELS))
    command("preview", "pr_url", "path")
    post = command("post", "pr_url", "path")
    post.add_argument("--commits")
    return top


def dispatch(args):
    if args.command == "prior":
        return cmd_prior(args.pr_url, args.tmp_dir, args.kind, args.document, args.trust)
    if args.command == "draft":
        return cmd_draft(args.pr_url, args.tmp_dir, args.document, args.kind, args.lang,
                         args.prior_doc)
    if args.command == "wording":
        return cmd_wording(args.pr_url, args.path)
    if args.command == "comments":
        return cmd_comments(args.pr_url, args.tmp_dir)
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
