#!/usr/bin/env python3
"""scratch-guard.py — single implementation of the .claude/tmp/ containment check.

Usage: python3 scratch-guard.py [-p|-w] <path>

Prints the normalized repo-relative path on stdout and exits 0 when <path>
stays under .claude/tmp/. Exits 1 on any violation (message on stderr).
With -p the parent directory is additionally resolved to its physical path
and re-checked, so a symlinked directory component cannot escape; exits 3
when the parent directory does not exist. With -w the final component is
resolved as well (following even a dangling symlink), so a symlinked entry
cannot redirect a file write outside .claude/tmp/; use it for write targets.
"""

import os
import sys
from pathlib import Path

SCRATCH_ROOT = Path(".claude/tmp")


def fail(message):
    print(f"Error: {message}", file=sys.stderr)
    return 1


def cwd_candidates():
    # $PWD (exported by shells) keeps the logical cwd with symlinks
    # unresolved, matching how shell callers spell absolute paths;
    # Path.cwd() is the physical form.
    yield Path.cwd()
    env_pwd = os.environ.get("PWD", "")
    if env_pwd:
        pwd = Path(env_pwd)
        if pwd.is_absolute():
            yield pwd


def guard(mode, raw):
    target = Path(raw)

    # Convert an absolute path to repo-relative; reject anything outside the CWD.
    if target.is_absolute() or raw.startswith(("/", "\\")):
        for cwd in cwd_candidates():
            try:
                target = target.relative_to(cwd)
                break
            except ValueError:
                continue
        else:
            return fail(f"absolute path is outside the current project: {raw}")

    parts = target.parts
    if ".." in parts:
        return fail(f"path containing '..' is not allowed: {raw}")
    if parts[: len(SCRATCH_ROOT.parts)] != SCRATCH_ROOT.parts:
        return fail(f"path is not under {SCRATCH_ROOT.as_posix()}/: {raw}")
    if len(parts) <= len(SCRATCH_ROOT.parts):
        return fail(f"the bare {SCRATCH_ROOT.as_posix()}/ root is not allowed: {raw}")

    if mode is not None:
        # Resolve physical (symlink-free) paths so a symlinked component
        # cannot escape SCRATCH_ROOT.
        try:
            resolved_parent = target.parent.resolve(strict=True)
        except FileNotFoundError:
            return 3
        except OSError:
            return fail(f"cannot resolve the parent directory: {raw}")
        if not resolved_parent.is_dir():
            return fail(f"parent directory exists but cannot be entered: {raw}")
        try:
            scratch_real = SCRATCH_ROOT.resolve(strict=True)
        except OSError:
            return fail(f"cannot resolve {SCRATCH_ROOT.as_posix()}: {raw}")
        if not resolved_parent.is_relative_to(scratch_real):
            return fail(f"resolved path escapes {SCRATCH_ROOT.as_posix()}/: {raw}")
        if mode == "-w":
            try:
                resolved_target = target.resolve()
            except OSError:
                return fail(f"cannot resolve the write target: {raw}")
            if not resolved_target.is_relative_to(scratch_real):
                return fail(f"resolved path escapes {SCRATCH_ROOT.as_posix()}/: {raw}")

    print(target.as_posix())
    return 0


def main(argv):
    mode = None
    args = list(argv)
    if args and args[0] in ("-p", "-w"):
        mode = args.pop(0)
    if len(args) != 1 or not args[0]:
        return fail("a path argument is required")
    return guard(mode, args[0])


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
