# cgh

*[日本語版 README](README_ja.md)*

A GitHub pull request workflow on top of [`creview`](../creview/README.md). Every skill takes a
pull request URL. Nothing goes to GitHub until you have seen it and told the skill to post it.
The plugin never approves, merges, pushes, or marks a thread resolved.

## Requirements

- The `creview` plugin, version 0.18.1 or later, which Claude Code installs with `cgh` as a
  dependency, and what it needs for a pull request: an authenticated GitHub CLI (`gh`), Git 2.41
  or later, `python3` (3.9 or later) on the `PATH`, and a clone with the pull request's
  repository as a remote. The skills refuse a pull request of any other repository.
- A pull request that is open when the skill starts. When it is merged after you push,
  `/cgh:respond` can still post its replies.
- A session started at the repository root.
- A project whose `.claude`, `.claude/tmp`, and `.claude/worktrees` are not symbolic links, even
  ones pointing inside the project: the bundled scripts refuse them with an error. To share
  configuration across working trees, keep it in `~/.claude/` instead.

## Skills

| Command | Purpose | Options |
|---------|---------|---------|
| `/cgh:review` | Review a pull request and post the triaged findings. | `--adversarial`, `--trust`, `--adr` |
| `/cgh:gate` | Judge whether a self-reviewed pull request can merge, and post PASS or BLOCK. | `--adversarial`, `--trust`, `--adr` |
| `/cgh:respond` | Fix what a pull request's reviews call for, and reply to them. | `--no-confirm`, `--trust`, `--adr` |
| `/cgh:resolve` | Verify the findings you raised, posted by `/cgh:review` or written by hand, and reply with the result. | `--trust` |

### `/cgh:review`

Runs `/creview:start`, then `/creview:triage`, shows what it would post, and posts on your
instruction.

Before the review, it collects the problems comments on the pull request already raise, yours and
everyone else's, people and AI alike. Triage leaves out a finding that raises one of them, with a
reason such as "Already raised (@name)", since whoever raised the problem can be expected to see
it through. The preview lists it under what is not posted, a Critical or Major one first and
marked ⚠️, and you can still select it. A finding stays when the code shows that the comment is
wrong about the problem's cause, location, or effect.

- **Event**: Request Changes when a posted finding is Critical or Major, otherwise Comment.
  It makes no LGTM judgment.
- **Content**: each comment holds the severity and finding ID (`Critical C-1`, `Major M-1`,
  `Minor mi-1`), the finding, and the estimate's recommendation, summarized for people. Cost,
  signals, and reviewer agents are left out.
- **Posted by default**: findings triaged Will Fix, including a Critical or Major finding the
  estimate downgraded, since the problem stays in the code.
  - Info, Won't Fix, and a downgraded Minor finding stay out unless you ask for them. The
    preview lists them with the reason.
- **Placement**:

| The finding's location | Where it goes |
|------------------------|---------------|
| A line in the diff | An inline comment |
| A line outside the diff, in a file in the diff | A file-level comment |
| A file outside the diff, or no file | The review body |

### `/cgh:gate`

A merge gate for code that has already been self-reviewed. It looks only for broken code,
regressions of existing behavior, changes the review could not read, and work left undone with
no issue recording it: a `TODO` in the code, an open item in the description, or a follow-up the
description or a code comment promises. Nice-to-have tests, refactoring, and style are not
findings. A residue that names an issue or a pull request counts as recorded. A conversation
comment does not record one. The focus is in [rules/gate-focus.md](rules/gate-focus.md).

It also reads every comment on the pull request, including threads marked resolved on GitHub. What
a discussion concludes has to end up in the code or the description, or be tracked in an issue or
ticket that the description, a code comment, or a comment by the author, an assignee, or you names.
Any other comment records nothing.

- A problem discussed and recorded this way is not raised again, unless the code shows the record
  wrong about it. Neither is one declined because its premise is wrong, when the code bears that
  out.
- A discussion with no such ending is raised as an unsettled discussion in place of the problem
  itself, and it blocks. A line in the description or a comment naming the tracking issue settles
  it.
- An agreed change or a promised follow-up counts whatever the topic. A declined comment counts
  when its problem is one the gate looks for, unless the code shows it absent. An unanswered one
  counts only when its problem is one the gate looks for and holds in the code.

- **BLOCK** (Request Changes): a posted finding or an earlier gate finding still unverified is
  blocking, or the pull request has merge conflicts.
