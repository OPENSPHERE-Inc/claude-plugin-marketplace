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

The leader (team lead) calls `TeamCreate`, spawns each selected specialist once as a named,
persistent teammate, and drives five phases over a shared task list, reporting progress to
the console at each one:

1. **Design** — architect teammates write a design for their assigned area.
2. **Design review** — reviewer teammates review the design; actionable findings
   (Critical / Major) are sent straight to the owning architect, who revises (bounded loop).
3. **Coding** — coder teammates implement the design within disjoint file scopes.
4. **QA** — the build / format / test workflow runs once; on failure the identified
   specialist fixes it and QA re-runs (bounded loop).
5. **Code review** — reviewer teammates review the code (and `comment-sensei` reviews
   comments when any were added); actionable findings go to the owning coder, after which
   QA re-runs to keep the build green.

Teammates persist across phases, so they keep their own context (an architect remembers its
design rationale; a coder remembers what it wrote) and revise incrementally. Feedback flows
**peer to peer** — reviewers message the owning architect / coder directly; the leader holds
only the roster, task status, severity counts, paths, and the QA result, never the bodies.

## Requirements

This skill uses agent-team tools (`TeamCreate`, `SendMessage`, `TaskCreate` / `TaskUpdate` /
`TaskList`, `TeamDelete`). It runs only in a runtime where those are available — a deliberate
trade-off favoring efficiency over the broad portability of a one-shot, stateless agent design.

## Options

- `--design-rounds N` (default 2) — max design-review ⇄ revision iterations.
- `--review-rounds N` (default 2) — max code-review ⇄ fix iterations.
- `--qa-attempts N` (default 5) — max QA verify ⇄ coder-fix attempts.
- `--base {branch}` (default `main` / `master`) — base branch for diff capture.
- `--commit` (default off) — commit the verified implementation in one commit.

## Architect / coder / reviewer agents

This plugin does not bundle specialist architects, coders, or reviewers. The `team-analysis`
task enumerates agents recursively (`**/*.md`, including subdirectories) from the
**destination project** (`.claude/agents/`) → **user** (`~/.claude/agents/`) → **plugin
bundle**, reads each agent's frontmatter `name` / `description`, and assigns the best matches
to each role (multiple per role); each is spawned as a teammate. With no match for a role, it
falls back to `general-purpose`. The QA task resolves the build/test-fix specialist the same
way.

## Bundled agents and support files

- `agents/dev-helper.md` — mechanical teammate: team formation (scoping + agent selection)
  and QA (running the project's format / build / test, identifying the fix specialist on
  failure).
- `agents/comment-sensei.md` — code-comment specialist teammate; reviews and fixes comments
  added or modified during coding, against `rules/comment.md`.
- `rules/` — `teammate.md` (teammate common rules), `agents-detection.md`,
  `build-format-detection.md`, `comment.md`, `review.md`, `document.md`.
- `scripts/` — `fetch-diff.sh` (working-tree diff for QA / code review), `rm-tmp.sh` (deletes
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
