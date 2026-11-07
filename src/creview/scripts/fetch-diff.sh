#!/usr/bin/env bash
# fetch-diff.sh — Fetch all git diff sections for parallel-review.
# Usage: <path>/fetch-diff.sh <base-branch> <output-file>
#        <path>/fetch-diff.sh --range <from-rev> <to-rev> <output-file>
#        <path>/fetch-diff.sh --pr <merge-base> <head> <output-file>
#        <path>/fetch-diff.sh --pr-since <merge-base> <since> <head> <output-file>
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
# .gitmodules, nor its .gitattributes can hide a change. --pr requires Git 2.41
# or later (--attr-source) and always fails on an older Git.
#
# --pr-since is --pr for the changes <head> adds to <since>, an ancestor of it:
# <from> is <since>. When the pull request merged its base since <since>, the
# diff starts from <since> merged with <merge-base>, so that what the base
# brought in is left out while a conflict's resolution and a base change the
# merge dropped stay, and the log leaves out the base's commits. A file that
# merge left conflicted without conflict markers, such as a binary file or one
# the base deleted, starts from its version in <merge-base>, or from no file.

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
SINCE=""
if [[ "${1:-}" == "--range" || "${1:-}" == "--pr" ]]; then
    RANGE_MODE=1
    [[ "$1" == "--range" ]] || PR_MODE=1
    FROM="${2:?Error: $1 requires a from revision}"
    TO="${3:?Error: $1 requires a to revision}"
    OUT="${4:?Error: output file path argument required}"
elif [[ "${1:-}" == "--pr-since" ]]; then
    RANGE_MODE=1
    PR_MODE=1
    FROM="${2:?Error: --pr-since requires a merge base}"
    SINCE="${3:?Error: --pr-since requires a since revision}"
    TO="${4:?Error: --pr-since requires a head revision}"
    OUT="${5:?Error: output file path argument required}"
else
    FROM="${1:?Error: base branch argument required}"
    TO="HEAD"
    OUT="${2:?Error: output file path argument required}"
fi

for rev in "${FROM}" "${TO}" ${SINCE:+"${SINCE}"}; do
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
    ATTR_SOURCE="${DIFF_FROM}"
    if ! git --attr-source="${ATTR_SOURCE}" rev-parse --git-dir >/dev/null 2>&1; then
        echo "Error: git does not accept --attr-source;" \
            "fetch-diff.sh --pr requires Git 2.41 or later" >&2
        exit 1
    fi
fi

# Print, as update-index -z --index-info records, the base's entry for each path that <merge>,
# the -z output of merge-tree run at the top of the working tree, left conflicted with the since
# side's entry, or a removal when the base has none.
base_entries() { # <merge>
    local tree record mode oid stage path kept=""
    {
        IFS= read -r -d '' tree
        while IFS= read -r -d '' record; do
            read -r mode oid stage <<< "${record%%$'\t'*}"
            path="${record#*$'\t'}"
            if [[ "${stage}" == 2 ]]; then
                kept=""
                if [[ "$(GIT_LITERAL_PATHSPECS=1 git ls-tree --full-tree \
                    --format='%(objectmode) %(objectname)' "${tree}" -- "${path}")" \
                    == "${mode} ${oid}" ]]; then
                    kept="${path}"
                    printf '0 %s\t%s\0' "${oid}" "${path}"
                fi
            elif [[ "${stage}" == 3 && "${path}" == "${kept}" ]]; then
                printf '%s %s\t%s\0' "${mode}" "${oid}" "${path}"
            fi
        done
    } < "$1"
}

