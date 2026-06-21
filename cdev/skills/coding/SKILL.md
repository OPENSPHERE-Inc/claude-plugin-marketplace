---
name: coding
description: Orchestrate a coding task end to end with a standing agent team using paired review cells — a design cell step, a coding cell step, and a QA gate. Reviewers are auto-selected from the destination project agents. Use proactively when the user asks to implement a feature, build a change, or carry out a coding task. Requires a runtime with background subagents (Agent run_in_background) and inter-agent messaging (SendMessage).
allowed-tools: Agent, SendMessage, TodoWrite, Read, Glob, Grep, Bash(mkdir:*), Bash(grep:*), Bash(ls:*), Bash(find:*), Bash(git log:*), Bash(git diff:*), Bash(git show:*), Bash(git status:*), Bash(git branch:*), Bash(git add:*), Bash(git commit:*), Bash(${CLAUDE_PLUGIN_ROOT}/scripts/fetch-diff.sh:*), Bash(${CLAUDE_PLUGIN_ROOT}/scripts/rm-tmp.sh:*)
---

# Multi-Agent Coding

As the **coding leader (team lead)**, you assemble a standing team and drive a coding task through two cell steps — design and coding — and a final QA gate. In a cell, a producer (an architect or a coder) and a paired reviewer run an autonomous review loop and close their own cell. You set up the cells, enforce the step gates and the QA gate, and arbitrate escalations.

The leader does not design, write, review, or fix code.

## Requirements

This skill uses background subagents (`Agent` with `run_in_background`) and inter-teammate messaging (`SendMessage`), and runs only in a runtime where they are available. The session has a single implicit team; no explicit team creation or deletion. There is no shared task list.

## Input

The user supplies a coding task: a feature to implement, a change to make, or a bug to fix, optionally with target paths or a language. When the argument is `$ARGUMENTS`, interpret it as the task specification (including options).

## Options

- `--review-rounds N` (default 2, range 1–5) — Max review ⇄ triage iterations per cell.
- `--qa-attempts N` (default 5, range 1–10) — Max QA verify ⇄ fix attempts.
- `--commit` (default OFF) — After QA passes, commit the implementation in one commit (concise message, no finding IDs).

## Output language

Design documents and finding descriptions are written in the user's chat language. The leader fixes the current chat language as `{doc_lang}` and passes it to every teammate at spawn. Structural anchors (severity labels `Critical` / `Major` / `Minor` / `Info`, JSON field names) do not change regardless of `{doc_lang}`.

## Timestamp (`{timestamp}`)

`{timestamp}` is a date-time string (format `YYYYMMDD-HHMMSS`) fixed once at the start of Step 1 and reused in all later steps.

## Team model

The session has a single implicit team. Each teammate is spawned once as a background, persistent subagent (spawn requirements in § Agent types and spawn requirements), persists across steps (its context is retained), goes idle between turns (a message wakes it), and reports completion to the leader via `SendMessage(to: "main")`.

A teammate is addressed by the **agentId** returned in its spawn result. A friendly name stops resolving once the teammate goes idle (`No agent named X is currently addressable`), so always address by agentId. The leader keeps a roster: each teammate's `slug` (the role label `architect-{slug}` / `coder-{slug}` / `reviewer-{slug}` / `dev-helper` / `comment-sensei`) → `{agentType, agentId}`. When teammates DM each other, the leader hands each the other's agentId in the dispatch message. The leader is reached at `to: "main"` (always addressable).

The leader holds no shared task list; it tracks each cell's status, alongside the roster, in its own working state (and may surface it to the user via `TodoWrite`).

The leader runs event-driven: after dispatching a cell or task it ends its turn and is re-invoked by teammate messages (`to: "main"`). It updates its tracking state on each message and starts the next step once the step's gate condition is met.

## Agent types and spawn requirements

Spawn each teammate with the Agent tool. Rather than copying an exact argument list, meet these requirements: launch it as a background, persistent subagent (so a follow-up message continues it), pass the spawn contract as its prompt, include a `description`, and record the returned agentId in the roster.

Agent type (subagent_type):

- Bundled agents are named with the plugin namespace: `cdev:dev-helper`, `cdev:comment-sensei`.
- Reviewers use the registered name team-analysis returns (project `.claude/agents` / user `~/.claude/agents` agents keep their registered name).
- Architects and coders always run as `general-purpose`. Some specialist agents emit tool calls as text and stall, so work cannot continue. A producer (architect / coder) works to its assigned scope and the project's conventions; domain correctness is enforced by the specialist reviewers in review.

## Spawn contract

Spawn each teammate once with the prompt below. It fixes the role and the reporting protocol; each later message names the template to Read for that task. For common prohibitions and the cell protocol, see `${CLAUDE_PLUGIN_ROOT}/rules/teammate.md`.

