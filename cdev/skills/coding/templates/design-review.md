---
name: design-review
description: Instruction template for a reviewer teammate that reviews a design section and resolves the review cell with the paired architect in cdev /coding Step 2 (in-loop quality gate)
template_id: 448ee08a-0284-4066-9de9-9f82e9078914
---

Review the design produced by `{{producer}}` and resolve the cell as the reviewer (see `{{plugin_root}}/rules/teammate.md` § Review cell), up to `{{review_rounds}}` rounds.

Task: `{{task}}`
Design section: `{{design_path}}`
Producer: `{{producer}}` | Cell task: `{{cell_task}}`

Judge the design for correctness and completeness against the task, feasibility, missing edge cases / error handling, interface and data-shape soundness, testability, and risk to existing code. Judge also whether its list of the files to add or change names every file the implementation needs, tests, documentation, and the definitions of the agents, skills, or commands that run a script the design adds included: the team re-formation assigns coders only to the files in that list. A directory counts as listing the files whose names the design leaves to the coder when one coder could hold them all: all AI-facing prompt files or none, of one domain, and a test going to the same coder as the file it tests. Read `{{plugin_root}}/rules/review.md` and follow it. Read `{{plugin_root}}/rules/divergence.md` and, following its § reviewer, detect divergence patterns. Restrict tool use to Read / Glob / Grep / Bash(grep/ls/find); do not edit anything.

Severity labels: Critical (design is wrong or will not meet the task) / Major (significant gap or risk) / Minor (improvement) / Info (note); actionable = Critical / Major.

Run the cell protocol on cell `{{cell_task}}`: DM each actionable finding to `{{producer}}` as the section / area plus the issue and the recommended fix direction (prose in {{doc_lang}}, severity labels as-is), and report the severity counts to the leader as one line (`Critical N / Major N / Minor N / Info N`). When you close the cell, resolved or at the round cap, also state in that report to the leader whether the design as closed creates or edits an AI-facing prompt file (per `{{plugin_root}}/rules/prompt.md`).
