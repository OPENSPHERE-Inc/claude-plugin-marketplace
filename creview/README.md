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

## Reviewer / fixer agents

This plugin does not bundle specialist agents. The triage / scope-analysis /
analysis / format-build-verify sub-agents enumerate the **destination
project's** `.claude/agents/*.md`, read each agent's frontmatter
`name` / `description`, and pick the best match per finding. With no
`.claude/agents/` (or no match), they fall back to `general-purpose`. The
mechanical aggregation / compile / verification agent `review-helper` is
bundled (`agents/review-helper.md`).

## Bundled support files

- `rules/` — `comment.md`, `document.md`, `review.md`, `sub-agent.md`
  (only the rules the skills reference).
- `scripts/` — `fetch-diff.sh`, `render-review.py`, `rm-tmp.sh`. Skills invoke
  them via `${CLAUDE_PLUGIN_ROOT}/scripts/...`; sub-agent templates receive the
  resolved path through the `{{plugin_root}}` launch variable.
- `sequencer/programs/review_rounds.py` — a deterministic sequencer-program
  variant of `/creview:rounds`.

## Sequencer variant (review_rounds.py)

`sequencer/programs/review_rounds.py` drives the same multi-round flow through
the [agent-sequencer](https://github.com/OPENSPHERE-Inc/agent-sequencer) MCP
server instead of the `/creview:rounds` skill. It depends on the
`agent-sequencer` plugin / MCP server (registered in this marketplace as an
external plugin). Place the program in the agent-sequencer programs directory.
Its Instruction prompts are written in Japanese; the skills it invokes
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
