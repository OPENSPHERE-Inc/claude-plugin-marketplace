#!/usr/bin/env bash
# fetch-diff.sh — Fetch all git diff sections for parallel-review.
# Usage: <path>/fetch-diff.sh <base-branch> <output-file>
#
# Writes the following sections to <output-file>:
#   === Changed Files (<base>..HEAD) ===
#   === Commit Log (<base>..HEAD) ===
#   === Commit Diff (<base>..HEAD) ===
#   === Staged Changes ===
#   === Unstaged Changes ===

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
GUARD="${SCRIPT_DIR}/lib/scratch-guard.py"

BASE="${1:?Error: base branch argument required}"
OUT="${2:?Error: output file path argument required}"

if ! git rev-parse --verify --quiet --end-of-options "${BASE}^{commit}" >/dev/null; then
    echo "Error: invalid base branch: ${BASE}" >&2
    exit 1
fi

OUT="$(python3 "${GUARD}" "${OUT}")" || exit 1
mkdir -p "$(dirname "${OUT}")"
OUT="$(python3 "${GUARD}" -w "${OUT}")" || exit 1

{
    printf '=== Changed Files (%s..HEAD) ===\n' "${BASE}"
    git diff --name-status "${BASE}..HEAD"
    printf '\n'

    printf '=== Commit Log (%s..HEAD) ===\n' "${BASE}"
    git log "${BASE}..HEAD" --oneline
    printf '\n'

    printf '=== Commit Diff (%s..HEAD) ===\n' "${BASE}"
    git diff "${BASE}..HEAD"
    printf '\n'

    printf '=== Staged Changes ===\n'
    git diff --cached
    printf '\n'

    printf '=== Unstaged Changes ===\n'
    git diff
    printf '\n'
} > "${OUT}"
