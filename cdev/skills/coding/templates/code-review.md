---
name: code-review
description: Instruction template for a reviewer teammate reviewing the produced code in cdev /coding Step 6 (in-loop quality gate)
template_id: 4abf814d-2e3e-4bec-8ff8-45c9a176b01f
---

Read `{{diff_path}}` and review the code produced for the task as an in-loop quality gate.

Task: `{{task}}`
Design sections (intended behavior): Read every file in `{{design_paths}}`.
Scope map (coder → scope): `{{scope_map}}`

Rules:

- Restrict tool use to Read / Glob / Grep / Bash(grep/ls/find). Use Read on the changed files to see surrounding code; re-running git is unnecessary (the diff is in `{{diff_path}}`).
- Judge the code for correctness against the design and task, bugs, missing edge cases / error handling, security, performance, and maintainability. Read `{{plugin_root}}/rules/review.md` and follow it.
- Severity labels: Critical (fatal, must fix) / Major (should fix) / Minor (caution) / Info (note).

Routing and reporting:

- For each actionable finding (Critical / Major), SendMessage the owning `coder-{slug}` (resolve the owner from `{{scope_map}}` by the file the finding concerns). State `file:line`, the issue, and the recommended fix direction, in {{doc_lang}}. `line` is the real line number obtained by Read-ing the target file, not a diff position. Keep `file:line` and severity labels as-is.
- Report to the leader (via SendMessage): `{critical, major, minor, info}` (the count of findings at each severity; no bodies). Mark the task done via TaskUpdate.
