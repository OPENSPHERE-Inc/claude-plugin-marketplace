# creview

*[日本語版 README](README_ja.md)*

A multi-agent parallel code review workflow for Claude Code.

## Skills

| Command | Maps from | Purpose |
|---------|-----------|---------|
| `/creview:start` | `parallel-review` | Run a parallel code review of local changes or a GitHub pull request; produce a review document with metadata markers. |
| `/creview:triage` | `review-respond` (triage + estimate) | Triage and estimate findings; persist `triage` / `estimate` into the document. |
| `/creview:respond` | `review-respond` (fix) | Fix Will-Fix / Maintain / Alternative findings; verify the build; persist `status`. |
| `/creview:resolve` | `review-resolve` | Verify fix resolutions against the source; persist `verification`. |
| `/creview:rounds` | `review-rounds` | Automatically iterate start → triage → respond → resolve across rounds. |

Every command requires a session started at the repository root, with or
without `--worktree`; started from a subdirectory of the repository, it stops
with an error.

`review-respond` was split into two skills. Run `/creview:triage <doc>`
first; review the persisted decisions in the document; then run
`/creview:respond <doc>`. There is no confirmation prompt inside either skill —
the split itself is the review gate. `/creview:respond` keeps the `--commit`
option.

The review document records the branch the review ran on in a
`- **Branch:** {branch}` header bullet, for a review of local changes as well.
Run on their own while that branch is not checked out, `/creview:triage`,
`/creview:respond`, and `/creview:resolve` work in a temporary worktree on it,
where `/creview:respond` commits its fixes to that branch. The header bullets
are described in full after the pull request review below.

`/creview:start` takes an `--adversarial` option (default OFF) that runs the
reviewers in adversarial mode, where every Critical / Major finding must state
a concrete failure scenario; `/creview:rounds` accepts the same flag and passes
it through to `/creview:start`. `/creview:triage` is adversarial
unconditionally: the triage sub-agent proposes a verdict, the findings are
split into batches of up to eight and three challenge sub-agents per batch
independently argue the opposite where they can, and an adjudication sub-agent
decides the final verdict. A proposed verdict is overturned only when at least
two of its own batch's three challenges call for it and the adjudicator
confirms the facts they cite.

`/creview:start` also bounds how much diff a single reviewer owns. When the
change exceeds 800 changed lines or 20 changed files, the scope-analysis
sub-agent partitions the changed files into at most eight cohesive review
scopes of up to 400 changed lines / 10 files each and picks reviewers per
scope, so a large change is reviewed slice by slice rather than sampled by
reviewers that stop exploring once they have produced a few findings. A
smaller change stays a single scope.

Every changed file is assigned to reviewers, including a change with no added
or removed lines, such as a binary file, a mode change, or an empty file added
or deleted. A change that touches no file launches no reviewer and yields a
review document with only its header and no severity sections. For a binary
file the diff states only that it changed. The scope-analysis sub-agent picks the
reviewers for such a file from what uses the file in the source as well as
from its extension, and each reviewer judges from that context and its own
perspective whether the file needs review, for example whether an updated
image changes a web page's layout or lacks the resolution its target DPI
needs, and reads the file when it needs review. A reviewer can view an image,
but judges other binary formats, such as fonts or archives, from their uses
only.

Git also treats as binary a text file with a NUL byte in its first 8,000 bytes
and a path that `.gitattributes` marks `binary` or `-diff`, so the diff does
not show its content. A reviewer reads such a text file in full and reviews it
as text, whatever uses it; for a modified one, whose changed lines the diff
does not show, it also reports as a finding that the change could not be
located. It reports the same finding when it cannot view such a file in full,
whether the file is added or modified.

`/creview:start` also takes a GitHub pull request URL
(`https://{host}/{owner}/{repo}/pull/{number}`) as its review target and then
reviews that pull request: the diff from its merge base to its head commit.
The pull request must be open, its repository on its host must be a remote of
the current clone, and the GitHub CLI (`gh`) must be authenticated for that
host. Reviewing a pull request requires Git 2.41 or later; with an older Git
the run stops with an error. `--base` and `--range` cannot be combined with a
pull request URL.
The diff is taken without rename detection, with the `.gitattributes` of the
merge base, and with every change of the commit a submodule points to, so
neither an exact rename nor the pull request's `.gitmodules` or `.gitattributes`
can hide a change from the reviewers. For a submodule, the diff shows only its
old and new commits, not the changes to the files inside it. A reviewer reads
a text file that the diff shows as binary from the checked-out pull request.

