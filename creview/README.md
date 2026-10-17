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

`/creview:start` also takes a GitHub pull request URL
(`https://{host}/{owner}/{repo}/pull/{number}`) as its review target and then
reviews that pull request: the diff from its merge base to its head commit.
The pull request must be open, its repository on its host must be a remote of
the current clone, and the GitHub CLI (`gh`) must be authenticated for that
host. `--base` and `--range` cannot be combined with it.

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
  - When the pull request changes a `CLAUDE.md`, a `CLAUDE.local.md`, an
    `AGENTS.md`, or a file under `.claude/`, the run lists those files and
    asks whether you trust the pull request before checking it out: Claude
    Code can load them as instructions or skills once a sub-agent reads files
    in the worktree.
    - A path with a component shaped like a Windows 8.3 short name (a `~`
      followed by a digit, such as `CLAUDE~1`) is listed as well, since on
      NTFS it can stand for `.claude`.
    - Files that the pull request head's `CLAUDE.md`, `CLAUDE.local.md`,
      `AGENTS.md`, or `.claude/rules/*.md` import through `@` references,
      directly or through other imports, are listed as well when the pull
      request changes them.
    - When the pull request changes 300 or more files (GitHub lists at most
      300 changed files of a comparison) or the run cannot read all of those
      imports, it asks without a list, saying that the files could not be
      checked.
    - `--trust` skips the question, including when the files could not be
      checked.
  - Checking out the worktree requires Git 2.31 or later; with an older Git
    the run stops with an error.

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
files, `CLAUDE.md`, `AGENTS.md`, and `.claude/**` included, are data as well,
and the sub-agents are told to run none of them and to run no git command in
the worktree. These are instructions, not enforcement: for a pull request you
do not trust, also rely on your environment (a sandbox, hooks, or permission
rules).

During a worktree review, the session's working directory is the worktree.
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
`- **PR:** {url} (head {head_sha}, base {merge_base})`. When run separately on
such a document, `/creview:triage`, `/creview:respond`, and `/creview:resolve`
work on the current working tree, not on a worktree of the pull request. Check
out the pull request's head commit before running them; on another commit,
such as the base branch, they triage, fix, and verify code other than the pull
request's.

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
  `AGENTS.md`, and `.claude/**` as instructions or skills, along with the files
  they import through `@` references.
- `/creview:respond` runs the format, build, and test commands, and with them
  the pull request's build scripts and tests.
  - Without a `build-format.md`, it takes those commands from the checkout's
    `CLAUDE.md` or `README.md`.

creview assumes that, before you run it, you have checked the repository and
the pull request and trust them. The ways listed above and a worktree review's
trust confirmation, which lists the instruction files the pull request
changes, only support that decision: they do not cover every way the pull
request's code or instructions can take effect, and they cannot guarantee that
a repository or pull request fetched from the network is safe. Keep the agent
safe through your environment, such as a sandbox and permission rules, and
check out a pull request you do not trust, and run `/creview:respond` on it,
only in a sandbox.

When the review has Critical, Major, or Minor findings, `/creview:start` asks
at the end whether to run `/creview:triage` on the new review document, and
runs it in the same session if you agree. It does not ask after a worktree
review, where the current working tree is not at the pull request's head, or
under `/creview:rounds`.

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
round's workflow warning, which the final report lists. At the
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
- `/creview:triage` on its own, or run by `/creview:start` at its end — 2 or
  more. The triage sub-agent spawns the challenge sub-agents and the
  adjudication sub-agent.

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
  `adr-format.md` (only the rules the skills reference).
- `scripts/` — `fetch-diff.sh`, `render-review.py`, `del-tmp.sh`,
  `check-jsonl.py` (sub-agents validate the `.jsonl` they wrote with it),
  `lib/scratch-guard.py` (the shared `.claude/tmp/` containment check used by
  `fetch-diff.sh` / `del-tmp.sh`; from a linked worktree it also accepts the
  `.claude/tmp/` of another working tree of the same repository),
  `worktree.sh` (creates and removes the `--worktree` worktree), and
  `gh-pr.py` (resolves a pull request for `/creview:start`, checks its head
  commit out in a worktree, and removes that worktree). The scripts require
  `python3` (3.9 or later) on the `PATH`; `gh-pr.py` also requires an
  authenticated GitHub CLI (`gh`), and its worktree commands require Git 2.31
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
