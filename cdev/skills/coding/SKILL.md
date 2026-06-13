---
name: coding
description: Orchestrate a coding task end to end with a standing agent team — design, design review, coding, QA, and code review — with architects, coders, and reviewers auto-selected from the destination project agents. Use proactively when the user asks to implement a feature, build a change, or carry out a coding task. Requires a runtime with agent-team tools (TeamCreate / SendMessage / Task tools).
allowed-tools: Agent, TeamCreate, SendMessage, TeamDelete, TaskCreate, TaskUpdate, TaskList, Read, Glob, Grep, Bash(mkdir:*), Bash(grep:*), Bash(ls:*), Bash(find:*), Bash(git log:*), Bash(git diff:*), Bash(git show:*), Bash(git status:*), Bash(git branch:*), Bash(git add:*), Bash(git commit:*), Bash(${CLAUDE_PLUGIN_ROOT}/scripts/fetch-diff.sh:*), Bash(${CLAUDE_PLUGIN_ROOT}/scripts/rm-tmp.sh:*)
---

# Multi-Agent Coding

As the **coding leader (team lead)**, you assemble a standing team of specialist teammates and drive them through five phases — design, design review, coding, QA, and code review — sequencing the phases and the feedback loops.

The leader does not design, write, review, or fix code. The leader forms the team, creates and assigns tasks, sequences phases, and reports progress. The specialists are persistent teammates that retain context across phases and route feedback to each other directly.

## Requirements

This skill uses agent-team tools (`TeamCreate`, `SendMessage`, `TaskCreate` / `TaskUpdate` / `TaskList`, `TeamDelete`) and runs only in a runtime where they are available.

## Input

The user supplies a coding task: a feature to implement, a change to make, or a bug to fix, optionally with target paths or a language. When the argument is `$ARGUMENTS`, interpret it as the task specification (including options).

## Options

- `--design-rounds N` (default 2, range 1–5) — Max design-review ⇄ design-revision iterations.
- `--review-rounds N` (default 2, range 1–5) — Max code-review ⇄ code-fix iterations.
- `--qa-attempts N` (default 5, range 1–10) — Max QA verify ⇄ coder-fix attempts per QA run.
- `--base {branch}` (default `main` or `master`) — Base branch for diff capture in QA and code review.
- `--commit` (default OFF) — After QA and code review pass, commit the implementation in one commit (concise message, no finding IDs).

## Output language

Design documents and finding descriptions are written in the user's chat language. The leader fixes the current chat language as `{doc_lang}` (e.g. `日本語`, `English`) and passes it to every teammate at spawn. Structural anchors (severity labels `Critical` / `Major` / `Minor` / `Info`, JSON field names) do not change regardless of `{doc_lang}`.

## Timestamp (`{timestamp}`)

`{timestamp}` is a date-time string (format `YYYYMMDD-HHMMSS`) fixed once at the start of Step 1 and reused in all later steps.

## Team model

`TeamCreate` creates a team and its shared task list (the team and its task list are 1:1). Each teammate is spawned once via the Agent tool with `team_name` and `name`, persists across phases, is addressed by `name` via `SendMessage`, goes idle between turns (a message wakes it), and marks its work via `TaskUpdate`.

Teammate names:
- `architect-{slug}` — one per architect
- `coder-{slug}` — one per coder (`{slug}` from its scope)
- `reviewer-{n}` — one per reviewer
- `dev-helper` — team formation and QA (bundled agent)
- `comment-sensei` — comment review (bundled agent; spawned in Step 6 when comments are present)

## Spawn contract

Spawn each teammate once with the prompt below. It fixes the role and the reporting protocol; each later task message names the template to Read for that task. For common prohibitions, see `${CLAUDE_PLUGIN_ROOT}/rules/teammate.md`.

```
You are joining team {team_name} as {role}. For each task I assign, I name a template under `${CLAUDE_PLUGIN_ROOT}/skills/coding/templates/` and give its variables; Read that template and follow it for that task. Common variables for all tasks: plugin_root = ${CLAUDE_PLUGIN_ROOT}, doc_lang = {doc_lang}. Report each task result to the leader via SendMessage (counts / paths / one-line summary only); route detailed findings as the template directs; mark each assigned task done via TaskUpdate. Read `${CLAUDE_PLUGIN_ROOT}/rules/teammate.md` and observe the common prohibitions.
```

