#!/usr/bin/env bash
# rm-tmp.sh — Delete files or directories under .claude/tmp/ only.
# Usage: <path>/rm-tmp.sh <path> [<path> ...]
#
# Restricts deletion to paths under the project's .claude/tmp/ directory
# so that Bash(rm:*) need not be added to the permission allowlist.
# Rejects: paths outside .claude/tmp/, paths containing '..',
# and the .claude/tmp/ root itself (only sub-paths may be deleted).
# Directories are removed recursively.

set -euo pipefail

if [ $# -eq 0 ]; then
    echo "Error: at least one path is required" >&2
    exit 2
fi

ALLOWED_PREFIX=".claude/tmp/"

for target in "$@"; do
    # Convert absolute path to relative by stripping the current working directory prefix.
    # Rejects absolute paths outside the current project.
    if [[ "${target}" == /* ]]; then
        cwd="$(pwd)"
        if [[ "${target}" == "${cwd}/"* ]]; then
            normalized="${target#"${cwd}/"}"
        else
            echo "Error: absolute path is outside the current project: ${target}" >&2
            exit 1
        fi
    else
        normalized="${target#./}"
    fi

    if [[ "${normalized}" == *..* ]]; then
        echo "Error: path containing '..' is not allowed: ${target}" >&2
        exit 1
    fi

    if [[ "${normalized}" != "${ALLOWED_PREFIX}"* ]]; then
        echo "Error: path is not under ${ALLOWED_PREFIX}: ${target}" >&2
        exit 1
    fi

    # Reject the bare .claude/tmp/ root (must have at least one real path
    # component beneath it). Repeated slashes are collapsed and trailing
    # '/' and '/.' segments stripped first, so disguised forms of the root
    # such as '.claude/tmp//', '.claude/tmp/.' and '.claude/tmp/./' are
    # all caught.
    stripped="${normalized}"
    while [[ "${stripped}" == *//* ]]; do
        stripped="${stripped//\/\//\/}"
    done
    while [[ "${stripped}" == */ || "${stripped}" == */. ]]; do
        stripped="${stripped%/.}"
        stripped="${stripped%/}"
    done
    if [[ "${stripped}" == "${ALLOWED_PREFIX%/}" ]]; then
        echo "Error: deleting the .claude/tmp/ root itself is not allowed: ${target}" >&2
        exit 1
    fi

    # Resolve the parent's physical (symlink-free) path so a symlinked path
    # component can't let rm escape .claude/tmp/. `pwd -P` is used instead of
    # `readlink -f` for portability.
    parent="${stripped%/*}"
    if resolved_parent="$(cd "${parent}" 2>/dev/null && pwd -P)"; then
        tmp_root="$(cd "${ALLOWED_PREFIX}" 2>/dev/null && pwd -P)" || {
            echo "Error: cannot resolve ${ALLOWED_PREFIX}: ${target}" >&2
            exit 1
        }
        case "${resolved_parent}" in
        "${tmp_root}" | "${tmp_root}"/*) ;;
        *)
            echo "Error: resolved path escapes ${ALLOWED_PREFIX}: ${target}" >&2
            exit 1
            ;;
        esac
        rm -rf -- "${stripped}"
    elif [[ -e "${parent}" ]]; then
        echo "Error: parent directory exists but cannot be entered: ${target}" >&2
        exit 1
    fi
    # A non-existent parent means the target is already gone; skip silently.
done
