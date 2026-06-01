#!/usr/bin/env python3
"""compile-review.py (respond) — Aggregate fix statuses into events.jsonl and
persist the status metadata into the review document via render-review.py.

Usage:
    python3 compile-review.py <tmp_dir> <document_path>

Reads <tmp_dir>/statuses/*.json (each carries a precomputed `memo_value` and a
`verdict` of Maintain | Alternative), writes <tmp_dir>/events.jsonl (empty when
no fixes), runs the sibling render-review.py, and prints a result JSON object to
stdout: {"fixed_count", "code_changed", "summary_line", "maintain", "alternative"}.
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

    events = []
    verdicts = {"Maintain": 0, "Alternative": 0}
    for status_path in sorted(glob.glob(os.path.join(tmp_dir, "statuses", "*.json"))):
        with open(status_path, encoding="utf-8") as f:
            status = json.load(f)
        events.append({"id": status["id"], "field": "status", "value": status["memo_value"]})
        if status.get("verdict") in verdicts:
            verdicts[status["verdict"]] += 1

    events_path = os.path.join(tmp_dir, "events.jsonl")
    with open(events_path, "w", encoding="utf-8", newline="\n") as f:
        for event in events:
            f.write(json.dumps(event, ensure_ascii=False) + "\n")
    subprocess.run([sys.executable, RENDER_REVIEW, document_path, events_path, document_path], check=True)

    fixed = len(events)
    breakdown = " + ".join(f"{n} {name}" for name, n in verdicts.items() if n)
    summary_line = f"{fixed} fixed ({breakdown})" if breakdown else f"{fixed} fixed"

    print(json.dumps({
        "fixed_count": fixed,
        "code_changed": fixed > 0,
        "summary_line": summary_line,
        "maintain": verdicts["Maintain"],
        "alternative": verdicts["Alternative"],
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