For task-message and routing conventions, see `${CLAUDE_PLUGIN_ROOT}/rules/teammate.md` § Team conventions.

## Leader scope (body isolation)

The leader holds only the roster, task ids / status, severity counts, file paths, and the QA result. Design bodies, source, and finding bodies stay with the teammates: reviewers route detailed findings to the owning `architect` / `coder` by `SendMessage`, and report only severity counts to the leader.

## Working directory

```
{tmp_dir} = .claude/tmp/cdev-coding-{timestamp}/
{tmp_dir}/design/{slug}.md   ← one design section per architect (read by reviewers and coders)
{tmp_dir}/changes.txt        ← working-tree diff (input to QA and code review)
{tmp_dir}/qa-result.json     ← QA result
{tmp_dir}/build.log          ← build / test output captured by dev-helper
```

Created in Step 1 with `mkdir -p`; removed by the leader in Step 7 via `${CLAUDE_PLUGIN_ROOT}/scripts/rm-tmp.sh {tmp_dir}`.

## Actionable findings

A reviewer reports severity counts to the leader. A finding is **actionable** when its severity is `Critical` or `Major`. The leader continues a feedback loop only while `critical + major > 0` and iterations remain; `Minor` / `Info` are advisory.

## Step 1 — Form the team

1. Resolve `{timestamp}`, fix `{tmp_dir}`, and create it: `mkdir -p {tmp_dir}/design`.
2. Console: `## Phase 0 — Team formation`.
3. `TeamCreate({team_name: "cdev-coding-{timestamp}"})`.
4. Spawn `dev-helper` via `Agent(subagent_type="dev-helper", team_name, name="dev-helper", prompt=<spawn contract, role="the team-formation and QA helper">)`.
5. `TaskCreate` a team-analysis task (owner `dev-helper`) and `SendMessage(dev-helper, ...)` naming `templates/team-analysis.md` with variable `task = {task specification}`. Receive its report: `{task_summary, target_languages, has_test_suite, architects:[{name, slug, scope, reason}], coders:[{name, slug, scope, reason}], reviewers:[{name, reason}], rationale}`.
6. For each roster member, spawn a teammate via `Agent(subagent_type={name}, team_name, name={role-name}, prompt=<spawn contract>)`: `architect-{slug}`, `coder-{slug}`, `reviewer-{n}`. Hold the scope map (which `coder-{slug}` / `architect-{slug}` owns which files).
7. Console: the roster with one-line reasons. Hold the roster and `{task_summary}` in context.

## Step 2 — Design (設計)

1. Console: `## Phase 1 — Design`.
2. For each architect, `TaskCreate` a design task (owner `architect-{slug}`) and `SendMessage` it naming `templates/design.md` with variables: `task = {task_summary}`, `assigned_scope = {its scope}`, `output_path = {tmp_dir}/design/{slug}.md`.
3. Each architect writes its section, marks the task done, and reports `{path, summary}`. Collect the section paths as `{design_paths}`.

## Step 3 — Design review (設計レビュー)

Iterate up to `--design-rounds`.

1. Console: `## Phase 2 — Design Review (iteration {i})`.
2. For each reviewer, `TaskCreate` a review task (owner `reviewer-{n}`) and `SendMessage` it naming `templates/design-review.md` with variables: `task = {task_summary}`, `design_paths = {design_paths}`, `scope_map = {architect → scope}`. The reviewer DMs its actionable findings to the owning `architect-{slug}`, reports `{critical, major, minor, info}` to the leader, and marks the task done.
3. Sum `critical + major` across reviewers.
4. If the sum is 0, or this was the last allowed iteration, exit the loop (design settled).
5. Otherwise, `SendMessage` each architect that received findings, naming `templates/design.md` with the same variables, to revise its section and resolve the actionable findings the reviewer DM'd it (it retains its design context). When the architects mark their revisions done, return to step 2 of this loop.

## Step 4 — Coding (コーディング)

