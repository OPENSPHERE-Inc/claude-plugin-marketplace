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
   reason) and the reviewer **resolves** and closes the cell. Both follow
   `rules/divergence.md`: the design must not carry a source that makes later reviews
   diverge (a fix producing the next finding without end) — an undecided specification or
   invariant, a problem class the approach cannot close, an unadjudicated conflict between
   requirements, or a mismatch with the existing design — and the reviewer raises any it
   finds as Major or higher.
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

The skill requires a session started at the repository root, with or without `--worktree`;
started from a subdirectory of the repository, it stops with an error.

The bundled `fetch-diff.sh` / `del-tmp.sh` scripts also require `python3` (3.9 or later) on
the `PATH`: their shared `.claude/tmp/` containment check is implemented in
`scripts/lib/scratch-guard.py`.

## Options

- `--review-rounds N` (default 5, max 10) — max review ⇄ triage iterations per cell.
- `--qa-attempts N` (default 5, max 10) — max QA verify ⇄ fix attempts.
- `--commit` (default off) — commit the verified implementation in one commit.
- `--worktree[=branch]` (default off) — run the task in a separate git worktree on `branch`;
  enables `--commit` (see below).
- `--output {dir}` — directory for the design documents (default
  `.claude/tmp/cdev-coding-{timestamp}-design/`).

The design documents (`design-{slug}.md`, one per architect) are kept after the run; every
other intermediate file is deleted. `--commit` never stages them. The clean-working-tree
check at start ignores `.claude/tmp/`, `.claude/worktrees/`, and the `--output` destination,
so design documents left by earlier runs and the worktrees of `--worktree` runs do not block a
new run.

With `--worktree`, the team works in a separate git worktree under `.claude/worktrees/`, so the
main working tree's sources stay untouched and it does not need to be clean. The worktree
checks out `branch` — an existing local branch as is, or a new one created from the current
HEAD; without `=branch`, a new branch `cdev-coding-{timestamp}` is created. The branch checked
out in the main working tree cannot be used, because git does not check out one branch in two
worktrees. The worktree starts from committed state — the current HEAD for a new branch, the
tip of an existing one — so uncommitted changes in the main working tree are not part of the
task. Every teammate receives the worktree as its work target
(`target_dir`) and writes only under it, to the run's working directory, and to the output paths
its task names; paths in the task are passed as given, repository-relative paths resolve against
the worktree, and an absolute path into the main working tree is a read-only reference. Gitignored dependencies, virtual environments, build directories, and `.env` are
absent from the worktree as well, and so are the contents of submodules, which
`git worktree add` does not initialize; the build and tests must therefore pass in a fresh
checkout. Dependency installation and similar setup can go in the configure command of
`build-format.md`, but configure runs only at the start of the build stage — after the format
command, and not at all when the build is skipped or no Build is declared — so the format
command and tests that run without a build cannot rely on it. A build or test failure caused
by such a missing prerequisite is not fixed in the source: the QA gate ends without a QA-fix
cell and reports the failure as environmental. The working directory and the
default design-document destination are in the main working tree's `.claude/tmp/`, a relative
`--output` resolves against the main working tree's root, and the destination project's
`.claude/agents/` and `.claude/rules/` are read from the main working tree. At the end the
worktree is removed and the branch is kept; a worktree left with uncommitted changes — for
example after an unfixed QA failure — is kept and its path is reported. Git also refuses to
remove a worktree in which submodules were initialized (for example by the configure command),
so such a worktree is kept and reported as well; check its contents and remove it with
`git worktree remove --force <path>`, since a rerun on the same `--worktree=branch` fails while
it remains.

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
  `build-format-detection.md`, `comment.md`, `review.md`, `document.md`, `divergence.md`
  (divergence patterns the design must not introduce).
- `scripts/` — `fetch-diff.sh` (snapshots the pre-coding tree, then captures the QA diff since
  coding start), `del-tmp.sh` (deletes the run's working directory under `.claude/tmp/`),
  `check-jsonl.py` (teammates validate the `.jsonl` they wrote with it), and
  `lib/scratch-guard.py` (the shared `.claude/tmp/` containment check used by both; requires
  `python3` — see Requirements), and `worktree.sh` (creates and removes the `--worktree`
  worktree). The skill invokes them via
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
