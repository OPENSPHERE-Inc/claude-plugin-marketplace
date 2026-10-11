#!/usr/bin/env bash
# worktree.sh — create / remove the git worktree a skill runs in under --worktree.
# Usage: <path>/worktree.sh create <branch>
#        <path>/worktree.sh remove <worktree-path>
#
# create: adds a worktree at <toplevel>/.claude/worktrees/<branch, "/" → "-">
#   checking out <branch>: an existing local branch as is, a missing one created
#   from HEAD. Prints three lines: main_root=<toplevel>, worktree_path=<path>,
#   branch=<branch>.
# remove: removes a worktree that has no uncommitted changes; the branch is kept.
#   A dirty worktree is left in place and the script exits non-zero.
#   Gitignored files do not count as changes and are deleted with the worktree.

set -euo pipefail

MODE="${1:?Error: mode (create|remove) argument required}"

case "${MODE}" in
    create)
        BRANCH="${2:?Error: branch argument required}"
        # A leading "-" would be parsed as an option by check-ref-format and worktree add.
        if [[ "${BRANCH}" == -* ]] \
            || ! BRANCH="$(git check-ref-format --branch "${BRANCH}" 2>/dev/null)"; then
            echo "Error: invalid branch name: ${2}" >&2
            exit 1
        fi
        MAIN_ROOT="$(git rev-parse --show-toplevel)"
        WT_PATH="${MAIN_ROOT}/.claude/worktrees/${BRANCH//\//-}"
        if [[ -e "${WT_PATH}" ]]; then
            echo "Error: worktree path already exists: ${WT_PATH}" >&2
            exit 1
        fi
        if git show-ref --verify --quiet "refs/heads/${BRANCH}"; then
            git worktree add --quiet -- "${WT_PATH}" "${BRANCH}" >&2
        else
            git worktree add --quiet -b "${BRANCH}" -- "${WT_PATH}" HEAD >&2
        fi
        printf 'main_root=%s\nworktree_path=%s\nbranch=%s\n' \
            "${MAIN_ROOT}" "${WT_PATH}" "${BRANCH}"
        ;;
    remove)
        WT_PATH="${2:?Error: worktree path argument required}"
        # git refuses the main worktree and any worktree with modified or untracked files.
        git worktree remove -- "${WT_PATH}"
        # Drop the container left empty by the last removal, so the main tree is unchanged.
        PARENT="$(dirname -- "${WT_PATH}")"
        if [[ "${PARENT}" == */.claude/worktrees ]]; then
            rmdir -- "${PARENT}" 2>/dev/null || true
        fi
        ;;
    *)
        echo "Error: unknown mode '${MODE}' (expected 'create' or 'remove')" >&2
        exit 1
        ;;
esac