- **PASS** (Comment): otherwise. PASS is not an approval.

Severity and blocking are separate. Critical, Major, and Minor say only how bad a problem's
consequence is. After triage, each finding is judged blocking or non-blocking on its own, and each
posted comment shows which, next to its severity:

- Work left undone with no issue, an unsettled discussion, and a change the review could not read
  always block. An unchecked item in the description is typically Minor and blocking.
- A security problem blocks unless the author or an assignee deferred it explicitly, in the
  description, by naming a tracking issue, or, for a decider, by a decline.
- Other broken code and regressions block, unless both of these hold: it occurs only under a
  special condition normal use does not reach or in a very short window, and deferring it is
  evident from the description or from a decline by the assignees or, with none, the author.
- A finding with no judgment blocks. You can change a judgment at the preview.

The verdict goes in the review body, and findings are placed as in `/cgh:review`.

Run it again after fixes until it passes. A later run verifies the earlier gate findings at the
current head with `/creview:resolve`, reports them in the review body, and reviews the whole
pull request again. To accept an earlier finding without a fix, tell the skill to waive it:
later runs do not report it again. Earlier findings already verified are checked again: one that
still holds is left out of the review body, and one that no longer holds counts as unverified
again. An open item in the description is verified from the description: it is resolved once the item is
gone or names an issue or a pull request.

### `/cgh:respond`

Runs `/creview:triage` on the pull request's comments, shows the result, and waits for your
confirmation. It then runs `/creview:respond --commit` and asks you to push. After you push, it
drafts one reply per comment, with what was done and the commit, with the fact that the problem
is no longer in the code, or with why no change was made.
It shows them and posts on your instruction.

- At the confirmation, you can exclude findings from the fixes: their replies say why, from the
  reason you give.
- When the triage leaves nothing to fix, it skips the confirmation and goes on to the replies.
- `--no-confirm` goes from the triage to the fixes without stopping. Replies still wait for your
  instruction, with or without it.
  - Anyone who can comment on the pull request can put text into the findings, and the
    confirmation is the last check before the fixes, so do not use it on a pull request you do
    not trust.
- A reply to a finding from a review body or an issue comment goes out as an issue comment that
  mentions its author, unless the author is a bot.
- The skill refuses to send replies until the pull request contains the fix commits. A rebase
  changes their hashes, so push them as they are. If you rebased or squashed them, say so, and
  the skill collects the commits again.
- A finding that was not addressed gets no reply. Neither does one whose comment the skill
  could not identify: the skill lists those.
- Findings come from comments by anyone, people and AI alike, such as CodeRabbit or Copilot, and
  triage judges from the conversation and the code whether each is already dealt with: the code
  no longer has the problem, its review was dismissed, the pull request's assignees (or, with
  none, its author) decided not to change it and said why, or the reviewer who raised it withdrew
  it.
  - Anyone else's word counts only when one of those people can be taken to have stated it, and
    the facts a reply states are checked against the code.
  - The report lists every finding set to Won't Fix, with its location, authors, and reason.
- A comment that already has an answer to the same effect, from anyone, with nothing after it
  reopening the matter, does not get another reply saying no change was made.
- `/creview:respond` builds and tests the pull request's code. For a pull request you do not
  trust, see the warnings in the [creview README](../creview/README.md).

### `/cgh:resolve`

Verifies with `/creview:resolve` the findings you raised, whether `/cgh:review` posted them or
you wrote them by hand, and no one else's. It shows the replies, and posts on your instruction.
Each reply names the commit checked at. When the code
follows the fix the finding recommended, the reply leaves out the details. Info findings are
not verified.

A sub-agent judges from the conversation where each finding stands: open, declined with a reason,
verified earlier, or withdrawn by you. It reads the replies in the thread and, for a finding in a
review body or an issue comment, the conversation outside threads.

A decline counts only from the pull request's assignees or, with none, its author, and anyone
else's word only when one of them can be taken to have stated it. Verification checks the facts a
decline states against the code.

Findings verified earlier are checked again on every run, since a later change can undo a fix. One
that still holds gets no reply; one that no longer holds gets a reply saying so. A decline stays
until a fix or a newer decline replaces it, and each run checks its reason. When a run finds the
reason flawed, `/cgh:respond` can answer again, with a fix or with a new reason.

## Language