1. Console: `## Phase 3 — Coding`.
2. For each coder, `TaskCreate` a coding task (owner `coder-{slug}`) and `SendMessage` it naming `templates/code.md` with variables: `task = {task_summary}`, `design_paths = {design_paths}`, `assigned_scope = {its scope}`, `tdd = {has_test_suite}`, `feedback = (none)`. Coders own disjoint file scopes.
3. Each coder implements its scope, marks the task done, and reports `{files_changed, has_comments, summary}`. Set `{comments_present}` to true if any coder reported `has_comments == true`.

## Step 5 — QA

Run the QA verify ⇄ coder-fix loop, up to `--qa-attempts`.

1. Console: `## Phase 4 — QA (attempt {n})`.
2. Capture the working-tree diff: `${CLAUDE_PLUGIN_ROOT}/scripts/fetch-diff.sh {base} {tmp_dir}/changes.txt`.
3. `TaskCreate` a QA task (owner `dev-helper`) and `SendMessage(dev-helper, ...)` naming `templates/qa.md` with variables: `tmp_dir = {tmp_dir}`, `diff_path = {tmp_dir}/changes.txt`, `attempt_num = {n}`. Receive `{success, format_violations_fixed, workflow_source, workflow_warning, build_ran, test_ran, suggested_specialist, error_summary, summary_line}`. If `workflow_warning` is non-null, retain it for Step 7.
4. If `success == true`, exit the loop.
5. If `success == false` and attempts remain: ensure `{suggested_specialist}` is a teammate (spawn `coder-{suggested_specialist}` if it is not already on the team), then `SendMessage` it naming `templates/code.md` with `feedback = QA failure — Read {tmp_dir}/qa-result.json (failure section) and {tmp_dir}/build.log; fix the build/test error.`, `assigned_scope = {the failing files}`, and `tdd = {has_test_suite}`. After it marks the fix done, return to step 1 of this loop.
6. If still failing after the max attempts, present `error_summary` to the console and proceed to Step 6.

## Step 6 — Code review (コードレビュー)

Iterate up to `--review-rounds`.

1. Console: `## Phase 5 — Code Review (iteration {i})`.
2. Capture the current diff: `${CLAUDE_PLUGIN_ROOT}/scripts/fetch-diff.sh {base} {tmp_dir}/changes.txt`.
3. For each reviewer, `TaskCreate` a review task and `SendMessage` it naming `templates/code-review.md` with variables: `task = {task_summary}`, `diff_path = {tmp_dir}/changes.txt`, `design_paths = {design_paths}`, `scope_map = {coder → scope}`. The reviewer DMs its actionable findings to the owning `coder-{slug}`, reports `{critical, major, minor, info}` to the leader, and marks the task done.
4. When `{comments_present}` is true: ensure a `comment-sensei` teammate exists (spawn it if not), then `SendMessage` it naming `templates/comment-review.md` with variables: `diff_path = {tmp_dir}/changes.txt`, `design_paths = {design_paths}`. It fixes comment violations directly and reports `{reviewed_paths, fix_count}`.
5. Sum `critical + major` across reviewers.
6. If the sum is 0, or this was the last allowed iteration, exit the loop.
7. Otherwise, `SendMessage` each coder that received findings to fix them within its scope. When the coders mark their fixes done, set `{comments_present}` to true if any reported `has_comments == true` (keep it true if it already was), re-run Step 5 (QA) once to keep the build/test green, then return to step 3 of this loop.

## Step 7 — Clean up and report

1. If `--commit` is on and QA passed, commit the implementation: stage only the changed source files (not `.claude/tmp`), and commit once with a concise message describing the change (no finding IDs).
2. Shut down the teammates: `SendMessage` each one `{type: "shutdown_request"}` and wait for shutdown.
3. `TeamDelete`.
4. Remove the working directory: `${CLAUDE_PLUGIN_ROOT}/scripts/rm-tmp.sh {tmp_dir}`.
5. Report to the console: the team roster, the phases run (with iteration counts), files changed, the QA result (`summary_line`, plus `workflow_warning` if any), and any unresolved actionable findings or unfixed QA failure.
