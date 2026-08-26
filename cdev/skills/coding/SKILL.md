---
name: coding
description: Orchestrate a coding task end to end with a standing agent team using paired review cells — a design cell step, a coding cell step, and a QA gate. Reviewers are auto-selected from the destination project agents. Use proactively when the user asks to implement a feature, build a change, or carry out a coding task. Requires a runtime with background subagents (Agent run_in_background) and inter-agent messaging (SendMessage).
allowed-tools: Agent, SendMessage, TodoWrite, Read, Glob, Grep, Bash(mkdir:*), Bash(grep:*), Bash(ls:*), Bash(git log:*), Bash(git diff:*), Bash(git show:*), Bash(git status:*), Bash(git branch:*), Bash(git add:*), Bash(git commit:*), Bash(${CLAUDE_PLUGIN_ROOT}/scripts/fetch-diff.sh:*), Bash(${CLAUDE_PLUGIN_ROOT}/scripts/del-tmp.sh:*)
---

# Multi-Agent Coding

As the **coding leader (team lead)**, you assemble a standing team and drive a coding task through two cell steps — design and coding — and a final QA gate. In a cell, a producer (an architect or a coder) and a paired reviewer run an autonomous review loop and close their own cell. You set up the cells, enforce the step gates and the QA gate, and arbitrate escalations.

The leader does not design, write, review, or fix code.

## Requirements

This skill uses background subagents (`Agent` with `run_in_background`) and inter-teammate messaging (`SendMessage`), and runs only in a runtime where they are available. If either is unavailable, do not proceed — report the unmet requirement to the user and abort.

## Trust premise

The QA gate executes commands derived from the destination repository's build definitions (`build-format.md` / `CLAUDE.md` / `README.md`) literally, with full shell privileges. Do not use this skill on a repository whose origin is untrusted. If the repository is judged untrusted, do not start the task; abort and report the reason to the user.

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

The session has a single implicit team (no explicit creation or deletion). Each teammate is spawned once as a background, persistent subagent, keeps its context across steps, goes idle between turns (a message wakes it), and reports each task's completion to whoever assigned it.

Addressing contract:

- A teammate is addressed by the **name** it was spawned with — its role label `architect-{slug}` / `coder-{slug}` / `reviewer-{slug}` / `dev-helper` / `comment-sensei`. A name keeps resolving after the teammate goes idle or completes; the send resumes it from its transcript.
- The newest holder of a name wins, so never spawn two teammates under the same name in a session.
- The leader is reached at `to: "main"`. When teammates DM each other, the leader hands each the other's name in the dispatch message.
- Every `SendMessage` `message` is a string of prose sent with a `summary` (dispatches and reports alike); structured results travel as files, never inside `message`. The protocol objects are the only exception (`${CLAUDE_PLUGIN_ROOT}/rules/teammate.md` § Tools).

