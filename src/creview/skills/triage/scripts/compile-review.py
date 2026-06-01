#!/usr/bin/env python3
"""compile-review.py (triage) — Aggregate triage / estimate decisions into
events.jsonl and persist the triage / estimate metadata into the review
document via render-review.py.

Usage:
    python3 compile-review.py <tmp_dir> <document_path>

Reads <tmp_dir>/triage.json and <tmp_dir>/estimates/*.json (each carries a
precomputed `memo_value`), writes <tmp_dir>/events.jsonl, runs the sibling
render-review.py, and prints a result JSON object to stdout:
    {"fixed_count", "code_changed", "summary_line",
     "will_fix", "wont_fix", "maintain", "alternative", "downgrade"}
`status` / `verification` are out of scope (set by respond / resolve).
"""

import glob
import json
import os
import subprocess
import sys

RENDER_REVIEW = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "..", "..", "..", "scripts", "render-review.py",
)


def main():
    if len(sys.argv) != 3:
        sys.exit(f"Usage: {sys.argv[0]} <tmp_dir> <document_path>")
    tmp_dir, document_path = sys.argv[1:3]

    with open(os.path.join(tmp_dir, "triage.json"), encoding="utf-8") as f:
        triage = json.load(f)

    events = [
        {"id": item["id"], "field": "triage", "value": item["memo_value"]}
        for item in triage.get("items", [])
    ]

    verdicts = {"Maintain": 0, "Alternative": 0, "Downgrade": 0}
    for est_path in sorted(glob.glob(os.path.join(tmp_dir, "estimates", "*.json"))):
        with open(est_path, encoding="utf-8") as f:
            est = json.load(f)
        events.append({"id": est["id"], "field": "estimate", "value": est["memo_value"]})
        if est.get("verdict") in verdicts:
            verdicts[est["verdict"]] += 1

    events_path = os.path.join(tmp_dir, "events.jsonl")
    with open(events_path, "w", encoding="utf-8", newline="\n") as f:
        for event in events:
            f.write(json.dumps(event, ensure_ascii=False) + "\n")
    subprocess.run([sys.executable, RENDER_REVIEW, document_path, events_path, document_path], check=True)

    will_fix = triage.get("will_fix_count", 0)
    wont_fix = triage.get("wontfix_count", 0)
    breakdown = " + ".join(f"{n} {name}" for name, n in verdicts.items() if n)
    will_fix_part = f"{will_fix} Will Fix ({breakdown})" if breakdown else f"{will_fix} Will Fix"
    summary_line = f"{will_fix + wont_fix} triaged: {will_fix_part}, {wont_fix} Won't Fix"

    print(json.dumps({
        "fixed_count": 0,
        "code_changed": False,
        "summary_line": summary_line,
        "will_fix": will_fix,
        "wont_fix": wont_fix,
        "maintain": verdicts["Maintain"],
        "alternative": verdicts["Alternative"],
        "downgrade": verdicts["Downgrade"],
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
