---
name: rounds
description: Automatically iterate review, triage, respond, and resolve across multiple rounds until no actionable findings remain
allowed-tools: Agent, Read, Glob, Grep, Bash(grep:*), Bash(ls:*), Bash(find:*), Bash(git branch:*), Bash(mkdir:*)
---

# Automatic Review Round Execution

You act as the **review round orchestrator**, automatically iterating a flow equivalent to `/creview:start` → `/creview:triage` → `/creview:respond` → `/creview:resolve` across multiple rounds to comprehensively discover and fix significant issues. Each phase is run by a phase leader sub-agent; you control the round loop and aggregate the phases' return values. See "Sub-agent usage rules" for detailed responsibility allocation.

## Input

The user may optionally specify an output base path. When the argument is `$ARGUMENTS`, interpret it as the output base path (and options). When no output base path is specified, use the project root's `.claude/tmp/` as the default.

## Options

- `--confirm` (default OFF) — After triage / estimate are persisted into the review document (Step 2.2) and before the fix phase (Step 2.3), present the estimate summary to the user and wait for confirmation.
- `--confirm-round` (default OFF) — After resolve, if unresolved findings remain, wait for user confirmation before proceeding to the next round.
- `--commit` (default OFF) — Perform a git commit after each finding is fixed (passed through to the respond phase).
- `--max-rounds N` (default 5, range 1–10) — Change the maximum number of rounds for the outer loop.
- `--base {branch}` (default `main` or `master`) — Specify the base branch (passed to the review phase).
- `--adversarial` (default OFF) — Run the review phase in adversarial mode (passed through to the review phase).

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
- **Each phase is delegated whole to a phase leader sub-agent** (`subagent_type="review-leader"`). The phase sub-agent invokes the corresponding skill and runs it end to end — that skill's own sub-agents, its compile step, and its internal re-execution loops. The phase sub-agent in turn spawns sub-agents, and the triage sub-agent spawns its own challenge / adjudication sub-agents, so a nested spawn depth of 3 or more is required.
  - Review phase (Step 2.1) — `creview:start`
  - Triage & estimate phase (Step 2.2 / 2.5) — `creview:triage`
  - Respond phase (Step 2.3 / 2.5) — `creview:respond`
  - Resolve phase (Step 2.4 / 2.5) — `creview:resolve`
- **Final report aggregator sub-agent (Step 3)** — `subagent_type="review-helper"`; generates the final report from all rounds' review documents.
- **What you handle directly is limited to the following:**
  - Console headings, round loop control, and the feedback re-fix loop.
  - Phase sub-agent launch and aggregation of their return values (counters, paths, one-line summaries).
  - User interaction for `--confirm` / `--confirm-round`. A phase sub-agent cannot reach the user, so every wait for confirmation happens here, between phases.
  - Final summary presentation to the user.
