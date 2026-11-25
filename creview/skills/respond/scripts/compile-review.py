#!/usr/bin/env python3
"""compile-review.py (respond) — Aggregate fix statuses into events.jsonl and
persist the status metadata into the review document via render-review.py.

Usage:
    python3 compile-review.py <tmp_dir> <document_path>

Reads <tmp_dir>/statuses/*.jsonl (each carries a precomputed `memo_value` and a
`verdict` of Maintain | Alternative), writes <tmp_dir>/events.jsonl (empty when
no fixes), runs the sibling render-review.py, and prints a result JSON object to
stdout: {"fixed_count", "code_changed", "docs_only", "summary_line", "maintain",
"alternative"}.

`docs_only` is true only when there is at least one fix, every item in
<tmp_dir>/targets.jsonl (read as one JSON object) has a `stages` list that holds
"docs" and not "code", and each status `id` has an item there. It is false when
targets.jsonl is missing, unreadable, or malformed.
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
# json.dumps leaves these raw under ensure_ascii=False, and str.splitlines() splits a line at
# each of them.
LINE_SEPARATORS = {ord(c): f"\\u{ord(c):04x}" for c in "\u2028\u2029\u0085"}


def json_line(value):
    return json.dumps(value, ensure_ascii=False).translate(LINE_SEPARATORS)


def docs_only_target_ids(tmp_dir):
    try:
        with open(os.path.join(tmp_dir, "targets.jsonl"), encoding="utf-8") as f:
            targets = json.load(f)
    except (OSError, ValueError):
        return set()
    items = targets.get("items") if isinstance(targets, dict) else None
    if not isinstance(items, list) or not all(
            isinstance(item, dict) and isinstance(item.get("id"), str)
            and isinstance(item.get("stages"), list)
            and "docs" in item["stages"] and "code" not in item["stages"]
            for item in items):
        return set()
    return {item["id"] for item in items}


def main():
    if len(sys.argv) != 3:
        sys.exit(f"Usage: {sys.argv[0]} <tmp_dir> <document_path>")
    tmp_dir, document_path = sys.argv[1:3]

    events = []
    verdicts = {"Maintain": 0, "Alternative": 0}
    for status_path in sorted(glob.glob(os.path.join(tmp_dir, "statuses", "*.jsonl"))):
        with open(status_path, encoding="utf-8") as f:
            status = json.load(f)
        events.append({"id": status["id"], "field": "status", "value": status["memo_value"]})
        if status.get("verdict") in verdicts:
            verdicts[status["verdict"]] += 1

    events_path = os.path.join(tmp_dir, "events.jsonl")
    with open(events_path, "w", encoding="utf-8", newline="\n") as f:
        for event in events:
            f.write(json_line(event) + "\n")
    subprocess.run([sys.executable, RENDER_REVIEW, document_path, events_path, document_path], check=True)

    fixed = len(events)
    breakdown = " + ".join(f"{n} {name}" for name, n in verdicts.items() if n)
    summary_line = f"{fixed} fixed ({breakdown})" if breakdown else f"{fixed} fixed"
    docs_ids = docs_only_target_ids(tmp_dir)

    print(json.dumps({
        "fixed_count": fixed,
        "code_changed": fixed > 0,
        "docs_only": fixed > 0 and all(event["id"] in docs_ids for event in events),
        "summary_line": summary_line,
        "maintain": verdicts["Maintain"],
        "alternative": verdicts["Alternative"],
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
