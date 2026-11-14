#!/usr/bin/env bash
# restore.sh — restore one restore-list entry of a /cdev:coding design from a turning point
#   commit into the working tree.
# Usage: <path>/restore.sh <commit> <path>
#
# <path> is repository-relative. The restore also deletes the tracked paths under it that
# <commit> lacks. Refuses an absolute path, a backslash, a . or .. component, a leading - or :,
# a commit that does not resolve, a path in neither <commit> nor HEAD, and an entry whose
# restore would overwrite or delete an untracked file or a tracked file that differs from HEAD,
# or would change a path outside the entry, giving the reason on stderr. Like a git checkout,
# it may overwrite an ignored file at a path <commit> tracks, so /cdev:coding calls it only in
# the worktree a run under --worktree created. Changes no index, branch, or HEAD.

set -euo pipefail

if [[ $# -ne 2 ]]; then
    echo "Usage: restore.sh <commit> <path>" >&2
    exit 2
fi
COMMIT="$1"
ENTRY="$2"

# A leading "-" would be parsed as an option by rev-parse.
if [[ -z "${COMMIT}" || "${COMMIT}" == -* ]] \
    || ! SHA="$(git rev-parse --verify --quiet "${COMMIT}^{commit}")"; then
    echo "Error: not a commit: ${COMMIT}" >&2
    exit 1
fi

case "${ENTRY}" in
    '' | /* | -* | :* | [A-Za-z]:* | *\\*)
        echo "Error: not a repository-relative path: ${ENTRY}" >&2
        exit 1
        ;;
esac
# A bare "." is refused as well: it would restore the whole tree.
case "/${ENTRY}/" in
    */./* | */../*)
        echo "Error: path has a . or .. component: ${ENTRY}" >&2
        exit 1
        ;;
esac

cd "$(git rev-parse --show-toplevel)"
lgit() { git --literal-pathspecs -c core.quotePath=true "$@"; }

HEAD_SHA="$(git rev-parse --verify "HEAD^{commit}")"
TMP="$(mktemp -d "$(git rev-parse --absolute-git-dir)/restore.XXXXXX")"
trap 'rm -rf -- "${TMP}"' EXIT
trap 'exit 1' HUP INT TERM
# The script's own indexes keep the shared index and its lock out of the restore.
NEW_INDEX="${TMP}/new"
WT_INDEX="${TMP}/worktree"

# NEW: the tree of HEAD with the entry replaced by its content at <commit>.
lgit ls-tree -r -z "${SHA}" -- "${ENTRY}" > "${TMP}/entry"
GIT_INDEX_FILE="${NEW_INDEX}" git read-tree "${HEAD_SHA}"
GIT_INDEX_FILE="${NEW_INDEX}" lgit rm -r -q --cached --ignore-unmatch -- "${ENTRY}"
GIT_INDEX_FILE="${NEW_INDEX}" git update-index -z --index-info < "${TMP}/entry"
NEW="$(GIT_INDEX_FILE="${NEW_INDEX}" git write-tree)"
if [[ ! -s "${TMP}/entry" && "${NEW}" == "$(git rev-parse "${HEAD_SHA}^{tree}")" ]]; then
    echo "Error: ${ENTRY} is in neither ${COMMIT} nor HEAD; nothing was restored" >&2
    exit 1
fi

# A path added under a file of HEAD replaces that file.
OUTSIDE="$(git -c core.quotePath=true diff-tree -r --name-only --no-renames "${HEAD_SHA}" \
    "${NEW}" -- ":(exclude,literal)${ENTRY}")"
if [[ -n "${OUTSIDE}" ]]; then
    echo "Error: restoring ${ENTRY} from ${COMMIT} would change these paths outside it;" \
        "nothing was restored:" >&2
    printf '%s\n' "${OUTSIDE}" >&2
    exit 1
fi

GIT_INDEX_FILE="${WT_INDEX}" git read-tree "${HEAD_SHA}"
# read-tree -m takes an index entry without stat information for a local change.
GIT_INDEX_FILE="${WT_INDEX}" git update-index -q --refresh || :
# read-tree -m keeps a local change where HEAD and <commit> agree, so it is refused here.
CHANGED="$(GIT_INDEX_FILE="${WT_INDEX}" lgit diff-files --name-only -- "${ENTRY}")"
if [[ -n "${CHANGED}" ]]; then
    echo "Error: these tracked files under ${ENTRY} differ from HEAD; nothing was restored:" >&2
    printf '%s\n' "${CHANGED}" >&2
    exit 1
fi
# The two-way merge refuses, before it writes, to lose an untracked file or a local change.
if ! GIT_INDEX_FILE="${WT_INDEX}" git read-tree -m -u "${HEAD_SHA}" "${NEW}"; then
    echo "Error: git refused to restore ${ENTRY} from ${COMMIT}; its message above gives" \
        "the reason" >&2
    exit 1
fi
