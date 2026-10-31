#!/usr/bin/env python3
"""compile-pr-comments.py — Build a review document from the findings extracted
from a pull request's comments.

Usage:
    python3 compile-pr-comments.py <tmp_dir> <document_path> --pr-url <url> --head <sha>
        --merge-base <sha> --branch <branch|(none)> --trust <on|off> --lang <en|ja>

Reads, for each <tmp_dir>/pr-comments/batch-<n>.json, the file extract-<n>.jsonl next
to it:
    {"findings": [{"severity": "Critical" | "Major" | "Minor",
                   "categories": ["..."], "location": "path:line" | "path" | "PR",
                   "authors": ["..."], "description": "..."}]}

Writes <document_path> in the format of /creview:start's review document, with
findings in severity, path, and line order, empty metadata markers, and the PR,
Branch, Trust, and Source header bullets. The PR, Branch, Trust, and Scope bullets
take their values from the arguments alone: the compilers that write the extract files
can also write under <tmp_dir>. The Reviewers bullet lists the extract files' authors.
Line breaks in a value are folded, no value can open an HTML comment, and a
description cannot start a Markdown block, so comment text cannot pass for the
document's structure. A location that points outside the repository or into a .git
directory, or that holds a character other than a letter, a digit, a backslash, or one
of . _ - + @ / ( ) [ ] $ %, becomes PR. It merges no findings, so the same finding from
two batches stays as two. --lang selects the language of the labels the script writes;
finding text stays as extracted. With no findings it writes nothing.

Prints {"doc_path", "findings_total", "severity_counts"}; doc_path is null without
findings. A missing or malformed extract file exits 1, naming every such file on
stderr, and writes nothing.
"""

import argparse
import datetime
import glob
import json
import os
import re
import sys

SEVERITIES = (("Critical", "C"), ("Major", "M"), ("Minor", "mi"))
# What starts a Markdown block at the beginning of a paragraph. Inline markup such as `code`
# or **bold** is left out: a backslash before it would break it.
BLOCK_START_RE = re.compile(
    r"#{1,6}(?:\s|$)|[-+*](?:\s|$)|>|`{3}|~{3}|([-*_])\s*(?:\1\s*){2,}$|<[A-Za-z/!?]"
)
ORDERED_ITEM_RE = re.compile(r"([0-9]{1,9})([.)](?:\s|$).*)")
BRANCH_RE = re.compile(r"[\w./+@-]+")
PR_URL_RE = re.compile(
    r"https://[A-Za-z0-9.-]+(?::[0-9]+)?/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+/pull/([0-9]+)"
)
SHA_RE = re.compile(r"[0-9a-f]{40}(?:[0-9a-f]{24})?")
LOCATION_RE = re.compile(r"(.*):([0-9]+)")
# A repository path's characters, route names such as app/(group)/[slug]/a.$b.tsx included.
PATH_RE = re.compile(r"[\w.+@/\\()\[\]$%-]*")
ROOTED_RE = re.compile(r"(?:^|[(\[])[/\\$%]")
LABELS = {
    "en": {
        "title": "Pull Request Comment Review Report",
        "date": "Date",
        "scope": "Scope",
        "scope_value": "Comments of pull request #{number}",
        "reviewers": "Reviewers",
        "finding": "Finding",
        "no_findings": "No findings",
        "summary": "Summary",
        "total": "Total",
        "total_value": "{findings} findings from {reviewers} reviewers",
    },
    "ja": {
        "title": "プルリクエストコメントレビューレポート",
        "date": "日付",
        "scope": "対象範囲",
        "scope_value": "プルリクエスト #{number} のコメント",
        "reviewers": "レビュアー",
        "finding": "指摘",
        "no_findings": "指摘なし",
        "summary": "サマリー",
        "total": "合計",
        "total_value": "{findings} 件（レビュアー {reviewers} 名）",
    },
}


class Invalid(Exception):
    pass


def one_line(value):
    return " ".join(value.split()).replace("<!--", "&lt;!--")


def string_field(entry, field):
    value = entry.get(field)
    if not isinstance(value, str):
        raise Invalid(f"{field} is not a string")
    return value


def repository_location(location):
    # Later phases read the path a location names, and any commenter can name any path.
    m = LOCATION_RE.fullmatch(location)
    path = m.group(1) if m else location
    parts = [part.lower().strip("()[]") for part in re.split(r"[\\/]", path)]
    # Windows reads .git. as .git.
    if (not PATH_RE.fullmatch(path) or ROOTED_RE.search(path) or ".." in parts
            or ".git" in {part.rstrip(".") for part in parts}):
        return "PR"
    return location


def names(value, what):
    if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
        raise Invalid(f"{what} is not a list of strings")
    return [one_line(v) for v in value if one_line(v)]


def description_text(value):
    text = one_line(value)
    if BLOCK_START_RE.match(text):
        return "\\" + text
    item = ORDERED_ITEM_RE.fullmatch(text)
    # A backslash before a digit would print as a backslash.
    return f"{item.group(1)}\\{item.group(2)}" if item else text


