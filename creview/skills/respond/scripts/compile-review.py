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

`docs_only` is true only when there is at least one fix, each status `id` has an
item in <tmp_dir>/targets.jsonl (read as one JSON object), and every item there
counts as a fix of documentation text alone:
- An item whose `stages` holds "docs" and not "code" counts.
- An item whose `stages` holds "code" counts only when its `text_only` is the
  boolean true and at least one status carries its `id`, each with `text_only`
  the boolean true.
- Any other item does not count.
It is false when targets.jsonl is missing, unreadable, or malformed, or when an
item is not an object with a string `id` and a `stages` list.
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


def target_is_text_only(item, status_flags):
    if "code" in item["stages"]:
        return item.get("text_only") is True and bool(status_flags) and all(status_flags)
    return "docs" in item["stages"]


def docs_text_only(tmp_dir, statuses):
    try:
        with open(os.path.join(tmp_dir, "targets.jsonl"), encoding="utf-8") as f:
            targets = json.load(f)
    except (OSError, ValueError):
        return False
    items = targets.get("items") if isinstance(targets, dict) else None
    if not isinstance(items, list) or not all(
            isinstance(item, dict) and isinstance(item.get("id"), str)
            and isinstance(item.get("stages"), list)
            for item in items):
        return False
    item_ids = {item["id"] for item in items}
    status_flags = {}
    for status in statuses:
        if not isinstance(status["id"], str) or status["id"] not in item_ids:
            return False
        status_flags.setdefault(status["id"], []).append(status.get("text_only") is True)
    return all(target_is_text_only(item, status_flags.get(item["id"], [])) for item in items)


def main():
    if len(sys.argv) != 3:
        sys.exit(f"Usage: {sys.argv[0]} <tmp_dir> <document_path>")
    tmp_dir, document_path = sys.argv[1:3]

    statuses = []
    events = []
    verdicts = {"Maintain": 0, "Alternative": 0}
    for status_path in sorted(glob.glob(os.path.join(tmp_dir, "statuses", "*.jsonl"))):
        with open(status_path, encoding="utf-8") as f:
            status = json.load(f)
        statuses.append(status)
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

    print(json.dumps({
        "fixed_count": fixed,
        "code_changed": fixed > 0,
        "docs_only": fixed > 0 and docs_text_only(tmp_dir, statuses),
        "summary_line": summary_line,
        "maintain": verdicts["Maintain"],
        "alternative": verdicts["Alternative"],
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
