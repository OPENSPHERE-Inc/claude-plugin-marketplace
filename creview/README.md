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
session) when using a high `--max-rounds`.

## Reviewer / fixer agents

This plugin does not bundle specialist agents. The triage / scope-analysis /
analysis / format-build-verify sub-agents enumerate agents recursively
(`**/*.md`, including subdirectories) from the **destination project**
(`.claude/agents/`) → **user** (`~/.claude/agents/`) → **plugin bundle**, read
each agent's frontmatter `name` / `description`, and pick the best match per
finding (scope-analysis instead picks every agent relevant to each review
scope). With no match, they fall back to `general-purpose`. The
bundled agents are `review-helper` (mechanical aggregation / verification),
`comment-sensei` (comment-discipline review), and `review-leader` (the
`/creview:rounds` phase leader).

## Bundled support files

- `rules/` — `comment.md`, `document.md`, `review.md`, `wontfix.md`, `sub-agent.md`,
  `adr-format.md` (only the rules the skills reference).
- `scripts/` — `fetch-diff.sh`, `render-review.py`, `del-tmp.sh`, and
  `lib/scratch-guard.py` (the shared `.claude/tmp/` containment check used by
  `fetch-diff.sh` / `del-tmp.sh`). The scripts require `python3` (3.9 or later)
  on the `PATH`. Skills invoke them via `${CLAUDE_PLUGIN_ROOT}/scripts/...`;
  sub-agent templates receive the resolved path through the `{{plugin_root}}`
  launch variable.
- `skills/{triage,respond,resolve}/scripts/compile-review.py` — the per-skill
  compile step (leader-run): aggregates intermediate JSON into `events.jsonl`
  and calls `render-review.py`.
- `sequencer/programs/review_rounds.py` — a deterministic sequencer-program
  variant of `/creview:rounds`.

## Sequencer variant (review_rounds.py)

`sequencer/programs/review_rounds.py` drives the same multi-round flow through
the [agent-sequencer](https://github.com/OPENSPHERE-Inc/agent-sequencer) MCP
server instead of the `/creview:rounds` skill. It depends on the
`agent-sequencer` plugin / MCP server (registered in this marketplace as an
external plugin). Place the program in the agent-sequencer programs directory.
The orchestrator itself is the triage leader here, so this variant needs a
spawn depth of 2 or more — not the 3 that `/creview:rounds` needs.
Its Instruction prompts are written in English; the skills it invokes
(`/creview:start|triage|respond|resolve`) drive the review in the user's chat
language.

## Japanese master (repository-root `src/creview/`)

The Japanese master lives at the repository root under `src/creview/`,
mirroring this plugin's tree one-to-one (`src/creview/skills/start/SKILL.md`
↔ `creview/skills/start/SKILL.md`, etc.) with the same plugin skill names.
The active English files here are produced by translating and transforming
that master. To update: edit the Japanese master under `src/creview/`, then
re-translate and re-apply the transformations (rename, path rewrites, the
`review-respond` → `triage` + `respond` split, agent-dispatch generalization)
to the active files.
