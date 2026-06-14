---
name: coding
description: Orchestrate a coding task end to end with a standing agent team using paired review cells — a design cell phase, a coding cell phase, and a QA gate. Architects, coders, and reviewers are auto-selected from the destination project agents. Use proactively when the user asks to implement a feature, build a change, or carry out a coding task. Requires a runtime with agent-team tools (TeamCreate / SendMessage / Task tools).
allowed-tools: Agent, TeamCreate, SendMessage, TeamDelete, TaskCreate, TaskUpdate, TaskList, Read, Glob, Grep, Bash(mkdir:*), Bash(grep:*), Bash(ls:*), Bash(find:*), Bash(git log:*), Bash(git diff:*), Bash(git show:*), Bash(git status:*), Bash(git branch:*), Bash(git add:*), Bash(git commit:*), Bash(${CLAUDE_PLUGIN_ROOT}/scripts/fetch-diff.sh:*), Bash(${CLAUDE_PLUGIN_ROOT}/scripts/rm-tmp.sh:*)
---

# Multi-Agent Coding

As the **coding leader (team lead)**, you assemble a standing team and drive a coding task through two cell phases — design and coding — and a final QA gate. In a cell, a producer (an architect or a coder) and a paired reviewer run an autonomous review loop and close their own cell. You set up the cells, enforce the phase gates and the QA gate, and arbitrate escalations.

The leader does not design, write, review, or fix code.

## Requirements

This skill uses agent-team tools (`TeamCreate`, `SendMessage`, `TaskCreate` / `TaskUpdate` / `TaskList`, `TeamDelete`) and runs only in a runtime where they are available.

## Input

The user supplies a coding task: a feature to implement, a change to make, or a bug to fix, optionally with target paths or a language. When the argument is `$ARGUMENTS`, interpret it as the task specification (including options).

## Options

- `--review-rounds N` (default 2, range 1–5) — Max review ⇄ triage iterations per cell.
- `--qa-attempts N` (default 5, range 1–10) — Max QA verify ⇄ fix attempts.
- `--base {branch}` (default `main` or `master`) — Base branch for diff capture in QA and code review.
- `--commit` (default OFF) — After QA passes, commit the implementation in one commit (concise message, no finding IDs).

## Output language

Design documents and finding descriptions are written in the user's chat language. The leader fixes the current chat language as `{doc_lang}` and passes it to every teammate at spawn. Structural anchors (severity labels `Critical` / `Major` / `Minor` / `Info`, JSON field names) do not change regardless of `{doc_lang}`.

## Timestamp (`{timestamp}`)

`{timestamp}` is a date-time string (format `YYYYMMDD-HHMMSS`) fixed once at the start of Step 1 and reused in all later steps.

## Team model

`TeamCreate` creates a team and its shared task list (1:1). Each teammate is spawned once via the Agent tool with `team_name` and `name`, persists across phases, is addressed by `name` via `SendMessage`, goes idle between turns (a message wakes it), and marks its work via `TaskUpdate`.

Teammate names: `architect-{slug}`, `coder-{slug}`, `reviewer-{slug}`, `dev-helper`, `comment-sensei`.

## Spawn contract

Spawn each teammate once with the prompt below. It fixes the role and the reporting protocol; each later message names the template to Read for that task. For common prohibitions and the cell protocol, see `${CLAUDE_PLUGIN_ROOT}/rules/teammate.md`.

```
You are joining team {team_name} as {role}. For each task I assign, I name a template under `${CLAUDE_PLUGIN_ROOT}/skills/coding/templates/` and give its variables; Read that template and follow it for that task. Common variables: plugin_root = ${CLAUDE_PLUGIN_ROOT}, doc_lang = {doc_lang}. Report each task result to the leader via SendMessage (counts / paths / one-line summary only); route detailed findings peer-to-peer as the template directs; mark each assigned task done via TaskUpdate. Read `${CLAUDE_PLUGIN_ROOT}/rules/teammate.md` and observe the common prohibitions and the review-cell protocol.
```

## Review cell protocol

A cell pairs a producer (an architect or a coder) with one reviewer. The full protocol is in `${CLAUDE_PLUGIN_ROOT}/rules/teammate.md` § Review cell. In outline:

