#!/usr/bin/env python3
"""scratch-guard.py — single implementation of the .claude/tmp/ containment check.

Usage: python3 scratch-guard.py [-p|-w] <path>

Prints the normalized path on stdout and exits 0 when <path> stays under
.claude/tmp/ of the current directory (printed repo-relative) or, for an
absolute path outside the current directory, under .claude/tmp/ of another
working tree of the same repository (printed absolute). Exits 1 on any
violation (message on stderr).
With -p the parent directory is additionally resolved to its physical path
and re-checked, so a symlinked directory component cannot escape; exits 3
when the parent directory does not exist and its deepest existing ancestor
resolves inside .claude/tmp/ (an ancestor resolving outside exits 1, so a
follow-up mkdir -p cannot escape). With -w the final component is
resolved as well (following even a dangling symlink), so a symlinked entry
cannot redirect a file write outside .claude/tmp/; use it for write targets.
"""

import os
import subprocess
import sys
from pathlib import Path

SCRATCH_ROOT = Path(".claude/tmp")


def fail(message):
    print(f"Error: {message}", file=sys.stderr)
    return 1


def to_windows_drive_path(raw):
    # Git Bash spells Windows absolute paths as /<drive>/rest; native Windows
    # Python does not treat that as absolute. Rewrite it to <DRIVE>:/rest.
    # No-op off Windows and on paths that are not in that form.
    if os.name != "nt":
        return raw
    if len(raw) >= 2 and raw[0] == "/" and raw[1].isalpha():
        if len(raw) == 2 or raw[2] == "/":
            return f"{raw[1].upper()}:{raw[2:]}"
    return raw


def cwd_candidates():
    # $PWD (exported by shells) keeps the logical cwd with symlinks
    # unresolved, matching how shell callers spell absolute paths;
    # Path.cwd() is the physical form.
    yield Path.cwd()
    env_pwd = os.environ.get("PWD", "")
    if env_pwd:
        pwd = Path(to_windows_drive_path(env_pwd))
        if pwd.is_absolute():
            yield pwd


def worktree_roots():
    # A session switched into a linked worktree still keeps its scratch files
    # in the working tree it was launched from.
    try:
        listing = subprocess.run(
            ["git", "worktree", "list", "--porcelain"],
            capture_output=True,
            check=True,
        ).stdout.decode("utf-8", "surrogateescape")
    except (OSError, subprocess.CalledProcessError):
        return
    for line in listing.splitlines():
        if line.startswith("worktree "):
            yield Path(to_windows_drive_path(line[len("worktree "):]))


def locate(target, raw):
    # Returns (base, rel): rel is the path below base, and base is None when
    # rel is relative to the CWD. rel is None when no base contains <path>.
    if not (target.is_absolute() or raw.startswith(("/", "\\"))):
        return None, target
    for cwd in cwd_candidates():
        try:
            return None, target.relative_to(cwd)
        except ValueError:
            continue
    for root in worktree_roots():
        try:
            rel = target.relative_to(root)
        except ValueError:
            continue
        if rel.parts[: len(SCRATCH_ROOT.parts)] == SCRATCH_ROOT.parts:
            return root, rel
    return None, None


def missing_parent_status(target, raw, scratch_root, scratch_real):
    # rc=3 lets the caller mkdir -p every missing component, so the deepest
    # existing ancestor (following even a dangling symlink) must itself
    # resolve inside scratch_root, or a symlinked component could redirect
    # the mkdir outside. Ancestors at or above scratch_root are skipped:
    # scratch_real resolves through those same components, so they can
    # never appear to escape.
    ancestor = target.parent
    while not (ancestor.exists() or ancestor.is_symlink()):
        if ancestor == ancestor.parent:
            break
        ancestor = ancestor.parent
    if len(ancestor.parts) > len(scratch_root.parts):
        try:
            resolved_ancestor = ancestor.resolve()
        except OSError:
            return fail(f"cannot resolve the parent directory: {raw}")
        if not resolved_ancestor.is_relative_to(scratch_real):
            return fail(f"resolved path escapes {SCRATCH_ROOT.as_posix()}/: {raw}")
    return 3


def guard(mode, raw):
    base, target = locate(Path(to_windows_drive_path(raw)), raw)
    if target is None:
        return fail(f"absolute path is outside the current project: {raw}")

    parts = target.parts
    if ".." in parts:
        return fail(f"path containing '..' is not allowed: {raw}")
    if parts[: len(SCRATCH_ROOT.parts)] != SCRATCH_ROOT.parts:
        return fail(f"path is not under {SCRATCH_ROOT.as_posix()}/: {raw}")
    if len(parts) <= len(SCRATCH_ROOT.parts):
        return fail(f"the bare {SCRATCH_ROOT.as_posix()}/ root is not allowed: {raw}")

    scratch_root = SCRATCH_ROOT
    if base is not None:
        scratch_root = base / SCRATCH_ROOT
        target = base / target

    if mode is not None:
        # Resolve physical (symlink-free) paths so a symlinked component
        # cannot escape scratch_root.
        if scratch_root.is_symlink():
            return fail(f"{SCRATCH_ROOT.as_posix()} itself is a symlink: {raw}")
        try:
            # Non-strict: scratch_root may not exist yet (rc=3 lets the
            # caller create it).
            scratch_real = scratch_root.resolve()
        except OSError:
            return fail(f"cannot resolve {SCRATCH_ROOT.as_posix()}: {raw}")
        try:
            resolved_parent = target.parent.resolve(strict=True)
        except FileNotFoundError:
            return missing_parent_status(target, raw, scratch_root, scratch_real)
        except OSError:
            return fail(f"cannot resolve the parent directory: {raw}")
        if not resolved_parent.is_dir():
            return fail(f"parent directory exists but cannot be entered: {raw}")
        if not resolved_parent.is_relative_to(scratch_real):
            return fail(f"resolved path escapes {SCRATCH_ROOT.as_posix()}/: {raw}")
        if mode == "-w":
            try:
                resolved_target = target.resolve()
            except OSError:
                return fail(f"cannot resolve the write target: {raw}")
            if not resolved_target.is_relative_to(scratch_real):
                return fail(f"resolved path escapes {SCRATCH_ROOT.as_posix()}/: {raw}")

    sys.stdout.buffer.write((target.as_posix() + "\n").encode())
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
