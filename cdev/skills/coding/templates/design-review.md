---
name: design-review
description: Instruction template for a reviewer teammate that reviews a design section and resolves the review cell with the paired architect in cdev /coding Step 2 (in-loop quality gate)
template_id: 448ee08a-0284-4066-9de9-9f82e9078914
---

Review the design produced by `{{producer}}` and resolve the cell as the reviewer (see `{{plugin_root}}/rules/teammate.md` § Review cell), up to `{{review_rounds}}` rounds.

Task: `{{task}}`
Design section: `{{design_path}}`
Producer's agentId: `{{producer}}` | Cell task: `{{cell_task}}`

Judge the design for correctness and completeness against the task, feasibility, missing edge cases / error handling, interface and data-shape soundness, testability, and risk to existing code. Read `{{plugin_root}}/rules/review.md` and follow it. Restrict tool use to Read / Glob / Grep / Bash(grep/ls/find); do not edit anything.

Severity labels: Critical (design is wrong or will not meet the task) / Major (significant gap or risk) / Minor (improvement) / Info (note); actionable = Critical / Major.

Per the cell protocol: DM actionable findings (the section / area, the issue, the recommended fix direction; in {{doc_lang}}, severity labels as-is) to `{{producer}}`; report severity counts `{critical, major, minor, info}` to the leader; resolve after the producer triages; report cell `{{cell_task}}` resolved to the leader via `SendMessage(to: "main")`; and escalate a rejected `Critical` you still disagree with.
