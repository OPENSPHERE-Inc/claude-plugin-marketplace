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

# Validate <path> as a scratch write target and print the normalized path.
# mkdir -p runs only after the physical -w check reports a missing parent
# (rc=3), and -w is re-run afterwards, so mkdir never follows a symlinked
# component out of .claude/tmp/.
prepare_out() {
    local out rc=0
    out="$(python3 "${GUARD}" "$1")" || return 1
    python3 "${GUARD}" -w "${out}" >/dev/null || rc=$?
    if [[ "${rc}" -eq 3 ]]; then
        mkdir -p "$(dirname "${out}")" || return 1
        rc=0
        python3 "${GUARD}" -w "${out}" >/dev/null || rc=$?
    fi
    [[ "${rc}" -eq 0 ]] || return 1
    printf '%s\n' "${out}"
}

BASE="${1:?Error: base branch argument required}"
OUT="${2:?Error: output file path argument required}"

if ! git rev-parse --verify --quiet --end-of-options "${BASE}^{commit}" >/dev/null; then
    echo "Error: invalid base branch: ${BASE}" >&2
    exit 1
fi

OUT="$(prepare_out "${OUT}")" || exit 1

# Reviewers parse these sections as plain unified diffs: pin the prefix
# options and disable external diff / textconv / color so user git config
# cannot change the format (or run arbitrary commands).
review_diff() {
    git -c diff.noprefix=false -c diff.mnemonicPrefix=false \
        diff --no-ext-diff --no-textconv --no-color "$@"
}

{
    printf '=== Changed Files (%s..HEAD) ===\n' "${BASE}"
    review_diff --name-status "${BASE}..HEAD"
    printf '\n'

    printf '=== Commit Log (%s..HEAD) ===\n' "${BASE}"
    git log "${BASE}..HEAD" --oneline --no-color
    printf '\n'

    printf '=== Commit Diff (%s..HEAD) ===\n' "${BASE}"
    review_diff "${BASE}..HEAD"
    printf '\n'

    printf '=== Staged Changes ===\n'
    review_diff --cached
    printf '\n'

    printf '=== Unstaged Changes ===\n'
    review_diff
    printf '\n'
} > "${OUT}"