The leader runs event-driven and holds no shared task list: it dispatches, ends its turn, and is re-invoked by teammate messages (`to: "main"`). It tracks the roster (each teammate's name → `agentType`), the pairings, and each cell's status in its own working state (and may surface it to the user via `TodoWrite`), and starts the next step once the step's gate condition is met.

## Agent types and spawn requirements

Spawn each teammate with the Agent tool. Rather than copying an exact argument list, meet these requirements: launch it as a background, persistent subagent (so a follow-up message continues it), pass the spawn contract as its prompt, include a `description`, set `name` to its role label, and record that name in the roster.

Agent type (subagent_type):

- Bundled agents are named with the plugin namespace: `cdev:dev-helper`, `cdev:comment-sensei`.
- Reviewers use the registered name team-analysis returns (project `.claude/agents` / user `~/.claude/agents` agents keep their registered name).
- Architects and coders always run as `general-purpose`. Some specialist agents emit tool calls as text and stall, so work cannot continue. A producer (architect / coder) works to its assigned scope and the project's conventions; domain correctness is enforced by the specialist reviewers in review.

## Spawn contract

Spawn each teammate once with the prompt below. It fixes the role and the reporting protocol; each later message names the template to Read for that task. For common prohibitions and the cell protocol, see `${CLAUDE_PLUGIN_ROOT}/rules/teammate.md`.

```
You are joining the team as {role}. For each task I assign, I name a template under `${CLAUDE_PLUGIN_ROOT}/skills/coding/templates/` and give its variables; Read that template and follow it for that task. Common variables: plugin_root = ${CLAUDE_PLUGIN_ROOT}, doc_lang = {doc_lang}. Report each task result to whoever assigned it — the leader at to: "main", or the requesting teammate's name — counts / paths / one-line summary only; route detailed findings peer-to-peer to the recipient's name via SendMessage (I hand you each recipient's name), as the template directs. Read `${CLAUDE_PLUGIN_ROOT}/rules/teammate.md` and observe the common prohibitions and the review-cell protocol.
```

## Review cell protocol

A cell pairs a producer (an architect or a coder) with one reviewer, who run the protocol in `${CLAUDE_PLUGIN_ROOT}/rules/teammate.md` § Review cell autonomously: the producer creates its output, the reviewer DMs its actionable (`Critical` / `Major`) findings to the producer and reports severity counts to the leader, the producer triages each finding, and review ⇄ triage repeats up to `--review-rounds`.

Gate on closure: every cell ends in one closure report to `to: "main"` naming the cell id — resolved, or closed on round-cap exhaustion with a `FIXME:` left at any unresolved `Critical`. A `Critical` disagreement reaches the leader as an escalation before that closure.

Triage and arbitration judgment priority: (1) the user's original task instructions, then (2) the upstream design intent.

## Escalation

When a reviewer escalates a `Critical` disagreement, the leader arbitrates by the judgment priority above. If the leader cannot decide either, it presents a summary of the dispute to the user and has the producer insert a `FIXME:` at the location (requested via `SendMessage` to the producer's name). It proceeds without waiting for the user's reply; the unresolved item is recorded for the downstream authoritative review.

## Leader scope (body isolation)

The leader holds only the roster (each teammate's name → agentType), the pairings, each cell's status, severity counts, file paths, and the QA result. Design bodies, source, and finding bodies stay with the teammates; findings travel producer ⇄ reviewer by `SendMessage`.

## Working directory

```
{tmp_dir} = .claude/tmp/cdev-coding-{timestamp}/
{tmp_dir}/team.jsonl               ← team-analysis result (roster; read by the leader)
{tmp_dir}/design/design-{slug}.md  ← one design section per architect (read by reviewers and coders)
{tmp_dir}/baseline-tree            ← pre-coding working-tree snapshot (baseline for the QA diff)
{tmp_dir}/changes.txt              ← diff since coding start (input to QA)
{tmp_dir}/qa-result.jsonl          ← QA result
{tmp_dir}/build.log                ← build / test output captured by dev-helper
```

Created in Step 1 with `mkdir -p`; removed by the leader in Step 5 via `${CLAUDE_PLUGIN_ROOT}/scripts/del-tmp.sh {tmp_dir}`.

## Step 1 — Form the team and pair

1. This skill operates only on a clean working tree: run `git status --porcelain`, and if the output is non-empty (staged, unstaged, or untracked entries exist), display an error message on the console and terminate the skill.
2. Resolve `{timestamp}`, fix `{tmp_dir}`, and create it (`mkdir -p {tmp_dir}/design`). Then record the pre-coding baseline: `${CLAUDE_PLUGIN_ROOT}/scripts/fetch-diff.sh snapshot {tmp_dir}/baseline-tree`.
3. Console: `## Step 1 — Team formation`.
4. Spawn `dev-helper` (type `cdev:dev-helper`, name `dev-helper`). To it, `SendMessage` naming `templates/team-analysis.md` with `task = {task specification}`, `output_path = {tmp_dir}/team.jsonl`. On its completion report, Read `{tmp_dir}/team.jsonl`: `{task_summary, target_languages, has_test_suite, architects:[{name, slug, scope, reviewer, reason}], coders:[{name, slug, scope, reviewer, reason}], reviewers:[{name, slug, reason}], rationale}` (`name` is the subagent_type to spawn). Each producer's `reviewer` is the paired reviewer's `slug` (one reviewer may be paired to several producers, but only within the same domain).
5. Spawn each roster member, naming it `architect-{slug}` / `coder-{slug}` / `reviewer-{slug}` and using the `name` team-analysis returns as the type (architects and coders use `general-purpose`). Hold the pairings and `{task_summary}`. A producer's paired reviewer is addressed as `reviewer-{the producer's reviewer slug}`.
6. Console: the roster with each producer's paired reviewer and one-line reasons.

## Step 2 — Design cells (設計)

1. Console: `## Step 2 — Design`.
2. For each architect, start the design cell `design-{slug}` with two messages (addressed to roster names):
   - To `architect-{slug}`, `SendMessage` naming `templates/design.md` with `task = {task_summary}`, `assigned_scope = {its scope}`, `output_path = {tmp_dir}/design/design-{slug}.md`, `reviewer = {paired reviewer's name}`.
   - To the paired reviewer's name, `SendMessage` naming `templates/design-review.md` with `task = {task_summary}`, `design_path = {tmp_dir}/design/design-{slug}.md`, `producer = architect-{slug}`, `cell_task = design-{slug}`, `review_rounds = {--review-rounds}`.
3. Gate: one closure report per design cell, arbitrating any escalation as it arrives. Collect the section paths as `{design_paths}`.

## Step 3 — Code cells (コーディング)

1. Console: `## Step 3 — Coding`. Spawn `comment-sensei` (type `cdev:comment-sensei`, name `comment-sensei`) with role `the comment reviewer; a coder DMs you to review comments per templates/comment-review.md`.
2. For each coder, start the code cell `code-{slug}` with two messages (addressed to roster names):
   - To `coder-{slug}`, `SendMessage` naming `templates/code.md` with `task = {task_summary}`, `design_paths = {design_paths}`, `assigned_scope = {its scope}`, `tdd = {has_test_suite}`, `feedback = (none)`, `reviewer = {paired reviewer's name}`, `comment_reviewer = comment-sensei`.
   - To the paired reviewer's name, `SendMessage` naming `templates/code-review.md` with `task = {task_summary}`, `design_paths = {design_paths}`, `producer = coder-{slug}`, `cell_task = code-{slug}`, `review_rounds = {--review-rounds}`.
3. Gate: one closure report per code cell, arbitrating any escalation.

## Step 4 — QA gate

Run the QA verify ⇄ fix loop, up to `--qa-attempts`.

1. Console: `## Step 4 — QA (attempt {n})`.
2. Capture the diff since coding start: `${CLAUDE_PLUGIN_ROOT}/scripts/fetch-diff.sh diff {tmp_dir}/baseline-tree {tmp_dir}/changes.txt`.
3. To `dev-helper`, `SendMessage` naming `templates/qa.md` with `tmp_dir = {tmp_dir}`, `diff_path = {tmp_dir}/changes.txt`, `attempt_num = {n}`. Retain its one-line completion report as `{summary_line}`, then Read `{tmp_dir}/qa-result.jsonl`: `{success}` is `failure == null`; `{suggested_specialist}` / `{error_summary}` are the corresponding `failure` fields. If `workflow_warning` is non-null, retain it for Step 5.
4. If `success == true`, exit the loop.
5. If `success == false` and attempts remain, run a QA-fix cell:
   a. Cover the failing scope with a `general-purpose` coder and a paired reviewer whose domain matches the failure (`{suggested_specialist}` is the hint). Reuse roster members that fit; otherwise spawn under a `coder-{slug}` / `reviewer-{slug}` name not already in the roster. A newly spawned reviewer uses `{suggested_specialist}` as its subagent_type when that exists as a registered name per § Agent types and spawn requirements, otherwise `general-purpose`.
   b. To the coder's name, `SendMessage` naming `templates/code.md` with `task = {task_summary}`, `design_paths = {design_paths}`, `assigned_scope = {the failing files}`, `tdd = {has_test_suite}`, `feedback = QA failure — Read {tmp_dir}/qa-result.jsonl (failure section) and {tmp_dir}/build.log; fix the build/test error.`, `reviewer = {paired reviewer's name}`, `comment_reviewer = comment-sensei`; and to the reviewer's name, `SendMessage` naming `templates/code-review.md` with `task = {task_summary}`, `design_paths = {design_paths}`, `producer = {the coder's name}`, `cell_task = code-qa-{n}`, `review_rounds = {--review-rounds}`.
   c. When you receive the reviewer's closure report for that cell, return to step 1 of this loop (re-QA).
6. If still failing after the max attempts, present `error_summary` to the console and proceed to Step 5.

## Step 5 — Clean up and report

1. If `--commit` is on and QA passed, commit the implementation: stage only the changed source files (not `.claude/tmp`), and commit once with a concise message (no finding IDs).
2. Shut down the teammates: to each teammate's name, `SendMessage` `{type: "shutdown_request"}` and wait for shutdown.
3. Remove the working directory: `${CLAUDE_PLUGIN_ROOT}/scripts/del-tmp.sh {tmp_dir}`.
4. Report to the console: the team roster with pairings, the cells resolved per step, any escalations and the `FIXME:`s left for unresolved items, files changed, the QA result (`summary_line`, plus `workflow_warning` if any), and any unfixed QA failure.
