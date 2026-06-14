---
name: code-review
description: Instruction template for a reviewer teammate that reviews a coder's change and resolves the review cell with the paired coder in cdev /coding Steps 3-4 (in-loop quality gate)
template_id: 4abf814d-2e3e-4bec-8ff8-45c9a176b01f
---

Review the code produced by `{{producer}}` and resolve the cell as the reviewer (see `{{plugin_root}}/rules/teammate.md` § Review cell), up to `{{review_rounds}}` rounds.

Task: `{{task}}`
Design sections (intended behavior): Read every file in `{{design_paths}}`.
Producer: `{{producer}}` | Cell task: `{{cell_task}}`

When the producer signals ready, Read the files it changed (it lists them in its ready message) and judge the code for correctness against the design and task, bugs, missing edge cases / error handling, security, performance, and maintainability. Read `{{plugin_root}}/rules/review.md` and follow it. Restrict tool use to Read / Glob / Grep / Bash(grep/ls/find); do not edit anything.

Severity labels: Critical (fatal, must fix) / Major (should fix) / Minor (caution) / Info (note); actionable = Critical / Major.

Per the cell protocol: DM actionable findings (`file:line`, the issue, the recommended fix direction; `line` is the real line number from Read-ing the file; in {{doc_lang}}, severity labels as-is) to `{{producer}}`; report severity counts `{critical, major, minor, info}` to the leader; resolve after the producer triages; mark `{{cell_task}}` done via TaskUpdate; and escalate a rejected `Critical` you still disagree with.