LABEL="${FROM}..${TO}"
LOG_REVS=("${FROM}..${TO}")
if [[ -n "${SINCE}" ]]; then
    for rev in "${FROM}" "${SINCE}"; do
        if ! git merge-base --is-ancestor "${rev}" "${TO}"; then
            echo "Error: ${rev} is not an ancestor of ${TO}" >&2
            exit 1
        fi
    done
    LABEL="${SINCE}..${TO}"
    LOG_REVS=("^${SINCE}" "^${FROM}" "${TO}")
    if git merge-base --is-ancestor "${FROM}" "${SINCE}"; then
        DIFF_FROM="${SINCE}"
    else
        # merge-tree exits 1 on a conflict and still writes the tree, conflict markers included.
        # The merge drivers of git config, and its filters under merge.renormalize, would run on
        # the pull request's content: git merge-file, the built-in text merge, replaces each
        # driver, and its exit of 128 or more, as on a binary file, counts as a conflict. git
        # config reads only the file GIT_CONFIG names, while merge-tree ignores it.
        rc=0
        drivers="$(unset GIT_CONFIG; git config --name-only --get-regexp '^merge\..*\.driver$')" \
            || rc=$?
        if [[ "${rc}" -gt 1 ]]; then
            echo "Error: git config could not list the merge drivers" >&2
            exit 1
        fi
        merge_config=(-c merge.renormalize=false)
        while IFS= read -r key; do
            if [[ -n "${key}" ]]; then
                merge_config+=("--config-env=${key}=FETCH_DIFF_TEXT_MERGE")
            fi
        done <<< "${drivers}"
        text_merge='git merge-file -q --marker-size=%L -L since -L ancestor -L base %A %O %B'
        text_merge+='; s=$?; [ "$s" -lt 128 ] || s=1; exit "$s"'
        merge_dir="$(mktemp -d)"
        trap 'rm -rf "${merge_dir}"' EXIT
        top="$(git rev-parse --show-cdup)"
        rc=0
        FETCH_DIFF_TEXT_MERGE="${text_merge}" git -C "${top}" "${merge_config[@]}" \
            --attr-source="${ATTR_SOURCE}" merge-tree -z --write-tree --no-messages \
            "${SINCE}" "${FROM}" > "${merge_dir}/merge" || rc=$?
        if [[ "${rc}" -gt 1 ]] || ! IFS= read -r -d '' DIFF_FROM < "${merge_dir}/merge" \
            || [[ ! "${DIFF_FROM}" =~ ^[0-9a-f]{40,64}$ ]]; then
            echo "Error: git merge-tree could not merge ${FROM} into ${SINCE}" >&2
            exit 1
        fi
        # A file merge left with the since side's entry and no conflict markers starts from the
        # base's entry instead.
        base_entries "${merge_dir}/merge" > "${merge_dir}/entries"
        if [[ -s "${merge_dir}/entries" ]]; then
            index="${merge_dir}/index"
            GIT_INDEX_FILE="${index}" git read-tree "${DIFF_FROM}" \
                && GIT_INDEX_FILE="${index}" git update-index -z --index-info \
                    < "${merge_dir}/entries" \
                && DIFF_FROM="$(GIT_INDEX_FILE="${index}" git write-tree)" \
                || { echo "Error: git could not start the diff from the base's entries" >&2
                     exit 1; }
        fi
    fi
fi

# Reviewers parse these sections as plain unified diffs: pin the prefix
# options and disable external diff / textconv / color so user git config
# cannot change the format (or run arbitrary commands). Paths are printed
# unescaped, since reviewers Read the files by these paths.
# FIXME: text git renders as binary (a NUL byte, or a binary / -diff attribute) shows no
# changed lines, so a pull request can hide an edit in it. Diff such text with --text.
review_diff() {
    git ${ATTR_SOURCE:+"--attr-source=${ATTR_SOURCE}"} \
        -c diff.noprefix=false -c diff.mnemonicPrefix=false -c core.quotePath=false \
        diff --no-ext-diff --no-textconv --no-color ${NO_RENAMES:+"${NO_RENAMES}"} \
        --submodule=short ${IGNORE_SUBMODULES:+"${IGNORE_SUBMODULES}"} "$@"
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
    printf '=== Changed Files (%s) ===\n' "${LABEL}"
    review_diff --name-status "${DIFF_FROM}..${TO}" --
    printf '\n'

    printf '=== Commit Log (%s) ===\n' "${LABEL}"
    git log --oneline --no-color "${LOG_REVS[@]}" --
    printf '\n'

    printf '=== Commit Diff (%s) ===\n' "${LABEL}"
    review_diff "${DIFF_FROM}..${TO}" --
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