- When HEAD is the pull request's head commit, the working tree is reviewed
  in place; uncommitted changes to tracked files stop the run with an error.
- Otherwise the head commit is checked out, detached, in a temporary worktree
  under `.claude/worktrees/`, with git hooks and the filter drivers of your git
  configuration disabled, Git LFS smudging skipped, and symbolic links checked
  out as plain files holding the link target. The worktree is removed, with
  hooks and filter drivers disabled again, at the end of the run. It belongs to
  this run only and is unrelated to `/creview:rounds --worktree`.
  - The review document and the working directory stay in the main working
    tree's `.claude/tmp/`, and the project's `.claude/agents/` are read from
    the main working tree.
  - The checkout leaves out the agent files: every file and directory named
    `CLAUDE.md`, `CLAUDE.local.md`, `AGENTS.md`, `.mcp.json`, or `.claude`, in
    any letter case and at any depth. Claude Code or another agent can load
    them as instructions, skills, or settings once a sub-agent works in the
    worktree.
    - The reviewers see the pull request's changes to them in the diff only.
      When the diff shows one only as binary, they report as a finding that
      its content could not be reviewed.
    - `--trust` checks them out as well.
    - To review a pull request's agent configuration with those files in
      place, run the review in a sandbox, either with `--trust` or with the
      head commit checked out in your working tree for an in-place review.

One more reviewer runs alongside the code reviewers: the bundled
`pr-description-reviewer`, which reviews the change in the light of the pull
request's title and description and its CI results.

- It reports claims the change does not bear out, information a reviewer
  needs that the description leaves out, open task items, and failed checks,
  tracing a failure to its cause through the failed GitHub Actions job's log.
- It reads the pull request's comments and reviews for context only; they are
  not review targets.
- Every finding is anchored at a changed line of code and quotes the
  description text or CI output it rests on. A problem that no changed line
  points at, such as a claim about nothing in the diff or a failed check whose
  cause lies outside the change, is not reported.
- It runs with Read, Glob, Grep, and Write only, without shell or network
  access.

Every creview sub-agent is told to treat the pull request's text — its title,
description, comments, CI output, commit messages, and the lines it adds or
changes in files — and quotes of it in the review document as data, and to
change nothing on GitHub or any other remote. This includes the sub-agents of
`/creview:triage`, `/creview:respond`, and `/creview:resolve` when run
separately on the review document. In a worktree review, the checked-out
files, including the agent files checked out under `--trust`, are data as well,
and the sub-agents are told to run none of them and to run no git command in
the worktree. These are instructions, not enforcement: for a pull request you
do not trust, also rely on your environment (a sandbox, hooks, or permission
rules).

During a worktree review, and while `/creview:triage`, `/creview:respond`, or
`/creview:resolve` work in a worktree of a pull request (see below), the
session's working directory is the worktree.
Claude Code hooks, which fire on the sub-agents' tool calls as well, and the
status line command run there. A command they run relative to the current
directory, such as `npm run lint`, `./scripts/check.sh`, or `git status`,
therefore runs on the pull request's files without the protections above. For
a pull request you do not trust, turn such commands off, or write them against
`$CLAUDE_PROJECT_DIR` or an absolute path. The worktree lies under
`.claude/worktrees/` in your project, so a command that scans the whole
project, such as a test runner or a formatter run on `.`, must also leave that
directory out.

The review document records the pull request in a header bullet of the form
`- **PR:** {url} (head {head_sha}, base {merge_base})`, and the branch the
review ran on in a `- **Branch:** {branch}` bullet. A worktree review runs on a
detached HEAD and records no branch. Nor does a review of a commit range that
ends at a commit other than HEAD. A branch whose name has a character other
than a letter, a digit, `_`, `.`, `/`, `+`, `@`, or `-` is never recorded.
A `- **Trust:** on` or `off` bullet
records whether the reviewed tree had the agent files: `on` for an in-place
review or a worktree review with `--trust`, `off` for a worktree review without
it. Run on their own, `/creview:triage`, `/creview:respond`, and
`/creview:resolve` locate the document's code from the PR and Branch bullets:

