#!/usr/bin/env python3
"""check-jsonl.py — Validate the JSON syntax of a file a sub-agent wrote.

Usage:
    python3 <path>/check-jsonl.py <file> [<file> ...]

Accepts either shape this workflow uses: the whole file as one JSON value (what
a sub-agent writes), or one JSON value per non-blank line (events.jsonl). Prints
one ok line per file; on a syntax error prints <file>:<line>:<col>: <message> to
stderr and exits 1.
"""

from __future__ import annotations

import json
import sys


def check(path):
    """Return a description of the shape parsed, or raise ValueError with a located message."""
    try:
        with open(path, encoding="utf-8") as f:
            text = f.read()
    except OSError as exc:
        raise ValueError(f"{path}: {exc.strerror}")
    if not text.strip():
        raise ValueError(f"{path}:1:1: file is empty")

    whole_err = None
    try:
        json.loads(text)
        return "1 object"
    except json.JSONDecodeError as exc:
        whole_err = exc

    lines = [(n, line) for n, line in enumerate(text.splitlines(), 1) if line.strip()]
    errors = []
    for lineno, line in lines:
        try:
            json.loads(line)
        except json.JSONDecodeError as exc:
            errors.append((lineno, exc))
    if not errors:
        return f"{len(lines)} lines"

    # Neither shape parses. A one-line file can only have meant one object, so its
    # whole-file error is the accurate one; otherwise report the first bad line.
    if len(lines) == 1:
        raise ValueError(f"{path}:{whole_err.lineno}:{whole_err.colno}: {whole_err.msg}")
    lineno, exc = errors[0]
    raise ValueError(f"{path}:{lineno}:{exc.colno}: {exc.msg}")


def main():
    if len(sys.argv) < 2:
        sys.exit(f"Usage: {sys.argv[0]} <file> [<file> ...]")
    failed = 0
    for path in sys.argv[1:]:
        try:
            shape = check(path)
        except ValueError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            failed = 1
        else:
            print(f"ok {path}: {shape}")
    sys.exit(failed)


if __name__ == "__main__":
    main()
