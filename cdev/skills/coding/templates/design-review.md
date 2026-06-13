---
name: design-review
description: Instruction template for a reviewer teammate reviewing the design document in cdev /coding Step 3 (in-loop quality gate)
template_id: 448ee08a-0284-4066-9de9-9f82e9078914
---

Review the design for the task as an in-loop quality gate.

Task: `{{task}}`
Design sections: Read every file in `{{design_paths}}`.
Scope map (architect → scope): `{{scope_map}}`

Rules:

- Restrict tool use to Read / Glob / Grep / Bash(grep/ls/find). Read the existing code the design references when needed to judge feasibility. Do not edit anything.
- Judge the design for correctness and completeness against the task, feasibility, missing edge cases / error handling, interface and data-shape soundness, testability, and risk to existing code. Read `{{plugin_root}}/rules/review.md` and follow it.
- Severity labels: Critical (design is wrong or will not meet the task) / Major (significant gap or risk) / Minor (improvement) / Info (note).

Routing and reporting:

- For each actionable finding (Critical / Major), SendMessage the owning `architect-{slug}` (resolve the owner from `{{scope_map}}` by the design section / area the finding concerns). State the section or area, the issue, and the recommended fix direction, in {{doc_lang}}. Keep severity labels as-is.
- Report to the leader (via SendMessage): `{critical, major, minor, info}` (the count of findings at each severity; no bodies). Mark the task done via TaskUpdate.
