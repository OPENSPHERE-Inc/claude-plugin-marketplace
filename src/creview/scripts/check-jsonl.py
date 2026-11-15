#!/usr/bin/env python3
"""check-jsonl.py — Validate that a .jsonl file an agent wrote is JSON Lines.

Usage:
    python3 <path>/check-jsonl.py <file> [<file> ...]

Accepts a file each non-blank line of which is one JSON object on its own. A line
ends at a line feed, with one carriage return before it removed; blank lines are
skipped. A file with no non-blank line, a line that does not parse, and a line that
holds an array or a scalar are errors, and so is one JSON value written across
several lines, whose message says to write it on one line. Only the syntax is
checked, not the schema. Prints one ok line per file; on an error prints
<file>:<line>:<col>: <message> to stderr and exits 1.
"""

from __future__ import annotations

import json
import sys


def plural(n, word):
    return f"{n} {word}" if n == 1 else f"{n} {word}s"


def check(path):
    """Return the number of lines parsed, or raise ValueError with a located message."""
    try:
        with open(path, encoding="utf-8", newline="") as f:
            text = f.read()
    except OSError as exc:
        raise ValueError(f"{path}: {exc.strerror}")
    lines = [(n, line[:-1] if line.endswith("\r") else line)
             for n, line in enumerate(text.split("\n"), 1)]
    lines = [(n, line) for n, line in lines if line.strip()]
    if not lines:
        raise ValueError(f"{path}:1:1: file is empty")

    for lineno, line in lines:
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            try:
                json.loads(text)
            except json.JSONDecodeError:
                raise ValueError(f"{path}:{lineno}:{exc.colno}: {exc.msg}") from None
            raise ValueError(f"{path}:1:1: one JSON value spans {plural(len(lines), 'line')}; "
                             "write each value on one line") from None
        if not isinstance(value, dict):
            raise ValueError(f"{path}:{lineno}:1: the line is not a JSON object")
    return len(lines)


def main():
    if len(sys.argv) < 2:
        sys.exit(f"Usage: {sys.argv[0]} <file> [<file> ...]")
    failed = 0
    for path in sys.argv[1:]:
        try:
            count = check(path)
        except ValueError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            failed = 1
        else:
            print(f"ok {path}: {plural(count, 'line')}")
    sys.exit(failed)


if __name__ == "__main__":
    main()