- With a Branch bullet, they work in place when that branch is checked out,
  and otherwise in a temporary worktree on that local branch under
  `.claude/worktrees/`.
  - Without a local branch of that name, for example after the branch was
    deleted or for a review run in another clone, they stop with an error;
    create the branch again, such as from its remote branch, and rerun the
    skill.
- With a PR bullet only, they work in place when HEAD contains the head
  commit, and otherwise in a temporary worktree at the head commit.
  - For that worktree, the pull request must still be open with that head
    commit, which they check with `gh`; review an updated pull request again.
- With neither, as for a review on a detached HEAD, they work on the current
  working tree.

A worktree for a document with a PR bullet holds the pull request's code and
is checked out like a worktree review: git hooks and filter drivers disabled,
Git LFS smudging skipped, symbolic links as plain files, and the agent files
left out unless the Trust bullet is `on`. The three skills take no `--trust`:
following the Trust bullet, they work with the files the review had, and a
document without one counts as `off`. To work with the agent files, review the
pull request again with `--trust`. Their sub-agents are told what a worktree
review's sub-agents are told, except that `/creview:respond`, which fixes,
builds, and tests the code, is not told to leave the files unrun and git
unused. It runs the pull request's code as it does in place, in the git and
build ways listed below other than the checkout itself: its own git commands,
such as `git status` and `git commit`, run the hooks, filter drivers, and
`core.fsmonitor` listed there, and its build and tests run the pull request's
build scripts and tests. It takes the format, build, and test commands from the
main working tree's `build-format.md`, `CLAUDE.md`, or `README.md`, not from
the pull request's files.

In a worktree, `/creview:respond` turns `--commit` on. For a document with a
PR bullet only, it commits to a local branch `creview-pr-{number}`, which it
creates at the head commit or uses when the branch already points there, and
it records that branch in a Branch bullet, so later runs work on the fixes.
Pushing the branch to the pull request is left to you. Run in place on a
branch for such a document, it records that branch the same way. With Trust
`off`, a finding whose fix needs a left-out agent file stays unfixed, and the
summary lists it with the reason.

At the end the worktree is removed and its branch kept; a worktree with
uncommitted changes is kept and its path reported. Like the
`/creview:rounds --worktree` worktree described below, the worktree is a fresh
checkout without gitignored dependencies, virtual environments, build
directories, `.env`, or the contents of submodules, so `/creview:respond`'s
build and tests must pass without them. Git also refuses to remove a
worktree in which submodules were initialized, so such a worktree is kept and
reported as well. The review document, the
working directory, and the project's `.claude/agents/` and `.claude/rules/`
stay in the main working tree. A branch checked out in another worktree, such
as one that `/creview:rounds --worktree` kept, cannot be checked out again:
start a session at that worktree's root and run the skill there. A worktree
under `.claude/worktrees/` that one of the three skills kept for its
uncommitted changes is the exception: commit or discard its changes, remove it
with the `gh-pr.py remove` command the error names, and run the skill again.
The three skills refuse to run in a session started in a pull request worktree
that creview added. Run by `/creview:rounds`, the three skills create no worktree and
work where the round works.

A checkout in your working tree has none of a worktree review's protections,
and the pull request's code can run, for example in these ways:

- Git runs hooks and filter drivers, starting with the checkout itself.
  - With a relative `core.hooksPath` (such as `.husky/_` or `.githooks`), the
    hooks come from the pull request's tree: the checkout runs its
    `post-checkout` hook, and `/creview:respond --commit` its `pre-commit`
    hook.
  - A hook manager installed in `.git/hooks/`, such as pre-commit, lefthook, or
    Husky v4, reads its configuration from the pull request's tree
    (such as `.pre-commit-config.yaml`, `lefthook.yml`, or `package.json`), so its hooks
    run the commands the pull request writes there, even without a
    `core.hooksPath`.
  - With a relative `core.fsmonitor`, git commands such as the checkout and
    `git status` run the pull request's version of that script.
  - The pull request's `.gitattributes` chooses which filters run.
- Claude Code can load the pull request's `CLAUDE.md`, `CLAUDE.local.md`,
  `AGENTS.md`, `.mcp.json`, and `.claude/**` as instructions, skills, or
  settings, along with the files they import through `@` references.
- `/creview:respond` runs the format, build, and test commands, and with them
  the pull request's build scripts and tests.
  - Without a `build-format.md`, it takes those commands from the checkout's
    `CLAUDE.md` or `README.md`.

