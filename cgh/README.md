# cgh

*[日本語版 README](README_ja.md)*

A GitHub pull request workflow on top of [`creview`](../creview/README.md). Every skill takes a
pull request URL. Nothing goes to GitHub until you have seen it and told the skill to post it.
The plugin never approves, merges, pushes, or marks a thread resolved.

## Requirements

- The `creview` plugin, version 0.17.0 or later, which Claude Code installs with `cgh` as a
  dependency, and what it needs for a pull request: an authenticated GitHub CLI (`gh`), Git 2.41
  or later, `python3` (3.9 or later) on the `PATH`, and a clone with the pull request's
  repository as a remote. The skills refuse a pull request of any other repository.
- A pull request that is open when the skill starts. When it is merged after you push,
  `/cgh:respond` can still post its replies.
- A session started at the repository root.

## Skills

| Command | Purpose | Options |
|---------|---------|---------|
| `/cgh:review` | Review a pull request and post the triaged findings. | `--adversarial`, `--trust`, `--adr` |
| `/cgh:gate` | Judge whether a self-reviewed pull request can merge, and post PASS or BLOCK. | `--adversarial`, `--trust`, `--adr` |
| `/cgh:respond` | Fix what a pull request's reviews call for, and reply to them. | `--no-confirm`, `--trust`, `--adr` |
| `/cgh:resolve` | Verify the findings `/cgh:review` posted, and reply with the result. | `--trust` |

### `/cgh:review`

Runs `/creview:start`, then `/creview:triage`, shows what it would post, and posts on your
instruction. A later run does not report again the findings already posted and not yet verified.

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
comment neither creates a residue nor records one. The focus is in
[rules/gate-focus.md](rules/gate-focus.md).

- **BLOCK** (Request Changes): a posted finding or an earlier gate finding still unverified is
  Critical or Major, or the pull request has merge conflicts.
- **PASS** (Comment): otherwise. PASS is not an approval.

The verdict goes in the review body, and findings are placed as in `/cgh:review`.

Run it again after fixes until it passes. A later run verifies the earlier gate findings at the
current head with `/creview:resolve`, reports them in the review body, and reviews the whole
pull request again. To accept an earlier finding without a fix, tell the skill to waive it:
later runs do not report it again. An open item in the description cannot be verified from the code: update the description, then
waive it.

### `/cgh:respond`

Runs `/creview:triage` on the pull request's comments, shows the result, and waits for your
confirmation. It then runs `/creview:respond --commit` and asks you to push. After you push, it
drafts one reply per comment, with what was done and the commit, or with why no change was made.
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
  mentions its author.
- The skill refuses to send replies until the pull request contains the fix commits. A rebase
  changes their hashes, so push them as they are. If you rebased or squashed them, say so, and
  the skill collects the commits again.
- A finding that was not addressed gets no reply. Neither does one whose comment the drafter
  could not identify: the skill lists those.
- A comment that already has a reply from the skill does not get another one saying no change
  was made.
- `/creview:respond` builds and tests the pull request's code. For a pull request you do not
  trust, see the warnings in the [creview README](../creview/README.md).

### `/cgh:resolve`

Verifies the findings `/cgh:review` posted under your account with `/creview:resolve`, shows the
replies, and posts on your instruction. Each reply names the commit checked at. When the code
follows the fix the finding recommended, the reply leaves out the details. Info findings are
not verified.

## Language

Comments and replies go out in the language of the pull request's description. The preview
stays in the language you write in, and a second file next to it holds the wording that goes
out. Findings already in the description's language go out untranslated.

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

- A posted finding carries a hidden marker with its ID and location, a verification or a waiver
  one with the IDs it closes, and a reply one with the comment it answers. Only markers in your
  own comments count.
- `/cgh:gate` and `/cgh:resolve` read back only findings carrying a marker: comments you wrote
  by hand are not checked. Dismissing a review drops its findings.
- Finding IDs number on from the earlier ones, so an ID stays unique on a pull request. An ID on
  the pull request can therefore differ from the ID in the local review document.

## Limitations

- A failed call during a post is resolved from the review's state on GitHub: a review that went
  out anyway counts as posted, and one still pending is deleted. When the state cannot be read,
  the skill says so and refuses to post the same draft again: check the pull request before you
  run it again.
- When the pull request moves between the review and the post, the skill refuses to post, and
  you run it again: the findings' line numbers belong to the reviewed head.
- `/cgh:gate` waits for GitHub to compute whether the pull request merges, and refuses to post
  when GitHub does not finish, or when the verdict has changed since the preview.
- `/cgh:review`, `/cgh:gate`, and `/cgh:resolve` stop when earlier findings are not yet verified
  and HEAD holds commits the pull request does not have, or uncommitted changes at its head: the
  result would describe code the pull request does not contain.
- GitHub refuses Request Changes on your own pull request, so the skill sends Comment there. With
  `/cgh:gate`, the verdict is still in the review body.
- A PASS goes out as Comment, which does not clear a Request Changes you sent earlier: it stays
  on GitHub until it is dismissed, and dismissing it takes that review's findings out of later
  runs.
- GitHub allows one pending review per user on a pull request. Submit or discard yours first.
- Text in the comments comes from reviewers that read the pull request. A script quotes `@`
  mentions in it and escapes HTML comments, but read the preview before you post it.
