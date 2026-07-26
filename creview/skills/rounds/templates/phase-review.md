---
name: phase-review
description: Prompt for the phase leader sub-agent that runs /creview:start as its leader in /creview:rounds Step 2.1
template_id: 3e7b1c9d-6a24-4f85-b1d7-8c2e5a9f3b64
---

Run the `creview:start` skill as its review leader for one round of `/creview:rounds`. Read `{{plugin_root}}/rules/sub-agent.md` and observe the common prohibitions.

Input:

- Base branch: `{{base}}`
- This round's review document path: `{{document_path}}`
- Document language: `{{language}}`
- Adversarial mode: `{{adversarial}}`

What to do:

1. Invoke the `creview:start` skill with the arguments `--base {{base}} --output {{document_path}}`, appending `--adversarial` when `{{adversarial}}` is on, then act as its review leader through its Steps 1-4, including deleting the working directory. Leave the review target unspecified so the skill uses its default (the commits unique to the current branch).
2. Add the following to the "Round-specific overrides" section of every sub-agent launch prompt you issue:
   - Do not pass any past round's review document to the reviewers, and do not deduplicate against a past round.
   - Never include in a reviewer's prompt: past round finding counts, count trends, wording such as "appears to be converging", past round finding ids (`C-1`, `M-1`, etc.), or Fixed / Won't Fix statistics.
   - Aggregator sub-agent: write the review document in `{{language}}`.

Do not omit parts of a reviewer prompt template, add instructions to it to adjust the finding count, or add findings other than those the reviewers submit.

Return value: `{doc_path, findings_total, severity_counts: {critical, major, minor, info}, template_id}`. Include `template_id` exactly as Read from this template's frontmatter.
