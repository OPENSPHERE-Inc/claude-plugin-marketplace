#!/usr/bin/env bash
# del-tmp.sh — Delete files or directories under .claude/tmp/ only.
# Usage: <path>/del-tmp.sh [--dry] <path> [<path> ...]
#
# Restricts deletion to paths under the project's .claude/tmp/ directory
# so that Bash(rm:*) need not be added to the permission allowlist.
# Containment rules live in lib/scratch-guard.py. Directories are removed
# recursively; a target whose parent no longer exists is skipped silently.
# --dry, anywhere in the arguments, deletes nothing and also refuses a target
# that resolves outside .claude/tmp/, so a follow-up mkdir -p under it stays inside.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

dry=0
guard_mode=-p
targets=()
for arg in "$@"; do
    case "${arg}" in
    --dry) dry=1; guard_mode=-w ;;
    *) targets+=("${arg}") ;;
    esac
done

if [ "${#targets[@]}" -eq 0 ]; then
    echo "Error: at least one path is required" >&2
    exit 2
fi

for target in "${targets[@]}"; do
    rc=0
    stripped="$(python3 "${SCRIPT_DIR}/lib/scratch-guard.py" "${guard_mode}" "${target}")" || rc=$?
    case "${rc}" in
    0) [ "${dry}" -eq 1 ] || rm -rf -- "${stripped}" ;;
    3) ;;
    *) exit 1 ;;
    esac
done