1. The producer creates its output (a design section or code) and DMs the paired reviewer to review.
2. The reviewer reviews, DMs its actionable (`Critical` / `Major`) findings to the producer, and reports severity counts to the leader.
3. The producer triages each finding — fix it, or reject it with a one-line reason — applies the fixes, and tells the reviewer it is ready.
4. The reviewer resolves: it verifies the triage (fixes adequate, rejections reasonable). When satisfied, it marks the cell task done. If it still disagrees on a `Critical` finding, it escalates to the leader.
5. Steps 2–4 repeat up to `--review-rounds`; on exhaustion the reviewer closes the cell, leaving any unresolved `Critical` as a `FIXME:` at the location.

Triage and arbitration judgment priority: (1) the user's original task instructions, then (2) the upstream design intent.

## Escalation

When a reviewer escalates a `Critical` disagreement, the leader arbitrates by the judgment priority above. If the leader cannot decide either, it summarizes the dispute to the user for a decision and leaves a `FIXME:` at the location. Unresolved items do not block; they are recorded for the downstream authoritative review.

## Leader scope (body isolation)

The leader holds only the roster, the pairings, task ids / status, severity counts, file paths, and the QA result. Design bodies, source, and finding bodies stay with the teammates; findings travel producer ⇄ reviewer by `SendMessage`.

## Working directory

```
{tmp_dir} = .claude/tmp/cdev-coding-{timestamp}/
{tmp_dir}/design/{slug}.md   ← one design section per architect (read by reviewers and coders)
{tmp_dir}/changes.txt        ← working-tree diff (input to QA and code review)
{tmp_dir}/qa-result.json     ← QA result
{tmp_dir}/build.log          ← build / test output captured by dev-helper
```

Created in Step 1 with `mkdir -p`; removed by the leader in Step 5 via `${CLAUDE_PLUGIN_ROOT}/scripts/rm-tmp.sh {tmp_dir}`.

## Step 1 — Form the team and pair

1. Resolve `{timestamp}`, fix `{tmp_dir}`, and create it: `mkdir -p {tmp_dir}/design`.
2. Console: `## Phase 0 — Team formation`.
3. `TeamCreate({team_name: "cdev-coding-{timestamp}"})`.
4. Spawn `dev-helper` via `Agent(subagent_type="dev-helper", team_name, name="dev-helper", prompt=<spawn contract>)`. `TaskCreate` a team-analysis task (owner `dev-helper`) and `SendMessage(dev-helper, ...)` naming `templates/team-analysis.md` with variable `task = {task specification}`. Receive its report: `{task_summary, target_languages, has_test_suite, architects:[{name, slug, scope, reviewer, reason}], coders:[{name, slug, scope, reviewer, reason}], reviewers:[{name, slug, reason}], rationale}`. Each producer's `reviewer` is the paired reviewer's `slug` (one reviewer may be paired to several producers).
5. Spawn each roster member as a teammate via `Agent(subagent_type={name}, team_name, name={role-name}, prompt=<spawn contract>)`: `architect-{slug}`, `coder-{slug}`, `reviewer-{slug}`. Hold the roster, pairings, and `{task_summary}`.
6. Console: the roster with each producer's paired reviewer and one-line reasons.

## Step 2 — Design cells (設計)

1. Console: `## Phase 1 — Design`.
2. For each architect, `TaskCreate` a design cell (id `design-{slug}`, owner `architect-{slug}`) and start the cell with two messages:
   - `SendMessage` `architect-{slug}` naming `templates/design.md` with `task = {task_summary}`, `assigned_scope = {its scope}`, `output_path = {tmp_dir}/design/{slug}.md`, `reviewer = reviewer-{its paired slug}`.
   - `SendMessage` the paired `reviewer-{slug}` naming `templates/design-review.md` with `task = {task_summary}`, `design_path = {tmp_dir}/design/{slug}.md`, `producer = architect-{slug}`, `cell_task = design-{slug}`, `review_rounds = {--review-rounds}`.
   The pair runs the cell autonomously (review ⇄ triage ⇄ resolve); the reviewer marks `design-{slug}` done on resolve, or escalates.
