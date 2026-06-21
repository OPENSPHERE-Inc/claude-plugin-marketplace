# cdev

*[日本語版 README](README_ja.md)*

A team-native multi-agent coding workflow for Claude Code. One skill, `/cdev:coding`,
stands up an agent team and drives a task from design to verified, reviewed code.

## Skill

| Command | Purpose |
|---------|---------|
| `/cdev:coding` | Implement a coding task end to end: form a standing team, then run design → design review → coding → QA → code review with feedback loops. |

Invoke it with a task description, e.g. `/cdev:coding add a rate limiter to the
upload endpoint`.

## Lifecycle role

`cdev` is the **implementation stage** of the marketplace lifecycle: it gets a working,
self-checked first cut built quickly. Its in-loop reviews are **quality gates**, not an
authoritative review — run `creview` afterward for the bias-controlled, auditable review
(`/creview:start` → `triage` → `respond` → `resolve`). Because the authoritative review
lives in `creview`, `cdev` optimizes for speed and coherence instead.

## How it works

The leader (team lead) spawns each selected specialist once as a named, persistent
background teammate (`Agent` with `run_in_background`), pairs each producer with a reviewer,
and drives two cell steps and a final QA gate, reporting progress to the console:

1. **Design cells** — each architect writes a design for its area, then its **paired
   reviewer** reviews it; the architect **triages** each finding (fix, or reject with a
   reason) and the reviewer **resolves** and closes the cell.
2. **Code cells** — each coder implements its scope (test-first when the project has a test
   suite); `comment-sensei` fixes comment violations when comments are present; the **paired
   reviewer** reviews, the coder triages, the reviewer resolves and closes the cell.
3. **QA gate** — the build / format / test workflow runs once; on failure the responsible
   coder fixes it, the fix goes through a review cell, and QA re-runs (bounded loop).

A cell runs autonomously: the producer (architect / coder) and its paired reviewer loop
review ⇄ triage ⇄ resolve until the reviewer closes the cell. The leader sets up the cells,
enforces the step gates (all design cells close before coding; all code cells before QA),
runs the QA gate, and arbitrates escalations. When a reviewer and a producer deadlock on a
`Critical` finding, the reviewer escalates to the leader; if the leader cannot decide either,
it asks the user and leaves a `FIXME:`. Judgment priority is the user's original task first,
then the design intent. The authoritative review is `creview`, so unresolved items are left
as `FIXME:`s rather than blocking.

Teammates persist across steps, so they keep their own context and revise incrementally.
Feedback flows **peer to peer**; the leader holds only the roster, pairings, each cell's
status, severity counts, paths, and the QA result, never the bodies.

## Requirements

This skill uses background subagents (`Agent` with `run_in_background`) and `SendMessage`
between named teammates. The session has a single implicit team — no explicit team creation
or deletion, and no shared task list; the leader tracks each cell's status itself. It runs
only in a runtime where these are available — a deliberate trade-off favoring efficiency over
the broad portability of a one-shot, stateless agent design.

## Options

- `--review-rounds N` (default 2) — max review ⇄ triage iterations per cell.
- `--qa-attempts N` (default 5) — max QA verify ⇄ fix attempts.
- `--commit` (default off) — commit the verified implementation in one commit.

## Architect / coder / reviewer agents

This plugin does not bundle specialist reviewers. The `team-analysis`
task enumerates agents recursively (`**/*.md`, including subdirectories) from the
**destination project** (`.claude/agents/`) → **user** (`~/.claude/agents/`) → **plugin
bundle**, reads each agent's frontmatter `name` / `description`, and assigns the best-matching
specialists to the **reviewer** role — each reviewer covers a producer's domain, and an
out-of-domain specialty is never bundled onto one reviewer. **Architects and coders always run
as `general-purpose`**: some specialist agents emit malformed tool calls and stall, and a
producer works to its assigned scope and the project conventions while the specialist reviewers
enforce domain correctness. When no specialist matches a domain, the reviewer falls back to
`general-purpose`.

## Bundled agents and support files

- `agents/dev-helper.md` — mechanical teammate: team formation (scoping + agent selection)
  and QA (running the project's format / build / test, identifying the fix specialist on
  failure).
- `agents/comment-sensei.md` — code-comment specialist teammate; reviews and fixes comments
  added or modified during coding, against `rules/comment.md`.
- `rules/` — `teammate.md` (teammate common rules), `agents-detection.md`,
  `build-format-detection.md`, `comment.md`, `review.md`, `document.md`.
- `scripts/` — `fetch-diff.sh` (snapshots the pre-coding tree, then captures the QA diff since coding start), `rm-tmp.sh` (deletes
  the run's working directory under `.claude/tmp/`). The skill invokes them via
  `${CLAUDE_PLUGIN_ROOT}/scripts/...`; teammates receive the resolved path through the
  `{{plugin_root}}` variable.

## Build / test detection

QA resolves the project's format / build / test commands via
`rules/build-format-detection.md`: a `build-format.md` descriptor
(`.claude/rules/**/build-format.md`) takes priority, else `CLAUDE.md`, else `README.md`. When
none declares a workflow, QA performs a visual check only and returns a warning recommending a
`build-format.md` descriptor.

## Japanese master (repository-root `src/cdev/`)

The Japanese master lives at the repository root under `src/cdev/`, mirroring this plugin's
tree one-to-one (`src/cdev/skills/coding/SKILL.md` ↔ `cdev/skills/coding/SKILL.md`, etc.) with
the same skill name. The active English files here are produced by translating that master. To
update: edit the Japanese master under `src/cdev/`, then re-translate and re-apply the path
rewrites (`${CLAUDE_PLUGIN_ROOT}` / `{{plugin_root}}`) to the active files.
