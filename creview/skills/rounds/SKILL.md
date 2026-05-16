---
name: rounds
description: Automatically iterate review, triage, respond, and resolve across multiple rounds until no actionable findings remain
allowed-tools: Agent, Read, Write, Edit, Glob, Grep, Bash(grep:*), Bash(ls:*), Bash(find:*), Bash(git log:*), Bash(git diff:*), Bash(git show:*), Bash(git status:*), Bash(git branch:*), Bash(mkdir:*), Bash(cmake:*), Bash(make:*), Bash(clang-format:*), Bash(cmake-format:*), Bash(${CLAUDE_PLUGIN_ROOT}/scripts/rm-tmp.sh:*)
---

# Automatic Review Round Execution

You act as the **review round orchestrator**, automatically iterating a flow equivalent to `/creview:start` → `/creview:triage` → `/creview:respond` → `/creview:resolve` across multiple rounds to comprehensively discover and fix significant issues. You do not take on the role of a reviewer or fix author yourself; everything is delegated to sub-agents. See "Sub-agent usage rules" for detailed responsibility allocation.

## Input

The user may optionally specify an output base path. When the argument is `$ARGUMENTS`, interpret it as the output base path (and options). When no output base path is specified, use the project root's `.claude/tmp/` as the default.

## Options

- `--confirm` (default OFF) — After triage / estimate are persisted into the review document (Step 2.2) and before the fix phase (Step 2.3), present the estimate summary to the user and wait for confirmation.
- `--confirm-round` (default OFF) — After resolve, if unresolved findings remain, wait for user confirmation before proceeding to the next round.
- `--commit` (default OFF) — Perform a git commit after each finding is fixed (passed through to the respond phase).
- `--max-rounds N` (default 5, range 1–10) — Change the maximum number of rounds for the outer loop.
- `--base {branch}` (default `main` or `master`) — Specify the base branch (passed to the review phase).

## Review document file naming

- Format: `{base-path}/{branch-dir}/review-round{N}.md`
- Branch name retrieval: get the current branch name with `git branch --show-current`.
- The branch name is treated as a directory path — the entire branch name (including `/`) becomes the directory hierarchy.
- On re-runs on the same branch, append a sequential number `{branch-name}_1`, `{branch-name}_2`, ... to the suffix (smallest non-existing number).
  - Example: branch `feat/add-replay`, first run → `{base-path}/feat/add-replay/review-round1.md`, re-run → `{base-path}/feat/add-replay_1/review-round1.md`
- Default base-path: `.claude/tmp/`. Create the directory as needed.

## Review document language

Write the review document in the user's chat language.

## Sub-agent usage rules

- **For common prohibitions, see `${CLAUDE_PLUGIN_ROOT}/rules/sub-agent.md`.**
- **The prompt body for each sub-agent is stored in an external template (`templates/*.md`, with `template_id` in the frontmatter).** When launching a sub-agent via the Agent tool, the orchestrator passes a launch prompt that says "Read the template and follow its instructions," with variable values (including `plugin_root: ${CLAUDE_PLUGIN_ROOT}`) and round-specific overrides filled in. The sub-agent includes `template_id` in its return value. The orchestrator verifies that the returned `template_id` matches the UUID specified in each Step (hard-coded per Step in the referenced SKILLs), and relaunches the sub-agent if it does not match. The UUIDs are documented in the `${CLAUDE_PLUGIN_ROOT}/skills/{start,triage,respond,resolve}/SKILL.md` SKILLs.
- **Sub-agent nesting is prohibited** — when you yourself are launched as a sub-agent, you cannot launch further sub-agents from there.
- **Most work, including aggregation and compilation, is delegated to sub-agents** (one level of nesting is allowed):
  - Individual reviewers (Step 2.1) — launch the reviewers selected by the scope-analysis Sub from the destination project's `.claude/agents/` (or `general-purpose`) in parallel. Each reviewer Writes findings to a file; return value is path and counts only.
  - Aggregator sub-agent (Step 2.1) — Reads each individual reviewer's output file and merges them into the review document (start § Step 3).
  - Triage sub-agent (Step 2.2 / 2.5) — judging in a separate context to avoid bias, directly Reads the review document and performs finding extraction and judgment in a single stage (triage § Step 1).
  - Individual estimate (Step 2.2 / 2.5) — delegated in parallel to per-assignee specialist sub-agents; each Sub batch-estimates its assigned ids (triage § Step 2, read-only).
  - Estimate aggregator sub-agent (Step 2.2 / 2.5) — generates a summary of individual estimate results (triage § Step 2).
  - Select-fix-targets sub-agent (Step 2.3 / 2.5) — Reads the review document metadata and returns the fix targets grouped by assignee (respond § Step 1).
  - Individual fix (Step 2.3 / 2.5) — delegated to per-assignee specialist sub-agents; each Sub sequentially fixes its assigned ids (respond § Step 2).
  - Format & build verification sub-agent (Step 2.3 / 2.5) — runs clang-format / cmake-format + build once; on failure, identifies the specialist via code analysis (does not perform fixes; returns recommendation only).
  - Build-fix specialist sub-agent (Step 2.3 / 2.5) — fixes build errors as the specialist identified by the format & build verification Sub. After completion, the leader relaunches the format & build verification Sub (respond § Step 3).
  - Analysis sub-agent (Step 2.4 / 2.5) — Reads the review document and returns the verification assignment (by_assignee) (resolve § Step 1, no file output).
  - Verification sub-agent (Step 2.4 / 2.5) — launched in parallel per specialist; batch-verifies the assigned findings (resolve § Step 2, read-only).
  - Aggregator (compile) sub-agent (Step 2.2 / 2.3 / 2.4 / 2.5) — generates events.jsonl from intermediate files and runs render-review.py (triage § Step 3 / respond § Step 4 / resolve § Step 3).
  - Final report aggregator sub-agent (Step 3) — generates the final report from all rounds' review documents.
