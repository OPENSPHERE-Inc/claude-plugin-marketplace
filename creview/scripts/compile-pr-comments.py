#!/usr/bin/env python3
"""compile-pr-comments.py — Build a review document from the findings extracted
from a pull request's comments.

Usage:
    python3 compile-pr-comments.py <tmp_dir> <document_path> --branch <branch|(none)>
        --trust <on|off> --lang <en|ja>

Reads <tmp_dir>/pr.json, which gh-pr.py fetch wrote, and for each
<tmp_dir>/pr-comments/batch-<n>.json the file extract-<n>.jsonl next to it:
    {"findings": [{"severity": "Critical" | "Major" | "Minor",
                   "categories": ["..."], "location": "path:line" | "path" | "PR",
                   "authors": ["..."], "description": "..."}]}

Writes <document_path> in the format of /creview:start's review document, with
findings in severity, path, and line order, empty metadata markers, and the PR,
Branch, Trust, and Source header bullets. Line breaks in a value are folded, and a
description can neither start a Markdown block nor open an HTML comment, so comment
text cannot pass for the document's structure. It merges no findings, so the same
finding from two batches stays as two. --lang selects the language of the labels the
script writes; finding text stays as extracted. With no findings it writes nothing.

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
LOCATION_RE = re.compile(r"(.*):([0-9]+)")
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
    return " ".join(str(value).split())


def names(value, what):
    if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
        raise Invalid(f"{what} is not a list of strings")
    return [one_line(v) for v in value if one_line(v)]


def description_text(value):
    text = one_line(value).replace("<!--", "&lt;!--")
    if BLOCK_START_RE.match(text):
        return "\\" + text
    item = ORDERED_ITEM_RE.fullmatch(text)
    # A backslash before a digit would print as a backslash.
    return f"{item.group(1)}\\{item.group(2)}" if item else text


def read_finding(entry):
    if not isinstance(entry, dict):
        raise Invalid("a finding is not an object")
    if entry.get("severity") not in [name for name, _ in SEVERITIES]:
        raise Invalid(f"severity {entry.get('severity')!r}")
    location = one_line(entry.get("location") or "").replace("`", "")
    authors = names(entry.get("authors"), "authors")
    text = description_text(entry.get("description") or "")
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
    return [read_finding(entry) for entry in data["findings"]]


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


def render(findings, pr, args):
    labels = LABELS[args.lang]
    authors = list(dict.fromkeys(a for f in findings for a in f["authors"]))
    pr_ref = f"{pr['url']} (head {pr['head_sha']}, base {pr['merge_base']})"
    scope = labels["scope_value"].format(number=pr["number"])
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


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("tmp_dir")
    parser.add_argument("document_path")
    parser.add_argument("--branch", required=True, type=branch_arg)
    parser.add_argument("--trust", required=True, choices=("on", "off"))
    parser.add_argument("--lang", required=True, choices=sorted(LABELS))
    args = parser.parse_args()

    try:
        findings = read_extracts(args.tmp_dir)
        with open(os.path.join(args.tmp_dir, "pr.json"), encoding="utf-8") as f:
            pr = json.load(f)
        counts = dict.fromkeys((name for name, _ in SEVERITIES), 0)
        if findings:
            text, counts = render(findings, pr, args)
            with open(args.document_path, "w", encoding="utf-8", newline="\n") as f:
                f.write(text)
    except (OSError, ValueError, KeyError, Invalid) as e:
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
