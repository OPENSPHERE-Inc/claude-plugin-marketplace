---
name: start
description: Launch a parallel code review with reviewers auto-selected from the destination project agents. Use proactively when the user asks to review changes, a branch, or a PR (e.g. "review this code"), or right after a substantial implementation is completed.
allowed-tools: Agent, Read, Glob, Grep, Bash(${CLAUDE_PLUGIN_ROOT}/scripts/fetch-diff.sh:*), Bash(${CLAUDE_PLUGIN_ROOT}/scripts/rm-tmp.sh:*), Bash(grep:*), Bash(ls:*), Bash(find:*), Bash(mkdir:*), Bash(git log:*), Bash(git diff:*), Bash(git show:*)
---

# Parallel Code Review

As the **review leader**, you orchestrate a parallel code review using specialist reviewers and consolidate each reviewer's findings into a single report.

The review leader does not act as a reviewer; instead, the leader orchestrates the overall review and performs aggregation and judgment. All reviewer roles are delegated to sub-agents.

## Round Number

If the arguments include a round number (e.g., `Round 1`, `Round 2`), reflect it in the report title.

## Input

The user specifies one or more of the following as the review target:
- File path or glob pattern
- git diff range (e.g., `HEAD~3..HEAD`, branch name, PR)
- Description of the area to review

If the argument is `$ARGUMENTS`, interpret it as the review target specification (including round number and options).

## Timestamp (`{timestamp}`)

`{timestamp}` is a current date-time string (format `YYYYMMDD-HHMMSS`, e.g., `20240101-120000`) determined once at the start of Step 1. The same value is used in all subsequent steps.

## Options

- `--base {branch}` — Specify the base branch. Defaults to `main` or `master`.
- `--output {path}` — Specify the final report output path (`{final_doc_path}`).
- `--adversarial` (default OFF) — Run the Step 2 reviewers with the adversarial reviewer template.

### Adversarial Mode Values

`--adversarial` fixes the following values, used in Step 2 and Step 3:

- OFF (default): `{reviewer_template}` = `reviewer.md`, `{reviewer_template_id}` = `4d8c2e5b-1f73-4a96-b2e8-9c1d3a7f4b62`, `{review_mode}` = `standard`
- ON: `{reviewer_template}` = `adversarial-reviewer.md`, `{reviewer_template_id}` = `2e68714d-36e4-4a4c-a557-d34a81661cb1`, `{review_mode}` = `adversarial`

### Default Review Target

If the user does not explicitly specify a review target, use the following as the default:

1. Commits unique to the current branch — all commits since the divergence from the base branch (equivalent to `git log {base}..HEAD`).
2. Working tree changes — staged (`git diff --cached`) and unstaged (`git diff`) changes.

If no base branch is specified via `--base`, use whichever of `main` or `master` exists on the remote (prefer `main` if both exist).

### Output Destination (`{final_doc_path}`)

- If `--output` is given, use that value.
- Default when not specified: `.claude/tmp/creview-start-{timestamp}.md`. Do not place it under tmp_dir (it would be deleted in Step 4).
- When invoked from an upper orchestrator (e.g., /creview:rounds), the caller specifies the path.

## Output Language

The review document prose (finding descriptions, summary body) is written in the user's chat language. The leader determines the language the user is currently using in the chat, fixes it as `{doc_lang}` (e.g., `日本語`, `English`), and passes it as a variable to the Step 2 reviewers and the Step 3 aggregator sub-agent.

Structural anchors (severity headings `## Critical` / `## Major` / `## Minor` / `## Info`, finding-id, metadata markers) are parsing targets for later phases (triage / respond / resolve), so they do not change regardless of `{doc_lang}`.

## Sub-Agent Launch

For common prohibitions and launch-prompt completeness, see `${CLAUDE_PLUGIN_ROOT}/rules/sub-agent.md` and its § Launch Prompt Completeness. Each sub-agent's instructions live in an external `templates/*.md` carrying a `template_id` in its frontmatter; the launch prompt has the sub-agent Read that template instead of quoting it.

Launch every sub-agent with the prompt below, substituting the template, variables, and overrides the step names:

```
As your first action, you MUST Read `${CLAUDE_PLUGIN_ROOT}/skills/start/templates/{template}`. Do not perform any other judgment, action, or tool call before the Read completes. After reading, follow its instructions.

Variables (substitute into the template's {{...}} placeholders):
- {name}: {value}

Round-specific overrides (apply after following the template's instructions):
- (none)

Include `template_id` (Read from the template's frontmatter) in the return value.
```

Verify each returned `template_id` against the UUID its step names; on mismatch, re-launch that sub-agent.

## Internal Processing (Intermediate Files)

The leader (you) does not place reviewer output bodies in context.

### Working directory