```
You are joining the team as {role}. For each task I assign, I name a template under `${CLAUDE_PLUGIN_ROOT}/skills/coding/templates/` and give its variables; Read that template and follow it for that task. Common variables: plugin_root = ${CLAUDE_PLUGIN_ROOT}, doc_lang = {doc_lang}. Report each task result to the leader (SendMessage with to: "main") — counts / paths / one-line summary only; route detailed findings peer-to-peer to the recipient's agentId via SendMessage (I hand you each recipient's agentId), as the template directs. Read `${CLAUDE_PLUGIN_ROOT}/rules/teammate.md` and observe the common prohibitions and the review-cell protocol.
```

## Review cell protocol

A cell pairs a producer (an architect or a coder) with one reviewer. The full protocol is in `${CLAUDE_PLUGIN_ROOT}/rules/teammate.md` § Review cell. In outline:

1. The producer creates its output (a design section or code) and DMs the paired reviewer to review.
2. The reviewer reviews, DMs its actionable (`Critical` / `Major`) findings to the producer, and reports severity counts to the leader.
3. The producer triages each finding — fix it, or reject it with a one-line reason — applies the fixes, and tells the reviewer it is ready.
4. The reviewer resolves: it verifies the triage (fixes adequate, rejections reasonable). When satisfied, it reports the cell resolved to the leader via `SendMessage(to: "main")` (naming the cell id). If it still disagrees on a `Critical` finding, it escalates to the leader.
5. Steps 2–4 repeat up to `--review-rounds`; on exhaustion the reviewer closes the cell (reporting to the leader), leaving any unresolved `Critical` as a `FIXME:` at the location.

Triage and arbitration judgment priority: (1) the user's original task instructions, then (2) the upstream design intent.

## Escalation

When a reviewer escalates a `Critical` disagreement, the leader arbitrates by the judgment priority above. If the leader cannot decide either, it summarizes the dispute to the user for a decision and leaves a `FIXME:` at the location. Unresolved items do not block; they are recorded for the downstream authoritative review.

## Leader scope (body isolation)