- **Do not put review finding bodies or judgment bodies into context.** Hold only file paths and counters; the details stay inside each phase.
- Each round's results are passed to the next Step / next round **only through the review document**.
- Do not specify `model="..."` when launching (the model follows each agent definition's frontmatter).

## Phase sub-agent launch

Launch every phase via `Agent(subagent_type="review-leader", prompt=...)`:

```
As your first action, you MUST Read `${CLAUDE_PLUGIN_ROOT}/skills/rounds/templates/{template}`. Do not perform any other judgment, action, or tool call before the Read completes. After reading, follow its instructions.

Variables (substitute into the template's {{...}} placeholders):
- plugin_root: ${CLAUDE_PLUGIN_ROOT}
- {the variables the Step lists}

Round-specific overrides (apply after following the template's instructions):
- {the overrides the Step lists, or (none)}

Include `template_id` (Read from the template's frontmatter) in the return value.
```

Verify that the returned `template_id` matches the UUID the Step specifies; relaunch the phase sub-agent on mismatch. The same convention applies to the Step 3 sub-agent; see `${CLAUDE_PLUGIN_ROOT}/rules/sub-agent.md` § Launch prompt completeness.

## Flow overview

```
Round 1 start
  ├─ 2.1 review          [phase Sub] creview:start   → round1.md
  ├─ 2.2 triage+estimate  [phase Sub] creview:triage  → persists triage / estimate
  │     ↳ --confirm: present the estimate summary, wait for confirmation
  ├─ 2.3 respond / fix    [phase Sub] creview:respond → persists status
  │     ↳ skipped when there is no Maintain / Alternative target
  ├─ 2.4 resolve          [phase Sub] creview:resolve → persists verification
  ├─ 2.5 feedback re-fix loop (max 3) → re-run 2.2 → 2.3 → 2.4 with feedback overrides
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

### 2.1 — Review phase (start skill)

1. Display in console: `## Round {N} — Step 1: Review`
2. Launch the phase sub-agent with `templates/phase-review.md` (`template_id`: `3e7b1c9d-6a24-4f85-b1d7-8c2e5a9f3b64`).
   - Variables: `base` (`--base` value), `document_path` (this round's file path), `language` (user's chat language), `adversarial` (`--adversarial` state)
   - Overrides: (none)
3. Hold only the return value (`{doc_path, findings_total, severity_counts}`) in context.

### 2.2 — Triage & estimate phase (triage skill)

1. Display in console: `## Round {N} — Step 2: Triage & Estimate`
2. Launch the phase sub-agent with `templates/phase-triage.md` (`template_id`: `6d2a8f4c-1e93-4b57-9c8a-3f7b2d6e1a95`).
   - Variables: `document_path` (this round's file path), `previous_round_doc_paths` (Round 1: `(none)`; Round N: doc_paths of Round 1..N-1)
   - Overrides: outside the feedback loop, (none); inside it, the ones Step 2.5 lists
3. Hold only the return value (`{will_fix_count, wontfix_count, flipped_count, maintain_count, alternative_count, downgrade_count, summary_path, summary_line, error}`) in context.
4. When `error` is non-null, do not proceed to 2.3 or beyond: report the failure to the user and end the round loop.
5. Round loop control: when `will_fix_count` is 0, or when `maintain_count` and `alternative_count` are both 0, skip 2.3 and proceed to 2.4.
6. `--confirm`: when at least one Maintain / Alternative exists, Read `summary_path`, present it to the user, and wait for confirmation before 2.3.

### 2.3 — Respond phase (respond skill)

1. Display in console: `## Round {N} — Step 3: Respond (Fix & Verify)`
2. Launch the phase sub-agent with `templates/phase-respond.md` (`template_id`: `8b5e3d7a-4c16-4a92-a7f3-2d9c6b1e8f47`).
   - Variables: `document_path`, `commit_flag` (`--commit` state)
   - Overrides: outside the feedback loop, (none); inside it, the ones Step 2.5 lists
3. Hold only the return value (`{fix_count, fixed_count, code_changed, workflow_warning, summary_line}`) in context. When `workflow_warning` is non-null, retain it for this round's record.

### 2.4 — Resolve phase (resolve skill)

1. Display in console: `## Round {N} — Step 4: Resolve`
2. Launch the phase sub-agent with `templates/phase-resolve.md` (`template_id`: `2f9c6a1e-7b53-4d84-8e2b-5a1f9d3c7b26`).
   - Variables: `document_path`, `base` (`--base` value)
   - Overrides: outside the feedback loop, (none); inside it, the ones Step 2.5 lists
3. Hold only the return value (`{summary_path, summary_line, resolved_count, feedback_count, unresolved_count}`) in context.

### 2.5 — Feedback confirmation and re-fix loop

From the Step 2.4 return value (`feedback_count`), determine whether findings that "require feedback" remain. Do not Read the review document body.

- `feedback_count == 0`: end the round (proceed to 2.6).
- `feedback_count > 0`: enter the re-fix loop (max 3).

Each attempt re-runs 2.2 → 2.3 → 2.4, passing the text below as the phase sub-agent's `overrides` variable:

1. Display `## Round {N} — Step 5.1: Feedback Triage (attempt {M}/3)`. Re-run 2.2 with the overrides `Triage sub-agent: triage findings whose stage is "feedback" with priority (current_meta.verification has Feedback details).` and `Estimate sub-agent: estimate based on the Feedback content in current_meta.verification. Consider Downgrade if cost grows.` When all are Downgrade, skip step 2 and go to step 3.
2. Display `## Round {N} — Step 5.2: Feedback Fix (attempt {M}/3)`. Re-run 2.3 with the override `Fix sub-agent: re-fix based on the Feedback content in current_meta.verification.` When the returned `workflow_warning` is non-null, update this round's recorded value (last write wins).
3. Display `## Round {N} — Step 5.3: Feedback Verify (attempt {M}/3)`. Re-run 2.4 with overrides `(none)`.
4. If feedback remains, return to step 1. If not resolved within 3 attempts, end the round (remaining 💬 Feedback are counted as "unresolved" in 2.6).
5. When `--confirm-round` is enabled and unresolved findings remain, wait for user confirmation before proceeding to the next round.

### 2.6 — Round end

Record the round's results. Each counter is obtained from phase sub-agent return values (do not Read the review document body to count):

- Total findings: the review phase's `findings_total`
- Findings requiring action: the triage phase's `will_fix_count`
- Won't Fix count: the triage phase's `wontfix_count`
- Flipped count: the triage phase's `flipped_count`
- Maintain / Alternative / Downgrade counts: the triage phase's `maintain_count` / `alternative_count` / `downgrade_count`
- Fixed count: the respond phase's `fixed_count` (sum of Maintain normal fixes + Alternative FIXME attachments)
- Unresolved count: the resolve phase's `feedback_count` after the final attempt of Step 2.5
- Resolved count: the resolve phase's `resolved_count`
- Feedback attempts: the number of Step 2.5 attempts performed in this round
- workflow_warning: the `workflow_warning` retained in 2.3 / 2.5 (only for rounds where the format / build procedure was unresolved; null otherwise)

Condition for proceeding to the next round: only when **all** of the following are met, increment the round counter and return to Step 2.1:

1. The round counter is at most `--max-rounds`.
2. The respond phase's `code_changed` is true for this round. Treat it as false when Step 2.3 was skipped.

If not met, proceed to final report generation.

## Step 3 — Final report (delegate to the final report aggregator sub-agent)

Final report path: `{base-path}/{branch-dir}/final-report.md`

1. Launch the sub-agent via `Agent(subagent_type="review-helper", prompt=...)` with `templates/final-report-compile.md` (`template_id`: `4f8a2d1c-9b35-4e67-a2c1-8b5d3f9e7a16`).
   - Variables:
     - `round_doc_paths`: Round 1 → {round1_doc_path}, Round 2 → {round2_doc_path}, ...
     - `round_stats`: Round 1: findings=N, will_fix=N, flipped=N, maintain=N, alternative=N, downgrade=N, fixed=N, wontfix=N, feedback_attempts=N, unresolved=N, code_changed=<bool>, ... (for rounds whose workflow_warning is non-null, append workflow_warning="..." at the end)
     - `template_path`: {template_path}
     - `report_path`: {report_path}
     - `language`: user's chat language
   - Overrides: (none)
2. The orchestrator receives the return value (`{report_path, template_id}`) and holds only `report_path` in context.

### Final report format

Template: `${CLAUDE_PLUGIN_ROOT}/skills/rounds/templates/final-report.md` (the final report aggregator Sub Reads it to grasp the skeleton. The leader fills this path into the Sub prompt's `{template_path}`).

## Step 4 — Completion report

Report the final report path to the user, and concisely convey key statistics (total findings, resolved count, unresolved count).
