#!/usr/bin/env bash
# restore.sh — restore one restore-list entry of a /cdev:coding design from a turning point
#   commit into the working tree.
# Usage: <path>/restore.sh <commit> <path>
#
# <path> is repository-relative. The restore also deletes the tracked paths under it that
# <commit> lacks. Refuses an absolute path, a backslash, a . or .. component, a leading
# - or :, a commit that does not resolve, and an entry whose restore would overwrite or
# delete an untracked or ignored file, which it lists on stderr. Changes no index, branch,
# or HEAD.

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

TRACKED="$(lgit ls-tree -r --name-only "${SHA}" -- "${ENTRY}")"
OTHERS="$(lgit ls-files --others -- "${ENTRY}")"

# git restore overwrites an untracked or ignored file at a path the commit tracks, replaces
# one where the commit has a directory, and removes an untracked directory where the commit
# has a file, all without a warning. Both lists use git's quoting, so they compare as is.
CONFLICTS="$(
    {
        printf '%s\n' "${TRACKED}" | sed 's/^/T /'
        printf '%s\n' "${OTHERS}" | sed 's/^/O /'
    } | awk '
        function unquote(s) {
            if (s ~ /^".*"$/) s = substr(s, 2, length(s) - 2)
            return s
        }
        length($0) <= 2 { next }
        {
            tag = substr($0, 1, 1)
            raw = substr($0, 3)
            p = unquote(raw)
        }
        tag == "T" {
            tracked[p] = 1
            while (sub("/[^/]*$", "", p)) parent[p] = 1
            next
        }
        {
            sub("/$", "", p)
            hit = (p in tracked) || (p in parent)
            while (!hit && sub("/[^/]*$", "", p)) hit = (p in tracked)
            if (hit) print raw
        }
    '
)"
if [[ -n "${CONFLICTS}" ]]; then
    echo "Error: restoring ${ENTRY} from ${COMMIT} would overwrite or delete these untracked" \
        "or ignored files; nothing was restored:" >&2
    printf '%s\n' "${CONFLICTS}" >&2
    exit 1
fi

lgit restore --source="${SHA}" --worktree -- "${ENTRY}"