creview assumes that, before you run it, you have checked the repository and
the pull request and trust them. The ways listed above and a worktree review's
protections only support that decision: they do not cover every way the pull
request's code or instructions can take effect, and they cannot guarantee that
a repository or pull request fetched from the network is safe. Keep the agent
safe through your environment, such as a sandbox and permission rules, and
check out a pull request you do not trust, and run `/creview:respond` on it,
only in a sandbox.

`/creview:triage` and `/creview:respond` take an `--adr` option (default OFF)
that permits creating ADR files recording design decisions next to the review
document (`{review-doc basename}-adr-{finding-id}.md`, skeleton in
`rules/adr-format.md`). At estimate time the estimate sub-agents create an ADR
for a finding whose fix commits to one of several viable approaches; the user
can edit the ADR files between `/creview:triage` and `/creview:respond`. ADR
files referenced from the review document's `Estimate:` metadata are read back
at fix time (a user-edited Decision overrides the estimated plan) and get
their Status / History updated regardless of the flag — on `/creview:respond`
the flag only permits creating a new ADR for a design decision that first
arises during implementation. A later round that revisits the same location
updates or supersedes the existing ADR instead of duplicating it.
`/creview:rounds` accepts the same flag and passes it through to both phases.

`/creview:rounds` takes an `--incremental` option (default OFF) that makes each
round after the first review only the commits added since the previous round
started, instead of re-reviewing the whole branch diff every round. Round 1 is
always the full branch diff. Enabling it enables `--commit`, since an
uncommitted fix is not part of any round's commit range. The narrowed range is
applied at diff-fetch time — `/creview:start` gains a `--range {from}..{to}`
option that collects only that commit range and skips the working-tree
sections — so reviewers never see the earlier rounds' already-reviewed code.

`/creview:rounds` iterates for at most `--max-rounds` rounds (default 10,
maximum 20). From Round 2 on, a divergence pattern detection gate runs after
triage: a sub-agent reads the past rounds' and the current round's review
documents and traces the chains in which a fix for a finding produces a
finding in a later round. A chain that spans three or more rounds without
shrinking, or in which a finding of the current round asks to revert a past
fix, is a divergence; one round can yield several. When at least one is
detected, an investigation sub-agent — resolved from the destination project's
agents like the other specialists — identifies the source of each divergence
and writes fix proposals to `divergence-round{N}.md` next to the review
documents. The loop then pauses as it does for `--confirm`, presents that
report, and waits for the instruction to continue; a fix policy given with
that instruction is passed on to the round's respond phase.

`/creview:rounds` takes a `--worktree[=branch]` option (default OFF) that runs
every round in a separate git worktree under `.claude/worktrees/`, so the
fixes never touch the main working tree's sources. The worktree checks out
`branch` — an existing local branch as is, or a new one created from the
current HEAD; without `=branch`, a new branch `creview-rounds-{timestamp}` is
created. The branch checked out in the main working tree cannot be used,
because git does not check out one branch in two worktrees. Enabling it
enables `--commit`. The review documents, the final report, and every phase's
working directory stay in the main working tree's `.claude/tmp/`, and the
destination project's `.claude/agents/` and `.claude/rules/` are read from
the main working tree.
Every sub-agent receives the worktree as its work target (`target_dir`) and
writes only under it, to its working directory, and to the output paths it is
given; any other path, the main working tree included, is read-only.
The worktree starts from committed state — the current HEAD for a new branch,
the tip of an existing one — so uncommitted changes in the main working tree
are not part of the run. Gitignored dependencies, virtual environments, build
directories, and `.env` are absent from the worktree as well, and so are the
contents of submodules, which `git worktree add` does not initialize; the build
and tests must therefore pass in a fresh checkout. Dependency installation and
similar setup can go in the configure command of `build-format.md`, but
configure runs only at the start of the build stage — after the format
command, and not at all when the build is skipped or none is declared — so the
format command and tests that run without a build cannot rely on it. A build
or test failure caused by such a missing prerequisite is not fixed in the
source: respond stops its build-fix loop and records the failure as the
round's workflow warning, which the final report lists. Each round's review
document records the worktree's branch, so `/creview:triage`,
`/creview:respond`, and `/creview:resolve` run on it later work in a worktree
on that branch. At the
end the worktree is removed and the branch is kept; a worktree that still has
uncommitted changes is kept and its path is reported. Git also refuses to
remove a worktree in which submodules were initialized (for example by the
configure command), so such a worktree is kept and reported as well; check its
contents and remove it with `git worktree remove --force <path>`, since a rerun
on the same `--worktree=branch` fails while it remains.

