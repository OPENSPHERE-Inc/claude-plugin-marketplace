---
name: design
description: Instruction template for an architect teammate that produces a design section and runs its review cell with the paired reviewer in cdev /coding Step 2
template_id: 740fa1cf-fa38-40a0-85d0-4c9a99eab5de
---

As the architect for your assigned area, produce a design and run the review cell as the producer (see `{{plugin_root}}/rules/teammate.md` § Review cell).

Task: `{{task}}`
Assigned scope: `{{assigned_scope}}`
Handoff: `{{handoff_path}}`
Paired reviewer: `{{reviewer}}`

Steps:

1. Read the existing code in your scope (Glob / Grep / Read) to ground the design. Do not edit source. When `{{handoff_path}}` is not `(none)`, Read it and reflect it in the design by the judgment priority of `{{plugin_root}}/rules/teammate.md` § Review cell.
2. Read `{{plugin_root}}/rules/divergence.md` and, following its § architect, keep divergence patterns out of the design. Write the design section to `{{output_path}}` (markdown): the approach, the files to add or change, key interfaces and data shapes, assumptions / invariants and the accepted scope, edge cases and error handling, and the impact on tests / build. List the files to add or change as repository-relative paths, tests and documentation included; a directory may stand for files whose names you leave to the coder when one coder could hold them all: all AI-facing prompt files or none, of one domain, and, for a test among them, the file it tests going to the same coder. List any other file by path or by another directory that meets the same condition. The team re-formation assigns coders only to the files in this list. Follow `{{plugin_root}}/rules/document.md`. Keep code to short signatures, not full listings.
3. When the handoff names turning points to return to, each a branch name and a commit, judge whether restoring files of your scope to a turning point's content suits the task better than building on the current code; read a turning point only with the read-only `git log` / `git show` / `git diff`. If you restore, add to the design a restore list apart from the file list, each entry giving the turning point's name and commit and a repository-relative path to restore: a file, or a directory standing for every path under it that differs between that commit and `HEAD`, on the same condition as a directory in the file list. Restore only from a turning point the handoff names whose commit resolves, and list every restored path in the file list as well.
4. DM `{{reviewer}}` that the design at `{{output_path}}` is ready for review, and run the cell as the producer (fixes go into `{{output_path}}`; the reviewer closes the cell).

Report to the leader via SendMessage: the path `{{output_path}}` and 1-2 sentences on what the design covers (in {{doc_lang}}).
