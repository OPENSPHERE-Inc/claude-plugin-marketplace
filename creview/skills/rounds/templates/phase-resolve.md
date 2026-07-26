---
name: phase-resolve
description: Prompt for the phase leader sub-agent that runs /creview:resolve as its leader in /creview:rounds Step 2.4 and in the Step 2.5 feedback loop
template_id: 2f9c6a1e-7b53-4d84-8e2b-5a1f9d3c7b26
---

Run the `creview:resolve` skill as its verification leader for one round of `/creview:rounds`. Read `{{plugin_root}}/rules/sub-agent.md` and observe the common prohibitions.

Input:

- Review document: `{{document_path}}`
- Base branch: `{{base}}`
- Round-specific overrides: `{{overrides}}`

What to do:

1. Invoke the `creview:resolve` skill with the arguments `{{document_path}} --base {{base}}`, then act as its verification leader through its Steps 1-3, including the compile step.
2. Add each entry in `{{overrides}}` to the "Round-specific overrides" section of the launch prompt of the sub-agent it names, or of every sub-agent when it names none.

Return value: `{summary_path, summary_line, resolved_count, feedback_count, unresolved_count, template_id}`. Include `template_id` exactly as Read from this template's frontmatter.
