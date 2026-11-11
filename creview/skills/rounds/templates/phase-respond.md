---
name: phase-respond
description: Prompt for the phase leader sub-agent that runs /creview:respond as its leader in /creview:rounds Step 2.3 and in the Step 2.5 feedback loop
template_id: 8b5e3d7a-4c16-4a92-a7f3-2d9c6b1e8f47
---

Run the `creview:respond` skill as its respond leader for one round of `/creview:rounds`. Read `{{plugin_root}}/rules/sub-agent.md` and observe the common prohibitions.

Input:

- Review document: `{{document_path}}` (triage / estimate are already persisted in it)
- `--commit`: `{{commit_flag}}`
- `--adr`: `{{adr_flag}}`
- Round-specific overrides: `{{overrides}}`

What to do:

1. Invoke the `creview:respond` skill with the argument `{{document_path}}`, appending `--commit` when `{{commit_flag}}` is on and `--adr` when `{{adr_flag}}` is on. Then act as its respond leader through its Steps 1-6, including the format / build / test verification and interpretation test ⇄ fix loop, the commit step, and the compile step.
2. Add each entry in `{{overrides}}` to the "Round-specific overrides" section of the launch prompt of the sub-agent it names, or of every sub-agent when it names none.
3. When the skill stops on an error, as `error` below defines it, after its Step 4 loop has exited, whatever the loop's result, and before Step 6's compile has succeeded, run that compile before `{tmp_dir}` is removed, unless the compile is what failed: `python3 {{plugin_root}}/skills/respond/scripts/compile-review.py {tmp_dir} {{document_path}}`, with `{tmp_dir}` the skill's working directory. When that compile, or Step 6's own after the Step 4 loop has exited, fails, include in `error` that the fixes went through Step 4 but their status could not be written to the review document.

Return value: `{fix_count, fixed_count, code_changed, workflow_warning, prompt_warning, summary_line, error, template_id}`. `workflow_warning` is the value respond retained in its Step 4: non-null when the format / build procedure could not be resolved or when the build / test verification did not complete for an environmental cause, null otherwise. `prompt_warning` is the value respond held after its Step 4: non-null when an AI-facing prompt file was left failing the interpretation test or untested, null otherwise. `error` is null when the skill ran through its Steps 1-6, warnings included: a non-null `workflow_warning` or `prompt_warning`, or a Step 4 loop that exited on its last attempt with the build / test still failing, is no error. When the skill aborted or terminated, or stopped at a step that failed with no way on, such as a script exiting non-zero or a sub-agent's `template_id` mismatching twice in a row, `error` is the error the skill showed, or, when it showed none, a message you write naming the step it stopped at and what failed there: a command's exit code and error output, or the mismatched `template_id`. On an error, report `fix_count` and `fixed_count` as 0, `code_changed` as false, and `workflow_warning`, `prompt_warning`, and `summary_line` as null. Include `template_id` exactly as Read from this template's frontmatter.