3. Wait until every design cell task is done, arbitrating any escalation as it arrives. Collect the section paths as `{design_paths}`. Do not start Step 3 until all design cells are closed.

## Step 3 — Code cells (コーディング)

1. Console: `## Phase 2 — Coding`. Spawn `comment-sensei` via the spawn contract with role `the comment reviewer; a coder DMs you to review comments per templates/comment-review.md` (available to the code cells).
2. For each coder, `TaskCreate` a code cell (id `code-{slug}`, owner `coder-{slug}`) and start the cell with two messages:
   - `SendMessage` `coder-{slug}` naming `templates/code.md` with `task = {task_summary}`, `design_paths = {design_paths}`, `assigned_scope = {its scope}`, `tdd = {has_test_suite}`, `feedback = (none)`, `reviewer = reviewer-{its paired slug}`.
   - `SendMessage` the paired `reviewer-{slug}` naming `templates/code-review.md` with `task = {task_summary}`, `design_paths = {design_paths}`, `producer = coder-{slug}`, `cell_task = code-{slug}`, `review_rounds = {--review-rounds}`.
   The coder implements its scope (test-first when `tdd` is true). When its change adds or modifies comments, the coder also DMs `comment-sensei` to review and fix the comments within the cell. The pair runs the cell; the reviewer marks `code-{slug}` done on resolve, or escalates.
3. Wait until every code cell task is done, arbitrating any escalation. Do not start Step 4 until all code cells are closed.

## Step 4 — QA gate

Run the QA verify ⇄ fix loop, up to `--qa-attempts`.

1. Console: `## Phase 3 — QA (attempt {n})`.
2. Capture the working-tree diff: `${CLAUDE_PLUGIN_ROOT}/scripts/fetch-diff.sh {base} {tmp_dir}/changes.txt`.
3. `TaskCreate` a QA task (owner `dev-helper`) and `SendMessage(dev-helper, ...)` naming `templates/qa.md` with `tmp_dir = {tmp_dir}`, `diff_path = {tmp_dir}/changes.txt`, `attempt_num = {n}`. Receive `{success, format_violations_fixed, workflow_source, workflow_warning, build_ran, test_ran, suggested_specialist, error_summary, summary_line}`. If `workflow_warning` is non-null, retain it for Step 5.
4. If `success == true`, exit the loop.
5. If `success == false` and attempts remain, run a QA-fix cell:
   a. Ensure `{suggested_specialist}` is a teammate (spawn `coder-{suggested_specialist}` if not on the team) and a reviewer is paired with it (use the reviewer that covers the failing scope, or any reviewer).
   b. `SendMessage` the coder naming `templates/code.md` with `task = {task_summary}`, `design_paths = {design_paths}`, `assigned_scope = {the failing files}`, `tdd = {has_test_suite}`, `feedback = QA failure — Read {tmp_dir}/qa-result.json (failure section) and {tmp_dir}/build.log; fix the build/test error.`, `reviewer = reviewer-{paired slug}`; and `SendMessage` the reviewer naming `templates/code-review.md` with `task = {task_summary}`, `design_paths = {design_paths}`, `producer = coder-{slug}`, `cell_task = code-qa-{n}`, `review_rounds = {--review-rounds}`. The pair runs the cell (review ⇄ triage ⇄ resolve) before re-QA.
   c. When the cell closes, return to step 1 of this loop (re-QA).
6. If still failing after the max attempts, present `error_summary` to the console and proceed to Step 5.

## Step 5 — Clean up and report

1. If `--commit` is on and QA passed, commit the implementation: stage only the changed source files (not `.claude/tmp`), and commit once with a concise message (no finding IDs).
2. Shut down the teammates: `SendMessage` each one `{type: "shutdown_request"}` and wait for shutdown. Then `TeamDelete`.
3. Remove the working directory: `${CLAUDE_PLUGIN_ROOT}/scripts/rm-tmp.sh {tmp_dir}`.
4. Report to the console: the team roster with pairings, the cells resolved per phase, any escalations and the `FIXME:`s left for unresolved items, files changed, the QA result (`summary_line`, plus `workflow_warning` if any), and any unfixed QA failure.
