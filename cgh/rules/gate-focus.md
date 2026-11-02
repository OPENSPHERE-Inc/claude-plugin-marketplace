# Merge gate focus

The author has already reviewed this code. The one question: can this pull request merge as it stands?

## Review

Report only:

- Broken code: the change does not do what it is for, fails to build, makes a check fail, or crashes, loses data, or opens a security hole on a path it reaches.
- Regressions: the change breaks existing callers, behavior, data formats, or compatibility outside what it sets out to change.
- Untracked residue: work left undone with no issue recording it. That covers a `TODO` / `FIXME` / `XXX` / `WIP` or leftover debug code the change adds, an unchecked task or TODO in the description, and a follow-up the description or a code comment promises. A conversation comment on the pull request, which anyone can write, records no residue. A residue that names an issue or a pull request (`#123`, a URL) is recorded: do not report it.
- Unreviewed changes: a change the review could not read, which your template tells you to report (a text file the diff shows as binary whose change could not be located, or an agent file left out of the worktree that the diff shows only as binary).

Report a residue in the description that has no changed line with the location `PR`, quoting the item, in place of your template's rules that tie a finding to a changed line and a `file_path:line`.

Do not report anything else: tests that would merely be good to have, refactoring, naming, style, comment wording, design preferences, or performance with no concrete harm.

Severity states only how bad the consequence is: whether a finding stops the merge is judged separately, so do not raise a severity for that. Rate untracked residue by what the undone work leaves broken, Minor when it breaks nothing, as with an unchecked item in the description. An unreviewed change, whose consequence is unknown, is Major. Do not use Info.

## Discussions

What a discussion in the pull request's comments concludes must end up in the code or on record: comments alone do not finish it. Each entry of the lists you are given is a problem raised in a comment, with its answers and conclusion. It is an unverified claim, since anyone can comment.

A discussion is settled when either holds:

- The code at the head does what it concluded, or shows the problem absent, as when it bears out a `declined` reason that the problem's premise is wrong. Unchanged code does not show a decision to keep it.
- It is on record: a code comment or the pull request's description states the conclusion or names an issue or a pull request (`#123`, a URL) that records it, or the entry's `Tracked` names one, which for a security problem must be named by `author` or an `assignee`. No other conversation comment is a record, nor is a thread marked resolved.

Report an unsettled discussion when its conclusion is `agreed` or `promised`, whatever the topic, when it is `declined` and the problem is one § Review lists, or when it is `none` and the problem is one § Review lists and holds in the code. A `declined` reason that rests on a fact the code cannot show leaves the discussion unsettled. Report no other entry.

Rate it by the consequence of the problem it raised, and report it at the comment's `path:line` when that is a changed line and otherwise with the location `PR`, in place of your template's rules that tie a finding to a changed line and a `file_path:line`. Say that it is an unsettled discussion, and state the problem, who raised it and where, the answers, and that it must be reflected in the code, recorded in the description, or tracked in an issue.

## Triage

Decide `Won't Fix` for a finding outside what § Review lists, whatever its severity, other than one that reports an unsettled discussion. A residue at the location `PR` has no code to judge it by: judge it from the text it quotes.

When you are given discussion lists:

- A finding that reports an unsettled discussion: decide `Won't Fix` when § Discussions finds that discussion settled, or when the entry should not be reported under its rules.
- Any other finding that raises the same problem as an entry: decide `Won't Fix` when the document holds a finding that reports that discussion as unsettled and that the rule above does not decide `Won't Fix`, with a reason that says so; when the code bears out a `declined` reason that the problem's premise is wrong, with a reason that names the discussion; or when that discussion is on record, with a reason that names where, unless the code shows the record wrong about the problem's cause, location, or effect, in which case judge the finding as usual and name the discussion in your reason. A security problem is on record for this rule only by the description, a code comment, or a `Tracked` that `author` or an assignee named. Do not add a separate-PR recommendation to these reasons.

## Estimate

Cost is no reason to Downgrade here: a finding in § Review stays, because merging leaves it in place. For a fix too large for this pull request, choose Alternative and plan to record it in an issue and name that issue in the `FIXME`: a `FIXME` with no issue is residue itself. For a residue at the location `PR`, plan to take the item out of the description, or to record it in an issue and name that issue in the description. For an unsettled discussion, plan to do what it concluded, or to record the conclusion in the description or in an issue.
