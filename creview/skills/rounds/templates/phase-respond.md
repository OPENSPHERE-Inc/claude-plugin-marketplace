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

1. Invoke the `creview:respond` skill with the argument `{{document_path}}`, appending `--commit` when `{{commit_flag}}` is on and `--adr` when `{{adr_flag}}` is on. Then act as its respond leader through its Steps 1-6, including the format / build / test verification ⇄ build-fix re-execution loop, the commit step, and the compile step.
2. Add each entry in `{{overrides}}` to the "Round-specific overrides" section of the launch prompt of the sub-agent it names, or of every sub-agent when it names none.

Return value: `{fix_count, fixed_count, code_changed, workflow_warning, summary_line, template_id}`. `workflow_warning` is the value from the last format / build / test verification, and is null when the workflow was resolved. Include `template_id` exactly as Read from this template's frontmatter.
