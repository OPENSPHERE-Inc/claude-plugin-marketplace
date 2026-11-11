---
name: prompt-review
description: Prompt for prompt-sensei to self-check, fix, and compress what the fix sub-agents created or changed in AI-facing prompt files against the prompt discipline, in /creview:respond Step 3
template_id: 6be7d388-2c9d-41f1-a349-a47407e157f4
---

The target range is what the fixes of this run created or changed in AI-facing prompt files. Bring it to a state that violates no item of `{{plugin_root}}/rules/prompt.md` and carries no verbosity, without changing the actions the prompts ask of the agent and without undoing what a fix established for its finding, including a FIXME an 🚧 Alternative estimate directed. Leave the existing text outside the target range untouched, and do not count an existing violation outside it as remaining. Read `{{plugin_root}}/rules/sub-agent.md` and observe the common prohibitions.

Input:

- Target files: the files in the `files` arrays of `{{tmp_dir}}/statuses/*.jsonl` that still exist and are AI-facing prompt files as `prompt.md` defines them. `{{diff_path}}` is `fetch-diff.sh` output against HEAD after the fixes, and `{{baseline_path}}` the same output taken before them. A file `{{diff_path}}` shows as added or as the destination of a rename or copy, or lists under Untracked Files, and `{{baseline_path}}` does not show, counts as created, and its whole content is the target range. For any other file `{{diff_path}}` or `{{baseline_path}}` shows, the target range is where the two differ: what `{{diff_path}}` shows beyond what `{{baseline_path}}` shows (in a hunk both show, the lines that differ) and, for each hunk only `{{baseline_path}}` shows (a change from before the fixes that they reverted), the lines of the current file its context and `-` lines correspond to, or, for a hunk with neither, the lines on either side of where its `+` lines stood. For a file neither shows, such as a gitignored one, the target range is the parts the `description` of each fix listing it in `{{tmp_dir}}/statuses/*.jsonl` points to.
- Review document `{{document_path}}`: the findings each fix addressed (description, location, Triage / Estimate metadata), for the intent a fix or a compression must keep.

Steps:

1. Read the rule and each target file, and list every violation in the target range as `path:line`, including those inside embedded sub-agent prompts. In a skill (its SKILL.md and the templates it has an agent Read), list each Markdown output template embedded in a code block as a violation of its embedding; do not judge the template's content against the rule.
2. Fix the violations with Edit, then re-check that the fixes introduced no new ones. Repeat up to 2 times; what remains after the second pass is remaining. Fix an embedded Markdown output template by moving it to its own file under the skill's `templates/`, the only kind of file you may add.
3. Compress the target range, embedded sub-agent prompts included; the rule still applies. Remove with Edit:
   - Polite forms such as "please ..." → use the imperative.
   - The same rule repeated in multiple places → consolidate or replace with a reference.
   - Statements the AI would naturally infer (e.g. per-edge-case instructions for self-evident cases).
   - "A is the case, therefore not B" wording → keep only the first half.
   - Unnecessarily verbose code examples or templates → trim to the minimum skeleton.

   Decision criterion: if removing the text does not change the action the AI should take, remove it. Keep judgment WHY (constraints, premises, anti-misunderstanding notes).

Edit only the target files and the template files step 2 adds.

Return value: `{prompt_files: [{path, created}], violations_detected, violations_fixed, compressed_count, added_files: [path], remaining: [{location, rule}], template_id}`. Paths are repository-relative.

- `prompt_files`: the target files, `created` true for a file Input counts as created. With no target file, it is `[]`, every count is 0, and every array is empty.
- `compressed_count`: the number of target files compression changed.
- `added_files`: the template files step 2 added.
- `remaining`: each violation left after step 2, `location` as `path:line` and `rule` as the `prompt.md` item it breaks.

Include `template_id` (Read from this template's frontmatter) verbatim in the return value.
