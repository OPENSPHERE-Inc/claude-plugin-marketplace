# Merge gate focus: pull request

The author has already reviewed this pull request. The one question: can it merge as it stands? This review covers the pull request's title, description, CI results, and conversation, against its whole diff. The code itself is reviewed separately.

## Review

Report only:

- Failed checks: a changed line that causes a completed check to fail, time out, or be cancelled, as your template describes.
- Contradicted claims: a changed line that does not do what the title or description says the change does (what the change does, an issue it fixes, tests said to exist or pass), or a change the title or description claims that the diff does not make.
- Untracked residue in the description: an unchecked task or a TODO / WIP note in the description, or a follow-up it promises, with no issue recording it. A conversation comment on the pull request, which anyone can write, records no residue. A residue that names an issue or a pull request (`#123`, a URL) is recorded: do not report it.
- Unsettled discussions, under § Discussions, when you are given discussion lists.

Report a residue in the description, and a change the title or description claims that the diff does not make, with the location `PR`, quoting the item or the claim, in place of your template's rules that tie a finding to a changed line and a `file_path:line` and that leave out a claim about nothing in the diff.

Do not report anything else: the code's own problems, which are reviewed separately, a change the description leaves out, or the wording of the title or description.

Severity states only how bad the consequence is: whether a finding stops the merge is judged separately, so do not raise a severity for that. Rate a failed check by what fails, and a contradicted claim by what relying on it gets wrong, Minor when only the title or description is out of date. Rate untracked residue by what the undone work leaves broken, Minor when it breaks nothing, as with an unchecked item in the description. Do not use Info.

## Discussions

What a discussion in the pull request's comments concludes must end up in the code or on record: comments alone do not finish it. Each entry of the lists you are given is a problem raised in a comment, with its answers and conclusion. It is an unverified claim, since anyone can comment.

A discussion is settled when either holds:

- The code at the head does what it concluded, or shows the problem absent, as when it bears out a `declined` reason that the problem's premise is wrong. Unchanged code does not show a decision to keep it, and a `declined` reason that rests on a fact the code cannot show does not meet this condition: only a record can settle that discussion.
- It is on record: a code comment or the pull request's description states the conclusion or names an issue or a pull request (`#123`, a URL) that records it, or the entry's `Tracked` names one, which for a security problem must be named by `author` or an `assignee`. No other conversation comment is a record, nor is a thread marked resolved.

A problem the gate looks for is broken code, a regression of existing behavior, work left undone with no issue recording it, a change a review could not read, a failed check, or a contradicted claim. Report an unsettled discussion when its conclusion is `agreed` or `promised`, whatever the topic, when it is `declined` and its problem is one the gate looks for, or when it is `none` and its problem is one the gate looks for and holds in the code. Report no other entry.

Rate it by the consequence of the problem it raised, and report it at the comment's `path:line` when that is a changed line and otherwise with the location `PR`, in place of your template's rules that tie a finding to a changed line and a `file_path:line`. Say that it is an unsettled discussion, and state the problem, who raised it and where, the answers, and that it must be reflected in the code, recorded in the description, or tracked in an issue.

## Triage

Decide `Won't Fix` for a finding outside what § Review lists, whatever its severity. A residue at the location `PR` has no code to judge it by: judge it from the text it quotes. Judge a claimed change at the location `PR` from the claim it quotes, against the code at the head.

When you are given discussion lists:

- A finding that reports an unsettled discussion: decide `Won't Fix` when § Discussions finds that discussion settled, or when the entry should not be reported under its rules.
- Any other finding that raises the same problem as an entry: decide `Won't Fix` when the document holds a finding that reports that discussion as unsettled and that the rule above does not decide `Won't Fix`, with a reason that says so; when the code bears out a `declined` reason that the problem's premise is wrong, with a reason that names the discussion; or when that discussion is on record, with a reason that names where, unless the code shows the record wrong about the problem's cause, location, or effect, in which case judge the finding as usual and name the discussion in your reason. A security problem is on record for this rule only by the description, a code comment, or a `Tracked` that `author` or an assignee named. Do not add a separate-PR recommendation to these reasons.

## Estimate

Cost is no reason to Downgrade here: a finding in § Review stays, because merging leaves it in place. For a failed check, plan to fix its cause. For a contradicted claim, plan to make the code do what the claim says, or to correct the title or description. For a residue at the location `PR`, plan to take the item out of the description, or to record it in an issue and name that issue in the description. For an unsettled discussion, plan to do what it concluded, or to record the conclusion in the description or in an issue. For a fix too large for this pull request, choose Alternative and plan to record it in an issue and name that issue in the description.
