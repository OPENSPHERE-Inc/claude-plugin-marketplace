# Merge gate focus

The author has already reviewed this code. The one question: can this pull request merge as it stands?

## Review

Report only:

- Broken code: the change does not do what it is for, fails to build, makes a check fail, or crashes, loses data, or opens a security hole on a path it reaches.
- Regressions: the change breaks existing callers, behavior, data formats, or compatibility outside what it sets out to change.
- Untracked residue: work left undone with no issue recording it. That covers a `TODO` / `FIXME` / `XXX` / `WIP` or leftover debug code the change adds, an unchecked task or TODO in the description, and a follow-up the description or a code comment promises. A conversation comment on the pull request, which anyone can write, neither creates a residue nor records one. A residue that names an issue or a pull request (`#123`, a URL) is recorded: do not report it.
- Unreviewed changes: a change the review could not read, which your template tells you to report (a text file the diff shows as binary whose change could not be located, or an agent file left out of the worktree that the diff shows only as binary).

Report a residue in the description that has no changed line with the location `PR`, quoting the item, in place of your template's rules that tie a finding to a changed line and a `file_path:line`.

Do not report anything else: tests that would merely be good to have, refactoring, naming, style, comment wording, design preferences, or performance with no concrete harm.

Severity: Critical or Major for what must stop the merge, with untracked residue and unreviewed changes at Major; Minor for a real problem that need not stop it. Do not use Info.

## Triage

Decide `Won't Fix` for a finding outside what § Review lists, whatever its severity. A residue at the location `PR` has no code to judge it by: judge it from the text it quotes.

## Estimate

Cost is no reason to Downgrade here: a finding in § Review stays, because merging leaves it in place. For a fix too large for this pull request, choose Alternative and plan to record it in an issue and name that issue in the `FIXME`: a `FIXME` with no issue is residue itself. For a residue at the location `PR`, plan to update the description or record the item in an issue.
