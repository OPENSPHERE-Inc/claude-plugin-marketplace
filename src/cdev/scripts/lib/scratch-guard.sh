#!/usr/bin/env bash
# scratch-guard.sh — single implementation of the .claude/tmp/ containment check.
# Source this file; it defines scratch_guard and is not meant to be executed.
# The consuming scripts are allowlisted for direct execution, so they must not
# touch paths outside the scratch dir; this guard is what enforces that.
#
#   scratch_guard [-p] <path>
#
# Prints the normalized repo-relative path on stdout and returns 0 when <path>
# stays under .claude/tmp/. Returns 1 on any violation (message on stderr).
# With -p the parent directory is additionally resolved to its physical path
# and re-checked, so a symlinked component cannot escape; returns 3 when the
# parent directory does not exist.

SCRATCH_ROOT=".claude/tmp"

scratch_guard() {
    local physical=0
    if [[ "${1:-}" == "-p" ]]; then
        physical=1
        shift
    fi
    if [[ $# -eq 0 || -z "${1}" ]]; then
        echo "Error: scratch_guard requires a path argument" >&2
        return 1
    fi
    local target="$1" cwd normalized stripped parent resolved_parent scratch_real

    # Convert an absolute path to repo-relative; reject anything outside the CWD.
    if [[ "${target}" == /* ]]; then
        cwd="$(pwd)"
        if [[ "${target}" == "${cwd}/"* ]]; then
            normalized="${target#"${cwd}/"}"
        else
            echo "Error: absolute path is outside the current project: ${target}" >&2
            return 1
        fi
    else
        normalized="${target#./}"
    fi

    if [[ "${normalized}" == *..* ]]; then
        echo "Error: path containing '..' is not allowed: ${target}" >&2
        return 1
    fi

    if [[ "${normalized}" != "${SCRATCH_ROOT}/"* ]]; then
        echo "Error: path is not under ${SCRATCH_ROOT}/: ${target}" >&2
        return 1
    fi

    # Collapse repeated slashes and strip trailing '/' and '/.' segments so
    # disguised forms of the bare root ('.claude/tmp//', '.claude/tmp/.',
    # '.claude/tmp/./') are all caught by the root check below.
    stripped="${normalized}"
    while [[ "${stripped}" == *//* ]]; do
        stripped="${stripped//\/\//\/}"
    done
    while [[ "${stripped}" == */ || "${stripped}" == */. ]]; do
        stripped="${stripped%/.}"
        stripped="${stripped%/}"
    done
    if [[ "${stripped}" == "${SCRATCH_ROOT}" ]]; then
        echo "Error: the bare ${SCRATCH_ROOT}/ root is not allowed: ${target}" >&2
        return 1
    fi

    if [[ "${physical}" -eq 1 ]]; then
        # Resolve the parent's physical (symlink-free) path so a symlinked
        # component cannot escape ${SCRATCH_ROOT}/. `pwd -P` is used instead
        # of `readlink -f` for portability.
        parent="${stripped%/*}"
        if ! resolved_parent="$(cd "${parent}" 2>/dev/null && pwd -P)"; then
            if [[ -e "${parent}" ]]; then
                echo "Error: parent directory exists but cannot be entered: ${target}" >&2
                return 1
            fi
            return 3
        fi
        scratch_real="$(cd "${SCRATCH_ROOT}" 2>/dev/null && pwd -P)" || {
            echo "Error: cannot resolve ${SCRATCH_ROOT}: ${target}" >&2
            return 1
        }
        case "${resolved_parent}" in
        "${scratch_real}" | "${scratch_real}"/*) ;;
        *)
            echo "Error: resolved path escapes ${SCRATCH_ROOT}/: ${target}" >&2
            return 1
            ;;
        esac
    fi

    printf '%s\n' "${stripped}"
}
