#!/usr/bin/env bash
# fetch-diff.sh — Fetch all git diff sections for review / QA.
# Usage: bash <path>/fetch-diff.sh <base-branch> <output-file>
#
# Writes the following sections to <output-file>:
#   === Changed Files (<base>..HEAD) ===
#   === Commit Log (<base>..HEAD) ===
#   === Commit Diff (<base>..HEAD) ===
#   === Staged Changes ===
#   === Unstaged Changes ===

BASE="${1:?Error: base branch argument required}"
OUT="${2:?Error: output file path argument required}"

case "${BASE}" in
    -*) echo "Error: base '${BASE}' must not start with '-'" >&2; exit 1 ;;
esac

if ! git rev-parse --verify --quiet "${BASE}^{commit}" >/dev/null 2>&1; then
    echo "Error: base '${BASE}' does not resolve to a commit" >&2
    exit 1
fi

OUT_DIR="$(dirname "${OUT}")"
mkdir -p "${OUT_DIR}"

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
