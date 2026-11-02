#!/usr/bin/env bash
# del-tmp.sh — Delete files or directories under .claude/tmp/ only.
# Usage: <path>/del-tmp.sh [--dry] <path> [<path> ...]
#
# Restricts deletion to paths under the project's .claude/tmp/ directory
# so that Bash(rm:*) need not be added to the permission allowlist.
# Containment rules live in lib/scratch-guard.py. Directories are removed
# recursively; a target whose parent no longer exists is skipped silently.
# --dry, anywhere in the arguments, runs the same checks and exits with the
# same status but deletes nothing.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

dry=0
targets=()
for arg in "$@"; do
    case "${arg}" in
    --dry) dry=1 ;;
    *) targets+=("${arg}") ;;
    esac
done

if [ "${#targets[@]}" -eq 0 ]; then
    echo "Error: at least one path is required" >&2
    exit 2
fi

for target in "${targets[@]}"; do
    rc=0
    stripped="$(python3 "${SCRIPT_DIR}/lib/scratch-guard.py" -p "${target}")" || rc=$?
    case "${rc}" in
    0) [ "${dry}" -eq 1 ] || rm -rf -- "${stripped}" ;;
    3) ;;
    *) exit 1 ;;
    esac
done