Nested sub-agent spawning is required
(`CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH`; the default is 3):

- `/creview:rounds` — 3 or more. Each phase runs in a phase leader
  sub-agent, which spawns that phase's own sub-agents, and the triage
  sub-agent spawns the challenge sub-agents and the adjudication
  sub-agent.
- `/creview:triage` on its own — 2 or more. The triage sub-agent spawns
  the challenge sub-agents and the adjudication sub-agent.

A long run also consumes many subagent slots — the challenge sub-agents alone
number three per batch of eight findings, and a split review runs one reviewer
per (scope, reviewer) pair — so raise
`CLAUDE_CODE_MAX_SUBAGENTS_PER_SESSION` (default 200, cumulative over the
session) when using a high `--max-rounds`. Sub-agents that run in parallel are
launched at most 20 at a time, the default of
`CLAUDE_CODE_MAX_CONCURRENT_SUBAGENTS`; the rest follow in later batches.

## Reviewer / fixer agents

Apart from the bundled agents listed at the end of this section, this plugin
does not bundle specialist agents. The triage / scope-analysis /
analysis / format-build-verify / divergence-detection sub-agents enumerate agents recursively
(`**/*.md`, including subdirectories) from the **destination project**
(`.claude/agents/`) → **user** (`~/.claude/agents/`) → **plugin bundle**, read
each agent's frontmatter `name` / `description`, and pick the best match per
finding (scope-analysis instead picks every agent relevant to each review
scope, and adds `general-purpose` to a scope whose picks all cover a narrower
concern than the code's behavior, such as comments alone). With no match, they
fall back to `general-purpose`. The
bundled agents are `review-helper` (mechanical aggregation / verification),
`comment-sensei` (comment-discipline review), `review-leader` (the
`/creview:rounds` phase leader), and `pr-description-reviewer` (the pull
request description and CI reviewer of `/creview:start`'s PR mode, bundled so
that its tools stay restricted). Only `comment-sensei` is a selection
candidate; the skills launch the other three by name.

## Bundled support files

- `rules/` — `comment.md`, `document.md`, `review.md`, `wontfix.md`, `sub-agent.md`,
  `adr-format.md`, `doc-worktree.md` (only the rules the skills reference).
- `scripts/` — `fetch-diff.sh`, `render-review.py`, `del-tmp.sh`,
  `check-jsonl.py` (sub-agents validate the `.jsonl` they wrote with it),
  `lib/scratch-guard.py` (the shared `.claude/tmp/` containment check used by
  `fetch-diff.sh` / `del-tmp.sh`; from a linked worktree it also accepts the
  `.claude/tmp/` of another working tree of the same repository),
  `worktree.sh` (creates and removes the `--worktree` worktree), and `gh-pr.py`
  (resolves a pull request and checks its head commit out in a worktree, finds
  from a review document's header where its code is and checks it out in a
  worktree when it is not checked out, and removes those worktrees). The
  scripts require
  `python3` (3.9 or later) on the `PATH`; `gh-pr.py` also requires an
  authenticated GitHub CLI (`gh`), and `fetch-diff.sh --pr` requires Git 2.41
  or later. Skills invoke them via `${CLAUDE_PLUGIN_ROOT}/scripts/...`;
  sub-agent templates receive the resolved path through the `{{plugin_root}}`
  launch variable.
- `skills/{triage,respond,resolve}/scripts/compile-review.py` — the per-skill
  compile step (leader-run): aggregates intermediate JSON into `events.jsonl`
  and calls `render-review.py`.

## Japanese master (repository-root `src/creview/`)

The Japanese master lives at the repository root under `src/creview/`,
mirroring this plugin's tree one-to-one (`src/creview/skills/start/SKILL.md`
↔ `creview/skills/start/SKILL.md`, etc.) with the same plugin skill names.
The active English files here are produced by translating and transforming
that master. To update: edit the Japanese master under `src/creview/`, then
re-translate and re-apply the transformations (rename, path rewrites, the
`review-respond` → `triage` + `respond` split, agent-dispatch generalization)
to the active files.
