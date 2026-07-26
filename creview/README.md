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
unconditionally: the triage sub-agent proposes a verdict, a challenge sub-agent
argues the opposite where it can, and an adjudication sub-agent decides the
final verdict.

Nested sub-agent spawning is required
(`CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH`; the default is 3):

- `/creview:rounds` — 3 or more. Each phase runs in a phase leader
  sub-agent, which spawns that phase's own sub-agents, and the triage
  sub-agent spawns the challenge / adjudication sub-agents.
- `/creview:triage` on its own — 2 or more. The triage sub-agent spawns
  the challenge / adjudication sub-agents.

A long run also consumes many subagent slots — raise
`CLAUDE_CODE_MAX_SUBAGENTS_PER_SESSION` (default 200, cumulative over the
session) when using a high `--max-rounds`.

## Reviewer / fixer agents

This plugin does not bundle specialist agents. The triage / scope-analysis /
analysis / format-build-verify sub-agents enumerate agents recursively
(`**/*.md`, including subdirectories) from the **destination project**
(`.claude/agents/`) → **user** (`~/.claude/agents/`) → **plugin bundle**, read
each agent's frontmatter `name` / `description`, and pick the best match per
finding. With no match, they fall back to `general-purpose`. The
bundled agents are `review-helper` (mechanical aggregation / verification),
`comment-sensei` (comment-discipline review), and `review-leader` (the
`/creview:rounds` phase leader).

## Bundled support files

- `rules/` — `comment.md`, `document.md`, `review.md`, `sub-agent.md`
  (only the rules the skills reference).
- `scripts/` — `fetch-diff.sh`, `render-review.py`, `rm-tmp.sh`, and
  `lib/scratch-guard.py` (the shared `.claude/tmp/` containment check used by
  `fetch-diff.sh` / `rm-tmp.sh`). The scripts require `python3` (3.9 or later)
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
