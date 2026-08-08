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
#   === Untracked Files ===

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

# git diff reports no untracked file in any of its modes. Register them in a
# throwaway index with --intent-to-add so a plain diff renders them as new files;
# the real index is never touched. Runs from the repo root to keep the listing
# repo-wide the way git diff already is whatever the CWD. The scratch dir is
# excluded by path at both the root and the invoking CWD — a project need not
# gitignore it, and this script's own output file lives there.
untracked_diff() (
    local f rc=0 prefix tmp_dir tmp_index
    prefix="$(git rev-parse --show-prefix)"
    cd "$(git rev-parse --show-toplevel)"

    local -a paths=()
    while IFS= read -r -d '' f; do
        paths+=("${f}")
    done < <(git ls-files --others --exclude-standard -z -- \
        ':(exclude).claude/tmp' ":(exclude)${prefix}.claude/tmp")
    [[ "${#paths[@]}" -gt 0 ]] || return 0

    # mktemp -d gives a mode-0700 private dir, so the index path inside it
    # cannot be pre-planted with a symlink by another local user.
    tmp_dir="$(mktemp -d)"
    tmp_index="${tmp_dir}/index"
    if GIT_INDEX_FILE="${tmp_index}" git add -N -- "${paths[@]}"; then
        GIT_INDEX_FILE="${tmp_index}" review_diff --name-status || rc=$?
        printf '\n'
        GIT_INDEX_FILE="${tmp_index}" review_diff || rc=$?
    else
        rc=$?
    fi
    # Remove the throwaway index dir on every path: errexit would skip a trailing rm on failure.
    rm -rf "${tmp_dir}"
    return "${rc}"
)

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

    printf '=== Untracked Files ===\n'
    untracked_diff
    printf '\n'
} > "${OUT}"
