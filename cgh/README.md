# cgh

*[日本語版 README](README_ja.md)*

A GitHub pull request workflow on top of [`creview`](../creview/README.md). Every skill takes a
pull request URL. Nothing goes to GitHub until you have seen it and told the skill to post it.
The plugin never approves, merges, pushes, or marks a thread resolved.

## Requirements

- The `creview` plugin, which Claude Code installs with `cgh` as a dependency, and what it needs
  for a pull request: an authenticated GitHub CLI (`gh`), Git 2.41 or later, and a clone with
  the pull request's repository as a remote.
- A pull request that is open.
- A session started at the repository root.

## Skills

| Command | Purpose | Options |
|---------|---------|---------|
| `/cgh:review` | Review a pull request and post the triaged findings. | `--adversarial` |
| `/cgh:gate` | Judge whether a self-reviewed pull request can merge, and post PASS or BLOCK. | `--adversarial` |
| `/cgh:respond` | Fix what a pull request's reviews call for, and reply to them. | |
| `/cgh:resolve` | Verify the findings `/cgh:review` posted, and reply with the result. | |

### `/cgh:review`

Runs `/creview:start`, then `/creview:triage`, shows what it would post, and posts on your
instruction.

- **Event**: Request Changes when a posted finding is Critical or Major, otherwise Comment.
  It makes no LGTM judgment.
- **Content**: each comment holds the finding ID (`C-1`, `M-1`, `mi-1`), the finding, and the
  recommendation from the estimate. Cost, signals, and reviewer agents are left out.
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
regressions of existing behavior, and work left undone with no issue recording it: a `TODO` in
the code, an open item in the description, or a promised follow-up. Nice-to-have tests,
refactoring, and style are not findings. A residue that names an issue or a pull request counts
as recorded. The focus is in [rules/gate-focus.md](rules/gate-focus.md).

- **BLOCK** (Request Changes): a posted finding or an earlier gate finding still unverified is
  Critical or Major, or the pull request has merge conflicts.
- **PASS** (Comment): otherwise. PASS is not an approval.

The verdict goes in the review body, and findings are placed as in `/cgh:review`.

Run it again after fixes until it passes. A later run verifies the earlier gate findings at the
current head with `/creview:resolve`, reports them in the review body, and reviews the whole
pull request again. To accept an earlier finding without a fix, tell the skill to waive it.

### `/cgh:respond`

Runs `/creview:triage` on the pull request's comments, then `/creview:respond --commit`, and asks
you to push. After you push, it drafts one reply per comment, with what was done and the commit,
or with why no change was made. It shows them and posts on your instruction.

- The triage result is not a stop: review the commits before you push them.
- A reply to a finding from a review body or an issue comment goes out as an issue comment that
  mentions its author.
- `post` refuses to send replies until the pull request contains the fix commits. A rebase
  changes their hashes, so push them as they are.
- A finding that was not addressed gets no reply. Neither does one whose comment the drafter
  could not identify: the skill lists those.
- `/creview:respond` builds and tests the pull request's code. For a pull request you do not
  trust, see the warnings in the [creview README](../creview/README.md).

### `/cgh:resolve`

Verifies the findings `/cgh:review` posted under your account with `/creview:resolve`, shows the
replies, and posts on your instruction. Each reply names the commit checked at. When the code
follows the fix the finding recommended, the reply leaves out the details.

## How state is kept

The state lives on the pull request, so a later run needs nothing from an earlier one.

- A posted finding carries a hidden marker with its ID and location, and a verification carries
  one with the IDs it closes. Only markers in your own comments count.
- `/cgh:gate` and `/cgh:resolve` read back only findings carrying a marker: comments you wrote
  by hand are not checked. Dismissing a review drops its findings.
- Finding IDs number on from the earlier ones, so an ID stays unique on a pull request. An ID on
  the pull request can therefore differ from the ID in the local review document.

## Limitations

- When the pull request moves between the review and the post, `post` refuses, and you run the
  skill again: the findings' line numbers belong to the reviewed head.
- `/cgh:gate` and `/cgh:resolve` stop when earlier findings need checking and HEAD holds commits
  the pull request does not have, or uncommitted changes at its head: the result would describe
  code the pull request does not contain.
- GitHub refuses Request Changes on your own pull request, so the skill sends Comment there. With
  `/cgh:gate`, the verdict is still in the review body.
- GitHub allows one pending review per user on a pull request. Submit or discard yours first.
- Text in the comments comes from reviewers that read the pull request. A script quotes `@`
  mentions in it and escapes HTML comments, but read the preview before you post it.
