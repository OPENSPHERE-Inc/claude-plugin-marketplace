# creview

*[日本語版 README](README_ja.md)*

A multi-agent parallel code review workflow for Claude Code.

## Skills

| Command | Maps from | Purpose |
|---------|-----------|---------|
| `/creview:start` | `parallel-review` | Run a parallel code review; produce a review document with metadata markers. |
| `/creview:triage` | `review-respond` (triage + estimate) | Triage and estimate findings; persist `triage` / `estimate` into the document. |
| `/creview:respond` | `review-respond` (fix) | Fix Will-Fix / Maintain / Alternative findings; verify the build; persist `status`. |
| `/creview:resolve` | `review-resolve` | Verify fix resolutions against the source; persist `verification`. |
| `/creview:rounds` | `review-rounds` | Automatically iterate start → triage → respond → resolve across rounds. |
| `/creview:pr` | — | Review and triage a GitHub pull request in a worktree; post the result as an inline review on instruction. |

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
smaller change stays a single scope. Changed files whose new content is
identical, such as a mirrored copy, are kept in one scope and reviewed once;
a finding is anchored at one of the copies and names the others.

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

`/creview:pr [<number> | <url>] [--adversarial] [--output <path>]` reviews an
open GitHub pull request without touching the main working tree. It requires
the GitHub CLI (`gh`), authenticated for the repository, and a session in a
clone of the repository the PR targets; with no PR given, it reviews the PR of
the current branch.

- The PR head is checked out, detached, in a temporary worktree under
  `.claude/worktrees/`. The worktree and its temporary branch are removed
  once the review and triage are done.
- The diff from the merge base to the PR head is reviewed the way
  `/creview:start` reviews a change, with the same reviewer selection and the
  same `--adversarial` mode. A separate reviewer checks the PR description
  against the code: claims the code does not bear out, missing information
  such as breaking changes or how the change was tested, and open issues such
  as unchecked task items or TODOs.
- Every comment on the PR is fetched — conversation comments, review bodies,
  and review threads with their resolved state, from humans and bots alike.
  Findings the conversation already raised, resolved, or rejected are marked
  Won't Fix. The remaining findings go through the same adversarial triage as
  `/creview:triage`; no estimate is made.
- The result is presented in the console with each finding's verdict and
  where it would be posted. The user can then exclude or include findings,
  reword comments, or change severities. Nothing is posted until the user
  instructs it.
- On instruction, the Will Fix findings other than Info are posted as one
  review. A finding becomes an inline comment when its line can be commented
  on in the PR diff, a file-level comment when only its file is in the diff,
  and an entry in the review body otherwise, which includes the findings on
  the PR description. The review requests changes when a Critical or Major
  finding is posted and is a plain comment otherwise; on the user's own PR,
  where GitHub does not allow requesting changes, it is a comment. The skill
  never approves a PR. Posting is refused when the PR head moved after the
  review; rerun the skill then.
- The posted comments are written in the language of the PR description; the
  review document and the console summary use the user's chat language. Each
  posted comment starts with its finding id in the review document (such as
  `M-1`), so the two can be matched. The
  review document stays at `.claude/tmp/creview-pr-{number}-{timestamp}.md`
  unless `--output` names another path.
- Every sub-agent treats the PR's code, description, and comments as data
  under review and does not follow instructions found in them.

Nested sub-agent spawning is required
(`CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH`; the default is 3):

- `/creview:rounds` — 3 or more. Each phase runs in a phase leader
  sub-agent, which spawns that phase's own sub-agents, and the triage
  sub-agent spawns the challenge sub-agents and the adjudication
  sub-agent.
- `/creview:triage` on its own — 2 or more. The triage sub-agent spawns
  the challenge sub-agents and the adjudication sub-agent.
- `/creview:pr` — 2 or more, for the same triage sub-agent.

A long run also consumes many subagent slots — the challenge sub-agents alone
number three per batch of eight findings, and a split review runs one reviewer
per (scope, reviewer) pair — so raise
`CLAUDE_CODE_MAX_SUBAGENTS_PER_SESSION` (default 200, cumulative over the
session) when using a high `--max-rounds`. Sub-agents that run in parallel are
launched at most 20 at a time, the default of
`CLAUDE_CODE_MAX_CONCURRENT_SUBAGENTS`; the rest follow as running ones return.

## Reviewer / fixer agents

This plugin does not bundle specialist agents. The triage / scope-analysis /
analysis / format-build-verify / divergence-detection sub-agents enumerate agents recursively
(`**/*.md`, including subdirectories) from the **destination project**
(`.claude/agents/`) → **user** (`~/.claude/agents/`) → **plugin bundle**, read
each agent's frontmatter `name` / `description`, and pick the best match per
finding (scope-analysis instead picks every agent relevant to each review
scope, and adds `general-purpose` to a scope whose picks all cover a narrower
concern than the code's behavior, such as comments alone). With no match, they
fall back to `general-purpose`. The
bundled agents are `review-helper` (mechanical aggregation / verification),
`comment-sensei` (comment-discipline review), and `review-leader` (the
`/creview:rounds` phase leader).

## Bundled support files

- `rules/` — `comment.md`, `document.md`, `review.md`, `wontfix.md`, `sub-agent.md`,
  `adr-format.md` (only the rules the skills reference).
- `scripts/` — `fetch-diff.sh`, `render-review.py`, `del-tmp.sh`,
  `check-jsonl.py` (sub-agents validate the `.jsonl` they wrote with it), and
  `lib/scratch-guard.py` (the shared `.claude/tmp/` containment check used by
  `fetch-diff.sh` / `del-tmp.sh`; from a linked worktree it also accepts the
  `.claude/tmp/` of another working tree of the same repository), and
  `worktree.sh` (creates and removes the `--worktree` worktree). The scripts
  require `python3` (3.9 or later)
  on the `PATH`. Skills invoke them via `${CLAUDE_PLUGIN_ROOT}/scripts/...`;
  sub-agent templates receive the resolved path through the `{{plugin_root}}`
  launch variable.
- `skills/{triage,respond,resolve}/scripts/compile-review.py` — the per-skill
  compile step (leader-run): aggregates intermediate JSON into `events.jsonl`
  and calls `render-review.py`.
- `skills/pr/scripts/gh-pr.py` — fetches the pull request and its
  conversation, and posts the review, through the `gh` CLI.

## Japanese master (repository-root `src/creview/`)

The Japanese master lives at the repository root under `src/creview/`,
mirroring this plugin's tree one-to-one (`src/creview/skills/start/SKILL.md`
↔ `creview/skills/start/SKILL.md`, etc.) with the same plugin skill names.
The active English files here are produced by translating and transforming
that master. To update: edit the Japanese master under `src/creview/`, then
re-translate and re-apply the transformations (rename, path rewrites, the
`review-respond` → `triage` + `respond` split, agent-dispatch generalization)
to the active files.