- **What the orchestrator (you) directly handles is limited to the following:**
  - Control between Steps and round loop judgment (including the format & build verification Sub ⇄ build-fix specialist Sub re-execution loop. Operational data files from each Sub may be Read; source code itself is not read.).
  - Sub-agent launch and aggregation of return values (lightweight counters, paths, and one-line summaries).
  - Final summary presentation to the user.
- **The orchestrator does not put review finding bodies or judgment bodies into context.** It holds only file paths and lightweight counters; details are handled by sub-agents.
- Each round's results are passed to the next Step / next round **only through the review document**. Intermediate data between sub-agents is self-contained within a Step and must not persist across Steps. (Within a round, triage / estimate are persisted into the document by the triage phase, so the respond phase reads them from the document.)
- **Launch aggregator / compilation / analysis / select-fix-targets / format & build verification sub-agents via `subagent_type="review-helper"` (analysis / compile / estimate-summary / format-build-verify) or `subagent_type="general-purpose"` (triage / select-fix-targets).** `model: sonnet` is already specified in review-helper's agent definition. For reviewer / estimate / fix / verify / build-fix sub-agents, specify the assignee resolved from the destination project's `.claude/agents/` (or `general-purpose`) via `subagent_type`. Do not specify `model="..."` from the SKILL (the model follows each agent definition's frontmatter).

For the launch prompt completeness convention, see `${CLAUDE_PLUGIN_ROOT}/rules/sub-agent.md` § Launch prompt completeness.

## Flow overview

```
Round 1 start
  ├─ 2.1 review (start skill)
  │     [scope-analysis Sub] selects reviewers from destination .claude/agents
  │     [reviewers] parallel → each Writes reviews/{name}.md
  │     [aggregator Sub] reviews/*.md → round1.md (no triage yet)
  ├─ 2.2 triage + estimate (triage skill)
  │     [triage Sub] round1.md → triage.json (includes by_assignee)
  │     ↳ if Will Fix is 0, persist Won't Fix triage and skip to 2.4
  │     [estimate Subs (per-assignee, parallel)] → estimates/{id}.json
  │     [estimate aggregator Sub] estimates/*.json → estimate-summary.md
  │     [compile Sub] triage.json + estimates/*.json → events.jsonl → render-review.py (persists triage/estimate into round1.md)
  │     ↳ --confirm: present estimate summary, wait for confirmation
  ├─ 2.3 respond / fix (respond skill)
  │     [select-fix-targets Sub] round1.md metadata → targets.json (by_assignee)
  │     ↳ if no Maintain/Alternative target, skip to 2.4
  │     [fix Subs (per-assignee, parallel)] fix Maintain, attach FIXME for Alternative → statuses/{id}.json
  │     [format & build verification Sub] ⇄ [build-fix specialist Sub] loop (max 5, leader-controlled)
  │     [compile Sub] statuses/*.json → events.jsonl → render-review.py (persists status)
  ├─ 2.4 resolve (resolve skill)
  │     [analysis Sub] round1.md → by_assignee (no file output)
  │     [verification Subs] per-specialist parallel → verifications/{id}.json
  │     [compile Sub] verifications/*.json → events.jsonl → render-review.py (persists verification)
  ├─ 2.5 feedback re-fix loop (max 3)
  │     [triage Sub] → [estimate Subs] → [compile] → [select-fix-targets] → [fix Subs]
  │       → [format & build verification Sub] ⇄ [build-fix specialist Sub] loop
  │       → [compile] → [analysis Sub] → [verification Subs] → [compile]
  └─ 2.6 round end → judge condition for proceeding to the next round
Round 2 start (do not pass the previous round's review document)
  └─ ...
Final step
  └─ [final report aggregator Sub] all round{N}.md + template → final-report.md
```

## Step 1 — Initialization

1. Verify the output directory exists; if not, create it.
2. Get the current branch name.
3. Parse options.
4. Set the round counter to 1.

## Step 2 — Round loop

While the round counter is at most `--max-rounds`, repeat the following.

### 2.1 — Run review (start skill)

The orchestrator (you) directly takes on the "review leader" role of `/creview:start`. Follow the procedure, templates, and format in `${CLAUDE_PLUGIN_ROOT}/skills/start/SKILL.md`.

Procedure:

1. Display in console: `## Round {N} — Step 1: Review`
2. Per start § Step 1, prepare the working directory and diff file, and launch the scope-analysis sub-agent. Hold only the return values (`line_count` / `recommended_reviewers`) in context.
3. Launch each `name` in `recommended_reviewers` in parallel via `Agent(subagent_type=name, prompt=...)`. Each reviewer Writes findings to `{tmp_dir}/reviews/{name}.md`; return value is `{path, severity counts}` only.
4. Per start § Step 3, launch the aggregator sub-agent to generate the review document (output path: {this round's file path}, language: user's chat language). Hold only the aggregator sub-agent's return value (`{doc_path, findings_total, severity_counts}`) in context.
5. Per start § Step 4, delete `{tmp_dir}`.

Round-specific overrides (apply after following the template's instructions):

- Do not pass the previous round's review document to reviewers (bias avoidance).
- Do not perform deduplication against the previous round.
- Convergence-induction prevention:
  - **The following must NEVER be included in the reviewer's prompt:**
    - Past round finding counts, count trends, or trend information such as "appears to be converging."
    - Past round finding IDs (`C-1`, `M-1`, etc.).
    - Statistics such as Fixed / Won't Fix counts from past rounds.
  - It is prohibited to omit parts of the reviewer prompt template or to add instructions in an attempt to adjust the finding count.
  - The review orchestrator itself is prohibited from adding findings other than those submitted by the reviewers.

### 2.2 — Triage & estimate (triage skill)

The orchestrator (you) directly takes on the "triage leader" role of `/creview:triage`. Follow the procedure and templates in `${CLAUDE_PLUGIN_ROOT}/skills/triage/SKILL.md`.

Input document: {this round's file path}

- Steps 1–3 — delegate to sub-agents per the triage § instructions. The triage skill persists `triage` / `estimate` into the document at its Step 3 (compile).

Round-specific overrides (apply after following the template's instructions):

- Console output: at triage start `## Round {N} — Step 2: Triage`; at estimate start `## Round {N} — Step 2.5: Estimate`.
- Triage sub-agent: pass the list of doc_paths for all past rounds as the `previous_round_doc_paths` variable (Round 1: `(none)`; Round N: doc_paths of Round 1..N-1). For decision behavior, see the Won't Fix guideline in `${CLAUDE_PLUGIN_ROOT}/skills/triage/templates/triage.md`. State the Will Fix count explicitly in the triage report (also when 0).
- Estimate sub-agent: do not reference the previous round's review document (bias avoidance). When determining diffusion signal e (Will Fix originating from FIXME), verify whether the finding originates from a `FIXME:` / `TODO:` in the review body or target file.
- Round loop control after triage: Will Fix == 0 → run the triage compile (persist Won't Fix), then skip 2.3 and proceed to 2.4.
- Round loop control after estimate: when both Maintain and Alternative are 0 (all Downgrade), run the triage compile, skip 2.3, and proceed to 2.4.
- `--confirm`: after the triage compile completes and at least one Maintain / Alternative exists, Read the estimate aggregator's `summary_path`, present it to the user, and wait for confirmation before 2.3.

### 2.3 — Respond / fix (respond skill)

The orchestrator (you) directly takes on the "respond leader" role of `/creview:respond`. Follow the procedure and templates in `${CLAUDE_PLUGIN_ROOT}/skills/respond/SKILL.md`. Pass `--commit` through when the round option is enabled.

Input document: {this round's file path} (triage / estimate already persisted by 2.2)

- Console output: at fix start `## Round {N} — Step 3: Respond (Fix & Verify)`.
- Steps 1–4 — delegate to sub-agents per the respond § instructions. Parallelization and the format & build verification ⇄ build-fix re-execution loop are orchestrated by the leader per that SKILL. The respond compile persists `status` into the document at its Step 4.
- If `fix_count == 0` (no Maintain / Alternative targets), the respond skill's compile reflects nothing; proceed to 2.4.

### 2.4 — Resolve (resolve skill)

The orchestrator (you) directly takes on the "review verification leader" role of `/creview:resolve`. Follow the procedure and templates in `${CLAUDE_PLUGIN_ROOT}/skills/resolve/SKILL.md`.

Input document: {this round's file path}

1. Display in console: `## Round {N} — Step 4: Resolve`
2. Per the resolve § procedure, launch in order: analysis Sub → verification Subs (parallel) → compile Sub.
3. The orchestrator holds only the return values (`{summary_path, summary_line, resolved_count, feedback_count, unresolved_count}`) in context. Do not read the verification body.

### 2.5 — Feedback confirmation and re-fix loop

From the Step 2.4 return value (`feedback_count`), determine whether there are findings that "require feedback." Do not Read the review document body directly.

- `feedback_count == 0`: end the round (proceed to 2.6).
- `feedback_count > 0`: enter the re-fix loop (max 3).

Re-fix loop (max 3) — each attempt re-runs the triage skill flow, then the respond skill flow, then the resolve skill flow. In each sub-agent's launch prompt, add a "Feedback finding priority" constraint to the "Round-specific overrides" section.

1. Display `## Round {N} — Step 5.1: Feedback Triage (attempt {M}/3)`. Re-run the triage skill (2.2). Add to the triage launch prompt overrides: `Triage findings whose stage is "feedback" with priority (current_meta.verification has Feedback details).` Add to the estimate launch prompt overrides: `Estimate based on the Feedback content in current_meta.verification. Consider Downgrade if cost grows.` If all are Downgrade, run the triage compile and skip step 2; go to step 3.
2. Display `## Round {N} — Step 5.2: Feedback Fix (attempt {M}/3)`. Re-run the respond skill (2.3). Add to the fix launch prompt overrides: `Re-fix based on the Feedback content in current_meta.verification.`
3. Display `## Round {N} — Step 5.3: Feedback Verify (attempt {M}/3)`. Re-run the resolve skill (2.4).
4. If feedback remains, return to step 1. If not resolved within 3 attempts, end the round (remaining 💬 Feedback are counted as "unresolved" in 2.6).
5. When `--confirm-round` is enabled and unresolved findings remain, wait for user confirmation before proceeding to the next round.

### 2.6 — Round end

Record the round's results. Each counter is obtained from sub-agent return values (do not Read the review document body to count):

- Findings requiring action: triage Sub's `will_fix_count`
- Maintain / Alternative / Downgrade counts: estimate aggregator Sub's `maintain_count` / `alternative_count` / `downgrade_count`
- Fixed count: respond compile Sub's `fixed_count` (sum of Maintain normal fixes + Alternative FIXME attachments)
- Unresolved count: resolve compile Sub's `feedback_count` after the final attempt of Step 2.5
- Resolved count: resolve compile Sub's `resolved_count`

Condition for proceeding to the next round: only when **all** of the following are met, increment the round counter and return to Step 2.1:

1. The round counter is at most `--max-rounds`.
2. At least one line of source code has changed in this round.

If not met, proceed to final report generation.

## Step 3 — Final report (delegate to the final report aggregator sub-agent)

Final report path: `{base-path}/{branch-dir}/final-report.md`

1. Launch the sub-agent via `Agent(subagent_type="review-helper", prompt=...)`. The task-specific instructions are stored in the external template `templates/final-report-compile.md`. Example launch prompt:

```
As your first action, you MUST Read `${CLAUDE_PLUGIN_ROOT}/skills/rounds/templates/final-report-compile.md`. Do not perform any other judgment, action, or tool call before the Read completes. After reading, follow its instructions.

Variables (substitute into the template's {{...}} placeholders):
- plugin_root: ${CLAUDE_PLUGIN_ROOT}
- round_doc_paths: Round 1 → {round1_doc_path}, Round 2 → {round2_doc_path}, ...
- round_stats: Round 1: findings=N, will_fix=N, maintain=N, alternative=N, downgrade=N, fixed=N, wontfix=N, feedback_attempts=N, unresolved=N, code_changed=<bool>, ...
- template_path: {template_path}
- report_path: {report_path}
- language: user's chat language

Round-specific overrides (apply after following the template's instructions):
- (none)

Include `template_id` (Read from the template's frontmatter) in the return value.
```

2. The orchestrator receives the return value (`{report_path, template_id}`). Verify that `template_id` matches `4f8a2d1c-9b35-4e67-a2c1-8b5d3f9e7a16`. If it does not match, relaunch the sub-agent. Hold only `report_path` in context.

### Final report format

Template: `${CLAUDE_PLUGIN_ROOT}/skills/rounds/templates/final-report.md` (the final report aggregator Sub Reads it to grasp the skeleton. The leader fills this path into the Sub prompt's `{template_path}`).

## Step 4 — Completion report

Report the final report path to the user, and concisely convey key statistics (total findings, resolved count, unresolved count).
