#!/usr/bin/env bash
# fetch-diff.sh — Fetch all git diff sections for parallel-review.
# Usage: <path>/fetch-diff.sh <base-branch> <output-file>
#        <path>/fetch-diff.sh --range <from-rev> <to-rev> <output-file>
#        <path>/fetch-diff.sh --pr <merge-base> <head> <output-file>
#
# Writes the following sections to <output-file>:
#   === Changed Files (<from>..<to>) ===
#   === Commit Log (<from>..<to>) ===
#   === Commit Diff (<from>..<to>) ===
#   === Staged Changes ===
#   === Unstaged Changes ===
#   === Untracked Files ===
#
# Without --range, <from> is <base-branch> and <to> is HEAD. With --range, the
# three working-tree sections are omitted: working-tree state belongs to no
# commit, so it is outside any <from>..<to> range.
#
# --pr is --range for a pull request checked out in the working tree: renames
# are not detected, submodule changes are always shown, and attributes are read
# from the merge base, so neither an exact rename, the pull request's
# .gitmodules, nor its .gitattributes can hide a change. A Git older than 2.41
# has no --attr-source: --pr then fails when the range changes, at any depth, a
# file that a case-insensitive file system may read as .gitattributes.

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

RANGE_MODE=0
PR_MODE=0
if [[ "${1:-}" == "--range" || "${1:-}" == "--pr" ]]; then
    RANGE_MODE=1
    [[ "$1" == "--range" ]] || PR_MODE=1
    FROM="${2:?Error: $1 requires a from revision}"
    TO="${3:?Error: $1 requires a to revision}"
    OUT="${4:?Error: output file path argument required}"
else
    FROM="${1:?Error: base branch argument required}"
    TO="HEAD"
    OUT="${2:?Error: output file path argument required}"
fi

for rev in "${FROM}" "${TO}"; do
    if ! git rev-parse --verify --quiet --end-of-options "${rev}^{commit}" >/dev/null; then
        echo "Error: invalid revision: ${rev}" >&2
        exit 1
    fi
done

OUT="$(prepare_out "${OUT}")" || exit 1

# git diff A..B compares two trees, so commits added to A after the fork point surface
# as reversals; diff from the merge base instead. git log keeps A..B, where two dots
# already means "commits in B but not in A". With no common ancestor (orphan branch,
# shallow clone) there is no merge base: fall back to FROM rather than aborting.
DIFF_FROM="$(git merge-base "${FROM}" "${TO}" 2>/dev/null || printf '%s' "${FROM}")"

# git diff reads attributes from the working tree even between two commits. GIT_ATTR_SOURCE
# is not used: a Git without --attr-source ignores it silently.
ATTR_SOURCE=""
NO_RENAMES=""
IGNORE_SUBMODULES=""
if [[ "${PR_MODE}" -eq 1 ]]; then
    NO_RENAMES="--no-renames"
    IGNORE_SUBMODULES="--ignore-submodules=none"
    if git --attr-source="${DIFF_FROM}" rev-parse --git-dir >/dev/null 2>&1; then
        ATTR_SOURCE="${DIFF_FROM}"
    # A case-insensitive file system may open .gitattributes under a name that differs in
    # Unicode case or normalization, or by HFS+ ignorable code points.
    # -I: the working tree is the pull request's, so its modules must not shadow unicodedata.
    elif ! git diff --name-only -z --no-relative --no-renames "${DIFF_FROM}" "${TO}" \
            | python3 -I -c '
import sys, unicodedata
ignorable = dict.fromkeys(
    [*range(0x200C, 0x2010), *range(0x202A, 0x202F), *range(0x206A, 0x2070), 0xFEFF])
def fold(name):
    name = unicodedata.normalize("NFD", name.decode("utf-8", "surrogateescape"))
    return unicodedata.normalize("NFD", name.translate(ignorable).casefold())
paths = sys.stdin.buffer.read().split(b"\0")
sys.exit(any(fold(p.rsplit(b"/", 1)[-1]) == ".gitattributes" for p in paths))'; then
        echo "Error: the pull request changes a .gitattributes file and git lacks --attr-source" \
            "(added in Git 2.41), so its attributes could hide changes from the diff;" \
            "use Git 2.41 or later" >&2
        exit 1
    fi
fi

# Reviewers parse these sections as plain unified diffs: pin the prefix
# options and disable external diff / textconv / color so user git config
# cannot change the format (or run arbitrary commands).
review_diff() {
    git ${ATTR_SOURCE:+"--attr-source=${ATTR_SOURCE}"} \
        -c diff.noprefix=false -c diff.mnemonicPrefix=false \
        diff --no-ext-diff --no-textconv --no-color ${NO_RENAMES:+"${NO_RENAMES}"} \
        ${IGNORE_SUBMODULES:+"${IGNORE_SUBMODULES}"} "$@"
}

# git diff reports no untracked file in any of its modes. Register them in a
# throwaway index with --intent-to-add so a plain diff renders them as new files;
# the real index is never touched. Runs from the repo root to keep the listing
# repo-wide the way git diff already is whatever the CWD. The scratch dir (at both
# the root and the invoking CWD) and the --worktree worktrees (.claude/worktrees,
# nested repos that git add -N would record as gitlinks) are excluded by path — a
# project need not gitignore them, and this script's own output file lives in the
# scratch dir.
untracked_diff() (
    local f rc=0 prefix tmp_dir tmp_index
    prefix="$(git rev-parse --show-prefix)"
    cd "$(git rev-parse --show-toplevel)"

    local -a paths=()
    while IFS= read -r -d '' f; do
        paths+=("${f}")
    done < <(git ls-files --others --exclude-standard -z -- \
        ':(exclude).claude/tmp' ":(exclude)${prefix}.claude/tmp" \
        ':(exclude).claude/worktrees')
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
    printf '=== Changed Files (%s..%s) ===\n' "${FROM}" "${TO}"
    review_diff --name-status "${DIFF_FROM}..${TO}"
    printf '\n'

    printf '=== Commit Log (%s..%s) ===\n' "${FROM}" "${TO}"
    git log "${FROM}..${TO}" --oneline --no-color
    printf '\n'

    printf '=== Commit Diff (%s..%s) ===\n' "${FROM}" "${TO}"
    review_diff "${DIFF_FROM}..${TO}"
    printf '\n'

    if [[ "${RANGE_MODE}" -eq 0 ]]; then
        printf '=== Staged Changes ===\n'
        review_diff --cached
        printf '\n'

        printf '=== Unstaged Changes ===\n'
        review_diff
        printf '\n'

        printf '=== Untracked Files ===\n'
        untracked_diff
        printf '\n'
    fi
} > "${OUT}"
