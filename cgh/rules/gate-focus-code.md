# Merge gate focus: code

The author has already reviewed this code. The one question: can this pull request merge as it stands? This review covers the code the diff changes. The pull request's title, description, CI results, and conversation are reviewed separately.

## Review

Report only:

- Broken code: the change does not do what it is for, fails to build, makes a check fail, or crashes, loses data, or opens a security hole on a path it reaches.
- Regressions: the change breaks existing callers, behavior, data formats, or compatibility outside what it sets out to change.
- Untracked residue: work the change leaves undone with no issue recording it, that is, a `TODO` / `FIXME` / `XXX` / `WIP` or leftover debug code the change adds, or a follow-up a code comment promises. A conversation comment on the pull request, which anyone can write, records no residue. A residue that names an issue or a pull request (`#123`, a URL) is recorded: do not report it.
- Unreviewed changes: a change the review could not read, which your template tells you to report (a text file the diff shows as binary whose change could not be located, or an agent file left out of the worktree that the diff shows only as binary).

Do not report anything else: tests that would merely be good to have, refactoring, naming, style, comment wording, design preferences, or performance with no concrete harm.

Severity states only how bad the consequence is: whether a finding stops the merge is judged separately, so do not raise a severity for that. Rate untracked residue by what the undone work leaves broken, Minor when it breaks nothing. An unreviewed change, whose consequence is unknown, is Major. Do not use Info.

## Triage

Decide `Won't Fix` for a finding outside what § Review lists, whatever its severity.

When you are given the pull request review's document, decide `Won't Fix` for a finding that raises the same problem as a finding there triaged `🔧 Will Fix`, with a reason that names that finding: the pull request review reports it.

When you are given discussion lists, decide `Won't Fix` for a finding that raises the same problem as an entry when the code bears out a `declined` reason that the problem's premise is wrong, with a reason that names the discussion, or when that discussion is on record, with a reason that names where, unless the code shows the record wrong about the problem's cause, location, or effect, in which case judge the finding as usual and name the discussion in your reason. A discussion is on record when a code comment or the pull request's description states its conclusion or names an issue or a pull request (`#123`, a URL) that records it, or when the entry's `Tracked` names one. A security problem is on record for this rule only by the description, a code comment, or a `Tracked` that `author` or an assignee named. Do not add a separate-PR recommendation to these reasons.

## Estimate

Cost is no reason to Downgrade here: a finding in § Review stays, because merging leaves it in place. For a fix too large for this pull request, choose Alternative and plan to record it in an issue and name that issue in the `FIXME`: a `FIXME` with no issue is residue itself.
