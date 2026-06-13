---
name: design
description: Instruction template for an architect teammate producing or revising a design-document section in cdev /coding Step 2-3
template_id: 740fa1cf-fa38-40a0-85d0-4c9a99eab5de
---

As the architect for your assigned area, produce (or revise) a design for the task and Write it to `{{output_path}}`.

Task: `{{task}}`
Assigned scope: `{{assigned_scope}}`

Steps:

1. Read the existing code in your scope (Glob / Grep / Read) to ground the design in what is already there. Do not edit source.
2. If this is a revision task (a reviewer sent you findings by message), revise your section to resolve every Critical / Major finding before writing.
3. Write the design section to `{{output_path}}` (markdown) covering: the approach, the files / modules to add or change, key interfaces and data shapes, edge cases and error handling, and the impact on tests / build. Follow `{{plugin_root}}/rules/document.md`. Make it concrete enough that a coder implements from it without further questions; keep code to short signatures, not full listings.

Report to the leader (via SendMessage): `{path: "{{output_path}}", summary}` (`summary` 1-2 sentences in {{doc_lang}}). Mark the task done via TaskUpdate.
