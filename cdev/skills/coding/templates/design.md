---
name: design
description: Instruction template for an architect teammate that produces a design section and runs its review cell with the paired reviewer in cdev /coding Step 2
template_id: 740fa1cf-fa38-40a0-85d0-4c9a99eab5de
---

As the architect for your assigned area, produce a design and run the review cell as the producer (see `{{plugin_root}}/rules/teammate.md` § Review cell).

Task: `{{task}}`
Assigned scope: `{{assigned_scope}}`
Paired reviewer: `{{reviewer}}`

Steps:

1. Read the existing code in your scope (Glob / Grep / Read) to ground the design. Do not edit source.
2. Write the design section to `{{output_path}}` (markdown): the approach, the files / modules to add or change, key interfaces and data shapes, edge cases and error handling, and the impact on tests / build. Follow `{{plugin_root}}/rules/document.md`. Keep code to short signatures, not full listings.
3. DM `{{reviewer}}` that the design at `{{output_path}}` is ready for review, and run the cell as the producer (fixes go into `{{output_path}}`; the reviewer closes the cell).

Report to the leader via SendMessage: the path `{{output_path}}` and 1-2 sentences on what the design covers (in {{doc_lang}}).