def read_finding(entry):
    if not isinstance(entry, dict):
        raise Invalid("a finding is not an object")
    if entry.get("severity") not in [name for name, _ in SEVERITIES]:
        raise Invalid("invalid severity")
    location = repository_location(one_line(string_field(entry, "location").replace("`", "")))
    authors = names(entry.get("authors"), "authors")
    text = description_text(string_field(entry, "description"))
    if not location or not authors or not text:
        raise Invalid("a finding lacks its location, authors, or description")
    categories = [re.sub(r"[/\[\]]", " ", c).strip()
                  for c in names(entry.get("categories", []), "categories")]
    return {"severity": entry["severity"], "categories": [c for c in categories if c],
            "location": location, "authors": authors, "description": text}


def read_extract(path):
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict) or not isinstance(data.get("findings"), list):
        raise Invalid("it has no findings list")
    findings = [read_finding(entry) for entry in data["findings"]]
    try:
        json.dumps(findings, ensure_ascii=False).encode("utf-8")
    except UnicodeEncodeError:
        raise Invalid("a value cannot be encoded as UTF-8") from None
    return findings


def batch_number(path):
    return int(re.search(r"batch-([0-9]+)\.json$", path).group(1))


def read_extracts(tmp_dir):
    batches = glob.glob(os.path.join(glob.escape(tmp_dir), "pr-comments", "batch-*.json"))
    findings, errors = [], []
    for batch in sorted(batches, key=batch_number):
        path = os.path.join(os.path.dirname(batch), f"extract-{batch_number(batch)}.jsonl")
        try:
            findings += read_extract(path)
        except (OSError, ValueError, Invalid) as e:
            errors.append(f"{os.path.basename(path)}: {e}")
    if errors:
        raise Invalid("; ".join(errors))
    return findings


def location_key(finding):
    location = finding["location"]
    if location == "PR":
        return (0, "", 0)
    m = LOCATION_RE.fullmatch(location)
    return (1, m.group(1), int(m.group(2))) if m else (1, location, 0)


def render(findings, args):
    labels = LABELS[args.lang]
    authors = list(dict.fromkeys(a for f in findings for a in f["authors"]))
    pr_ref = f"{args.pr_url} (head {args.head}, base {args.merge_base})"
    scope = labels["scope_value"].format(number=PR_URL_RE.fullmatch(args.pr_url).group(1))
    lines = [f"# {labels['title']}", "",
             f"- **{labels['date']}:** {datetime.date.today().isoformat()}",
             f"- **PR:** {pr_ref}"]
    if args.branch != "(none)":
        lines.append(f"- **Branch:** {args.branch}")
    lines += [f"- **Trust:** {args.trust}", "- **Source:** pr-comments",
              f"- **{labels['scope']}:** {scope}",
              f"- **{labels['reviewers']}:** {', '.join(authors)}", ""]

    counts = {}
    for severity, prefix in SEVERITIES:
        group = sorted((f for f in findings if f["severity"] == severity), key=location_key)
        counts[severity] = len(group)
        lines += [f"## {severity}", ""]
        if not group:
            lines += [labels["no_findings"], "", "---", ""]
        for n, finding in enumerate(group, 1):
            fid = f"{prefix}-{n}"
            bracket = f" [{'/'.join(finding['categories'])}]" if finding["categories"] else ""
            lines += [
                f"### {fid} — `{finding['location']}`{bracket}", "",
                f"- **{labels['reviewers']}:** {', '.join(finding['authors'])}", "",
                f"**{labels['finding']}:**", "",
                finding["description"], "",
                f"<!-- METADATA({fid}) -->", f"<!-- /METADATA({fid}) -->", "",
                "---", "",
            ]
    lines += ["## Info", "", labels["no_findings"], "", "---", "",
              f"## {labels['summary']}", ""]
    lines += [f"- **{severity}:** {counts[severity]}" for severity, _ in SEVERITIES]
    lines += ["- **Info:** 0", f"- **{labels['total']}:** "
              + labels["total_value"].format(findings=len(findings), reviewers=len(authors)), ""]
    return "\n".join(lines), counts


def branch_arg(value):
    if value != "(none)" and not BRANCH_RE.fullmatch(value):
        raise argparse.ArgumentTypeError(f"invalid branch name: {value!r}")
    return value


def pr_url_arg(value):
    if not PR_URL_RE.fullmatch(value):
        raise argparse.ArgumentTypeError(f"invalid pull request URL: {value!r}")
    return value


def sha_arg(value):
    if not SHA_RE.fullmatch(value):
        raise argparse.ArgumentTypeError(f"invalid commit: {value!r}")
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("tmp_dir")
    parser.add_argument("document_path")
    parser.add_argument("--pr-url", required=True, type=pr_url_arg)
    parser.add_argument("--head", required=True, type=sha_arg)
    parser.add_argument("--merge-base", required=True, type=sha_arg)
    parser.add_argument("--branch", required=True, type=branch_arg)
    parser.add_argument("--trust", required=True, choices=("on", "off"))
    parser.add_argument("--lang", required=True, choices=sorted(LABELS))
    args = parser.parse_args()

    try:
        findings = read_extracts(args.tmp_dir)
        counts = dict.fromkeys((name for name, _ in SEVERITIES), 0)
        if findings:
            text, counts = render(findings, args)
            with open(args.document_path, "w", encoding="utf-8", newline="\n") as f:
                f.write(text)
    except (OSError, ValueError, Invalid) as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    print(json.dumps({
        "doc_path": args.document_path if findings else None,
        "findings_total": len(findings),
        "severity_counts": {name.lower(): counts[name] for name, _ in SEVERITIES},
    }))
    return 0


if __name__ == "__main__":
    sys.exit(main())
