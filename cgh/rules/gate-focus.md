# Merge gate focus

The author has already reviewed this code. The one question: can this pull request merge as it stands?

## Review

Report only:

- Broken code: the change does not do what it is for, fails to build, makes a check fail, or crashes, loses data, or opens a security hole on a path it reaches.
- Regressions: the change breaks existing callers, behavior, data formats, or compatibility outside what it sets out to change.
- Untracked residue: work left undone with no issue recording it. That covers a `TODO` / `FIXME` / `XXX` / `WIP` or leftover debug code the change adds, an unchecked task or TODO in the description, and a follow-up the description or a comment promises. A residue that names an issue or a pull request (`#123`, a URL) is recorded: do not report it.

Do not report anything else: tests that would merely be good to have, refactoring, naming, style, comment wording, design preferences, or performance with no concrete harm.

Severity: Critical or Major for what must stop the merge, with untracked residue at Major; Minor for a real problem that need not stop it. Do not use Info.

## Triage

Decide `Won't Fix` for a finding outside what § Review lists, whatever its severity.

## Estimate

Cost is no reason to Downgrade here: a finding in § Review stays, because merging leaves it in place. For a fix too large for this pull request, choose Alternative and plan to record it in an issue and name that issue in the `FIXME`: a `FIXME` with no issue is residue itself.
