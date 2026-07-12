#!/usr/bin/env bash
# fetch-diff.sh — capture the working-tree changes made since coding start, for QA.
#
# Modes:
#   fetch-diff.sh snapshot <tree-out-file>
#     Record a baseline tree of the current working tree (tracked + untracked,
#     respecting .gitignore; excluding .claude/tmp) into <tree-out-file>.
#     Run once before any coding, so the QA diff is exactly what this run changed.
#
#   fetch-diff.sh diff <baseline-tree-file> <out-file>
#     Write the diff between that baseline and the current working tree to <out-file>,
#     including new (untracked) files. Sections:
#       === Changed Files (since coding start) ===
#       === Diff (since coding start) ===
#
# Diffing against the baseline excludes pre-existing commits and pre-existing
# uncommitted changes, so feature branches with prior commits do not bloat the diff.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "${SCRIPT_DIR}/lib/scratch-guard.sh"

# Tree object of the entire current working tree (tracked + untracked, .gitignore
# respected), built in a throwaway index seeded from the real index to reuse its
# stat cache, without touching the real index or working tree. The .claude/tmp
# scratch dir is excluded at diff time (PATHSPEC below), not here: naming it in a
# `git add` pathspec errors when the project gitignores it ("paths are ignored").
worktree_tree() {
    local tmp_index tree rc=0
    tmp_index="$(mktemp)"
    # No real index (fresh repo): remove the temp file — git rejects a 0-byte
    # index but creates a missing GIT_INDEX_FILE as an empty one.
    cp -p "$(git rev-parse --git-path index)" "$tmp_index" 2>/dev/null || rm -f "$tmp_index"
    if GIT_INDEX_FILE="$tmp_index" git add -A; then
        tree="$(GIT_INDEX_FILE="$tmp_index" git write-tree)" || rc=$?
    else
        rc=$?
    fi
    # Remove the throwaway index on every path: errexit would skip a trailing rm on failure.
    rm -f "$tmp_index"
    [[ $rc -eq 0 ]] || return "$rc"
    printf '%s\n' "$tree"
}

qa_diff() {
    git -c diff.noprefix=false -c diff.mnemonicPrefix=false \
        diff --no-ext-diff --no-textconv --no-color "$@"
}

# Keep the cdev scratch dir out of the diff whether or not the project gitignores it:
# exclude .claude/tmp at both the repo root and the CWD (the skill may run in a monorepo subdir).
PATHSPEC=(-- ':(top)' ':(top,exclude).claude/tmp' ':(exclude).claude/tmp')

MODE="${1:?Error: mode (snapshot|diff) argument required}"

case "${MODE}" in
    snapshot)
        OUT="${2:?Error: tree-out-file argument required}"
        OUT="$(scratch_guard "${OUT}")"
        mkdir -p "$(dirname "${OUT}")"
        OUT="$(scratch_guard -p "${OUT}")"
        worktree_tree > "${OUT}"
        ;;
    diff)
        BASELINE_FILE="${2:?Error: baseline-tree-file argument required}"
        OUT="${3:?Error: output file path argument required}"
        OUT="$(scratch_guard "${OUT}")"
        mkdir -p "$(dirname "${OUT}")"
        OUT="$(scratch_guard -p "${OUT}")"
        BASELINE="$(cat "${BASELINE_FILE}")"
        # Allow only a bare tree hash so a tampered baseline file cannot inject
        # git options (e.g. --output).
        [[ "${BASELINE}" =~ ^([0-9a-f]{40}|[0-9a-f]{64})$ ]] || {
            echo "Error: baseline-tree file does not contain a valid tree hash: ${BASELINE_FILE}" >&2
            exit 1
        }
        CURRENT="$(worktree_tree)"
        {
            printf '=== Changed Files (since coding start) ===\n'
            qa_diff --name-status "${BASELINE}" "${CURRENT}" "${PATHSPEC[@]}"
            printf '\n'
            printf '=== Diff (since coding start) ===\n'
            qa_diff "${BASELINE}" "${CURRENT}" "${PATHSPEC[@]}"
            printf '\n'
        } > "${OUT}"
        ;;
    *)
        echo "Error: unknown mode '${MODE}' (expected 'snapshot' or 'diff')" >&2
        exit 1
        ;;
esac