Comments and replies go out in the language of the pull request's description. The preview
stays in the language you write in, and when the wording that goes out differs, the skill shows
that as well. Findings already in the description's language go out untranslated.

## `--adversarial`

Passed to `/creview:start`, it runs the reviewers in adversarial mode, where every Critical /
Major finding must state a concrete failure scenario. See the
[creview README](../creview/README.md).

## `--trust`

When HEAD is not at the pull request's head, the creview skills work in a worktree of the pull
request, which by default leaves out its agent files (`CLAUDE.md`, `CLAUDE.local.md`, `AGENTS.md`,
`.mcp.json`, and `.claude`). Findings in those files are then reviewed from the diff only, and
`/creview:respond` does not fix them. `--trust` keeps them in the worktree. It counts only when
your own chat message gives it.

Claude Code can load those files as instructions, skills, or settings, so use it only for a pull
request you trust, or in a sandbox. See the [creview README](../creview/README.md).

## `--adr`

Passed to `/creview:triage`, it lets the estimate record design decisions as ADR files next to
the review document. They stay local and are not posted. With `/cgh:respond`, the confirmation
after the triage names them so that you can edit them before the fixes, and `/creview:respond`
reads them. `--no-confirm` skips that chance. `/cgh:respond` also passes `--adr` to
`/creview:respond`, so that a design decision made while fixing gets an ADR file too.

## How state is kept

The state lives on the pull request, so a later run needs nothing from an earlier one.

- Where a finding stands is judged from the conversation and the code, since people and AI work
  on a pull request with or without these skills. A reply by hand counts as much as one from a
  skill.
- Comments carry no hidden markers, since nothing guarantees that one survives, stays unedited,
  or is not forged on a pull request worked on by several people and AI. Sub-agents judge from
  visible text only: HTML comments in anyone's comment are removed before they read it.
- `/cgh:review` looks at every comment and `/cgh:respond` handles every comment, whoever wrote it.
  `/cgh:resolve` checks only your own findings, and `/cgh:gate` only its own, while it reads every
  comment for discussions. Dismissing a review drops its findings from those checks and from those
  discussions.
- A thread marked resolved on GitHub counts as dealt with in `/cgh:respond`, and the skill reports
  how many it left out.
- A sub-agent reads which finding IDs your comments use, in context, from their visible text. New
  IDs number on from those, so an ID stays unique among your findings on a pull request, as far as
  that reading is right. The review document of `/cgh:review` numbers its own way, so an ID posted from it
  can differ from the ID in that document.
- `/cgh:respond` keeps these IDs.
  - Your own findings have the same ID in its review document, its preview, and its report.
  - A finding by anyone else takes a new ID, since IDs others write can collide with yours. The
    reply that answers it shows the ID, and later runs reuse it. Until then, the ID can change from
    run to run.
- `post` reads back what it sent and reports the URL of anything that reads back differently.

## Limitations

- A failed call during a post is resolved from the review's state on GitHub: a review that went
  out anyway counts as posted, and one still pending is deleted. When the state cannot be read,
  the skill says so and refuses to post the same draft again: check the pull request before you
  run it again.
- When the pull request moves between the review and the post, the skill refuses to post, and
  you run it again: the findings' line numbers belong to the reviewed head.
- `/cgh:gate` waits for GitHub to compute whether the pull request merges, and refuses to post
  when GitHub does not finish, or when the verdict has changed since the preview.
- `/cgh:gate` and `/cgh:resolve` stop when there are earlier findings to check
  and HEAD holds commits the pull request does not have, or uncommitted changes at its head: the
  result would describe code the pull request does not contain.
- GitHub refuses Request Changes on your own pull request, so the skill sends Comment there. With
  `/cgh:gate`, the verdict is still in the review body.
- A PASS goes out as Comment, which does not clear a Request Changes you sent earlier: it stays
  on GitHub until it is dismissed, and dismissing it takes that review's findings out of later
  runs.
- GitHub allows one pending review per user on a pull request. Submit or discard yours first.
- Reading finding IDs and judging where findings stand take sub-agents on every run, cost tokens,
  and can vary between runs. An ID removed from a comment's text, or misread, can make a finding
  take a new ID.
- Text in the comments comes from reviewers that read the pull request. The skill removes `@`
  mentions outside code before posting, which is not certain to catch every one, and the rest goes
  out as written: a `@` mention left in it notifies that person, and an HTML comment in it is
  hidden on GitHub. Read the preview before you post it.
