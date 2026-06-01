#!/usr/bin/env python3
"""compile-review.py (resolve) — Build the verification report and events.jsonl
from verification results, and persist the verification metadata into the review
document via render-review.py.

Usage:
    python compile-review.py <tmp_dir> <document_path>

Reads <tmp_dir>/verifications/*.json (each carries severity / trailing_field /
outcome / reason / memo_value / feedback_detail), writes the human-facing report
<tmp_dir>/resolve-summary.md and <tmp_dir>/events.jsonl (verification events,
excluding Unresolved), runs the sibling render-review.py, and prints a result
JSON object to stdout: {"summary_path", "summary_line", "resolved_count",
"feedback_count", "unresolved_count"}.
"""

import datetime
import glob
import json
import os
import subprocess
import sys

RENDER_REVIEW = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "..", "..", "..", "scripts", "render-review.py",
)
SEVERITY_RANK = {"Critical": 0, "Major": 1, "Minor": 2, "Info": 3}


def cell(value):
    """Make a value safe for a single-line Markdown table cell."""
    return str(value if value is not None else "").replace("|", "\\|").replace("\n", " ").strip()


def main():
    if len(sys.argv) != 3:
        sys.exit(f"Usage: {sys.argv[0]} <tmp_dir> <document_path>")
    tmp_dir, document_path = sys.argv[1:3]

    verifications = []
    for path in glob.glob(os.path.join(tmp_dir, "verifications", "*.json")):
        with open(path, encoding="utf-8") as f:
            verifications.append(json.load(f))
    verifications.sort(key=lambda v: (SEVERITY_RANK.get(v.get("severity"), 9), v.get("id", "")))

    resolved = [v for v in verifications if v.get("outcome") == "Resolved"]
    feedback = [v for v in verifications if v.get("outcome") == "Feedback"]
    unresolved = [v for v in verifications if v.get("outcome") == "Unresolved"]

    lines = [
        "# Review Verification Report",
        "",
        f"**Review document: {document_path}**",
        f"**Verification date: {datetime.date.today().isoformat()}**",
        "",
        "## Verification Results",
    ]
    for title, rows, last_col in (
        ("Resolved", resolved, "Decision"),
        ("Feedback Required", feedback, "Issue"),
        ("Unresolved", unresolved, "Memo"),
    ):
        lines += ["", f"### {title}", "", f"| # | Severity | Trailing Field | {last_col} |", "| --- | --- | --- | --- |"]
        for v in rows:
            lines.append(f"| {cell(v.get('id'))} | {cell(v.get('severity'))} | {cell(v.get('trailing_field'))} | {cell(v.get('reason'))} |")
    lines += [
        "",
        "## Summary",
        "",
        f"- Findings verified: {len(verifications)}",
        f"- Resolved: {len(resolved)}",
        f"- Feedback Required: {len(feedback)}",
        f"- Unresolved: {len(unresolved)}",
    ]
    if feedback:
        lines += ["", "## Feedback Details"]
        for v in feedback:
            detail = v.get("feedback_detail") or {}
            lines += [
                "",
                f"### {v.get('id')} — Feedback",
                "",
                f"- **Original finding:** {detail.get('description', '')}",
                f"- **Trailing field:** {v.get('trailing_field', '')}",
                f"- **Actual state:** {detail.get('current_state', '')}",
                f"- **Issue:** {detail.get('issue', '')}",
                f"- **Suggestion:** {detail.get('suggestion', '')}",
                "",
                "---",
            ]

    summary_path = os.path.join(tmp_dir, "resolve-summary.md")
    with open(summary_path, "w", encoding="utf-8", newline="") as f:
        f.write("\n".join(lines) + "\n")

    events_path = os.path.join(tmp_dir, "events.jsonl")
    with open(events_path, "w", encoding="utf-8", newline="\n") as f:
        for v in verifications:
            if v.get("outcome") == "Unresolved":
                continue
            f.write(json.dumps({"id": v["id"], "field": "verification", "value": v["memo_value"]}, ensure_ascii=False) + "\n")
    subprocess.run([sys.executable, RENDER_REVIEW, document_path, events_path, document_path], check=True)

    summary_line = f"{len(resolved)} resolved"
    if feedback:
        # feedback is already sorted by severity; show the first few ids, capped.
        fb_ids = [v.get("id", "") for v in feedback]
        shown = ", ".join(fb_ids[:5]) + (", ..." if len(fb_ids) > 5 else "")
        summary_line += f", {len(feedback)} feedback ({shown})"
    if unresolved:
        summary_line += f", {len(unresolved)} unresolved"

    print(json.dumps({
        "summary_path": summary_path,
        "summary_line": summary_line,
        "resolved_count": len(resolved),
        "feedback_count": len(feedback),
        "unresolved_count": len(unresolved),
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