The leader holds only the roster (each teammate's slug → agentType / agentId), the pairings, each cell's status, severity counts, file paths, and the QA result. Design bodies, source, and finding bodies stay with the teammates; findings travel producer ⇄ reviewer by `SendMessage`.

## Working directory

```
{tmp_dir} = .claude/tmp/cdev-coding-{timestamp}/
{tmp_dir}/design/{slug}.md   ← one design section per architect (read by reviewers and coders)
{tmp_dir}/baseline-tree      ← pre-coding working-tree snapshot (baseline for the QA diff)
{tmp_dir}/changes.txt        ← diff since coding start (input to QA)
{tmp_dir}/qa-result.json     ← QA result
{tmp_dir}/build.log          ← build / test output captured by dev-helper
```

Created in Step 1 with `mkdir -p`; removed by the leader in Step 5 via `${CLAUDE_PLUGIN_ROOT}/scripts/rm-tmp.sh {tmp_dir}`.

## Step 1 — Form the team and pair

1. Resolve `{timestamp}`, fix `{tmp_dir}`, and create it (`mkdir -p {tmp_dir}/design`). Then record the pre-coding baseline: `${CLAUDE_PLUGIN_ROOT}/scripts/fetch-diff.sh snapshot {tmp_dir}/baseline-tree`.
2. Console: `## Step 1 — Team formation`.
3. Spawn `dev-helper` (type `cdev:dev-helper`) per the spawn requirements, and record its agentId in the roster. To its agentId, `SendMessage` naming `templates/team-analysis.md` with variable `task = {task specification}`. Receive its report (`to: "main"`): `{task_summary, target_languages, has_test_suite, architects:[{name, slug, scope, reviewer, reason}], coders:[{name, slug, scope, reviewer, reason}], reviewers:[{name, slug, reason}], rationale}` (`name` is the subagent_type to spawn; an architect's and coder's `name` is `general-purpose`). Each producer's `reviewer` is the paired reviewer's `slug` (one reviewer may be paired to several producers, but only within the same domain).
4. Spawn each roster member (`architect-{slug}` / `coder-{slug}` / `reviewer-{slug}`) per the spawn requirements, using the `name` team-analysis returns as the type (architects and coders use `general-purpose`). Record each teammate's agentId in the roster (slug → agentType / agentId), and hold the pairings and `{task_summary}`.
5. Console: the roster with each producer's paired reviewer and one-line reasons.

## Step 2 — Design cells (設計)

1. Console: `## Step 2 — Design`.
2. For each architect, start the design cell `design-{slug}` with two messages (addressed to roster agentIds):
   - To the architect's agentId, `SendMessage` naming `templates/design.md` with `task = {task_summary}`, `assigned_scope = {its scope}`, `output_path = {tmp_dir}/design/{slug}.md`, `reviewer = {paired reviewer's agentId}`.
   - To the paired reviewer's agentId, `SendMessage` naming `templates/design-review.md` with `task = {task_summary}`, `design_path = {tmp_dir}/design/{slug}.md`, `producer = {architect's agentId}`, `cell_task = design-{slug}`, `review_rounds = {--review-rounds}`.
   The pair runs the cell autonomously (review ⇄ triage ⇄ resolve); on resolve the reviewer reports the cell resolved to the leader (naming the cell id), or escalates.
3. Wait until you have received a resolve report for every design cell, arbitrating any escalation as it arrives; gate by counting the closure reports. Collect the section paths as `{design_paths}`. Do not start Step 3 until all design cells are closed.

## Step 3 — Code cells (コーディング)

1. Console: `## Step 3 — Coding`. Spawn `comment-sensei` (type `cdev:comment-sensei`) per the spawn requirements with role `the comment reviewer; a coder DMs you to review comments per templates/comment-review.md`, and record its agentId in the roster (available to the code cells).
2. For each coder, start the code cell `code-{slug}` with two messages (addressed to roster agentIds):
   - To the coder's agentId, `SendMessage` naming `templates/code.md` with `task = {task_summary}`, `design_paths = {design_paths}`, `assigned_scope = {its scope}`, `tdd = {has_test_suite}`, `feedback = (none)`, `reviewer = {paired reviewer's agentId}`, `comment_reviewer = {comment-sensei's agentId}`.
   - To the paired reviewer's agentId, `SendMessage` naming `templates/code-review.md` with `task = {task_summary}`, `design_paths = {design_paths}`, `producer = {coder's agentId}`, `cell_task = code-{slug}`, `review_rounds = {--review-rounds}`.
   The coder implements its scope (test-first when `tdd` is true). When its change adds or modifies comments, the coder also DMs `comment-sensei` to review and fix the comments within the cell. The pair runs the cell; on resolve the reviewer reports the cell resolved to the leader (naming the cell id), or escalates.
3. Wait until you have received a resolve report for every code cell, arbitrating any escalation. Do not start Step 4 until all code cells are closed.

## Step 4 — QA gate

Run the QA verify ⇄ fix loop, up to `--qa-attempts`.

1. Console: `## Step 4 — QA (attempt {n})`.
2. Capture the diff since coding start: `${CLAUDE_PLUGIN_ROOT}/scripts/fetch-diff.sh diff {tmp_dir}/baseline-tree {tmp_dir}/changes.txt`.
3. To dev-helper's agentId, `SendMessage` naming `templates/qa.md` with `tmp_dir = {tmp_dir}`, `diff_path = {tmp_dir}/changes.txt`, `attempt_num = {n}`. Receive its report (`to: "main"`) `{success, format_violations_fixed, workflow_source, workflow_warning, build_ran, test_ran, suggested_specialist, error_summary, summary_line}`. If `workflow_warning` is non-null, retain it for Step 5.
4. If `success == true`, exit the loop.
5. If `success == false` and attempts remain, run a QA-fix cell:
   a. Ensure a general-purpose coder covers the failing scope (reuse an existing one, or spawn a `general-purpose` coder and record its agentId in the roster). Pair it with a reviewer matching the failing domain (or `general-purpose` if none; `{suggested_specialist}` is a domain hint for picking the reviewer).
   b. To the coder's agentId, `SendMessage` naming `templates/code.md` with `task = {task_summary}`, `design_paths = {design_paths}`, `assigned_scope = {the failing files}`, `tdd = {has_test_suite}`, `feedback = QA failure — Read {tmp_dir}/qa-result.json (failure section) and {tmp_dir}/build.log; fix the build/test error.`, `reviewer = {paired reviewer's agentId}`, `comment_reviewer = {comment-sensei's agentId}`; and to the reviewer's agentId, `SendMessage` naming `templates/code-review.md` with `task = {task_summary}`, `design_paths = {design_paths}`, `producer = {coder's agentId}`, `cell_task = code-qa-{n}`, `review_rounds = {--review-rounds}`. The pair runs the cell (review ⇄ triage ⇄ resolve) before re-QA.
   c. When you receive the reviewer's resolve report, return to step 1 of this loop (re-QA).
6. If still failing after the max attempts, present `error_summary` to the console and proceed to Step 5.

## Step 5 — Clean up and report

1. If `--commit` is on and QA passed, commit the implementation: stage only the changed source files (not `.claude/tmp`), and commit once with a concise message (no finding IDs).
2. Shut down the teammates: to each teammate's agentId, `SendMessage` `{type: "shutdown_request"}` and wait for shutdown.
3. Remove the working directory: `${CLAUDE_PLUGIN_ROOT}/scripts/rm-tmp.sh {tmp_dir}`.
4. Report to the console: the team roster with pairings, the cells resolved per step, any escalations and the `FIXME:`s left for unresolved items, files changed, the QA result (`summary_line`, plus `workflow_warning` if any), and any unfixed QA failure.