```
{tmp_dir} = .claude/tmp/creview-start-{timestamp}/
{tmp_dir}/diff.txt                    ← Diff fetched by the leader in Step 1 (input to the scope-analysis sub-agent)
{tmp_dir}/reviews/{reviewer-name}.md  ← Output from each reviewer (numbered list of findings)
```

Creation is in Step 1; removal is done by the leader in Step 4 via `${CLAUDE_PLUGIN_ROOT}/scripts/rm-tmp.sh {tmp_dir}`.

## Step 1 — Identify Review Scope and Fetch Diff

The leader (you) does not Read the diff content. Diff analysis, line counting, and selection of required reviewer candidates are delegated to the scope-analysis sub-agent; the leader receives only the return value (line count + candidate list + summary).

1. Based on the user's input, identify the review target (base branch, target paths, etc.) and any explicitly requested reviewers (if any).
2. Resolve `{timestamp}` to fix `{tmp_dir}`, and create the working directory with `mkdir -p {tmp_dir}/reviews`.
3. Fetch diff information via script:
   - Output file path: `{tmp_dir}/diff.txt`
   - Run:
     ```
     ${CLAUDE_PLUGIN_ROOT}/scripts/fetch-diff.sh {base} {tmp_dir}/diff.txt
     ```
4. Launch the scope-analysis sub-agent to analyze the diff — template `scope-analysis.md`, `template_id` `b3e2f1a7-9c84-4d56-8e3b-7f1a4c9d2e85`, variables `plugin_root = ${CLAUDE_PLUGIN_ROOT}`, `tmp_dir = {tmp_dir}`, `user_requested = {user_requested}`, overrides `(none)`. Return value: `{line_count, recommended_reviewers, extension_summary, rationale, template_id}`.
5. Adopt `recommended_reviewers` as-is as the final reviewer list, and pass each element's `name` to `subagent_type` in Step 2.
6. If `line_count == 0`, generate an empty review document at `{final_doc_path}` and proceed directly to Step 4.

## Step 2 — Launch Parallel Reviewers

Launch all selected reviewers concurrently via the Agent tool. Each reviewer must not return findings to stdout; instead, they Write to a dedicated file. The review leader (you) must not load reviewer output bodies into context (the aggregator sub-agent reads them in a later step).

### Reviewer Output Files

- One file per reviewer: `{tmp_dir}/reviews/{reviewer-name}.md`
- Content is only the "numbered list of findings" (no greetings or overall summaries before or after)
- Format: numbered list of `[severity] [category] file_path:line — Description of the issue and its importance.`. Assign one or more category labels; if multiple, join them with `/` inside a single `[ ]` (e.g., `[Bug/Maintainability]`). See the reviewer template for preset details.

### Reviewer Launch

Specify `subagent_type={name}` (the name resolved by the scope-analysis Sub from the destination project's `.claude/agents/`, or `general-purpose`). The agent definition's persona and perspective load automatically; do not include the persona / perspective in the launch prompt.

Template `{reviewer_template}`, `template_id` `{reviewer_template_id}`, variables `plugin_root = ${CLAUDE_PLUGIN_ROOT}`, `targets = {targets}`, `base = {base}`, `diff_path = {diff_path}`, `output_path = {output_path}`, `doc_lang = {doc_lang}`, overrides `(none)`. Return value from each reviewer: `{path, critical, major, minor, info, template_id}`.

## Step 3 — Consolidate the Report (Delegate to Aggregator Sub-Agent)

After all reviewers complete, launch the aggregator sub-agent and delegate report consolidation to it.
The review leader does not perform aggregation work (Reading each reviewer file, deduplicating, sorting, Writing the deliverable) and does not load reviewer output bodies into context.

Launch via `Agent(subagent_type="review-helper", prompt=...)` (model follows review-helper's agent definition; do not specify model from the leader).

Template `aggregator.md`, `template_id` `7a5f8c1d-3e92-4b67-9c4a-2d8e1f7b3c54`, variables `plugin_root = ${CLAUDE_PLUGIN_ROOT}`, `tmp_dir = {tmp_dir}`, `reviewer_paths_list = {reviewer_paths_list}`, `final_doc_path = {final_doc_path}`, `round_num_or_omitted = {round_num_or_omitted}`, `targets_description = {targets_description}`, `reviewer_names_csv = {reviewer_names_csv}`, `review_mode = {review_mode}`, `doc_lang = {doc_lang}`, overrides `(none)`. Return value: `{doc_path, findings_total, severity_counts, duplicates_merged, template_id}`.

## Step 4 — Clean Up Temporary Files

After the aggregator sub-agent completes Writing the final report, delete the entire working directory created in Step 1 (including `diff.txt` and the reviewer files under `reviews/`).

```bash
${CLAUDE_PLUGIN_ROOT}/scripts/rm-tmp.sh {tmp_dir}
```
