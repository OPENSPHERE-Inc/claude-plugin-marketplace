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
2. `{{main_root}}` is the main working tree's root when the run works in a worktree it created, and `(none)` when the run works in the user's working tree, whose ignored files a restore could overwrite. When the handoff names turning points to return to, each a branch name and a commit, and `{{main_root}}` is not `(none)`, judge whether restoring files of your scope to a turning point's content suits the task better than building on the current code; read a turning point only with the read-only `git log` / `git show` / `git diff`. When `{{main_root}}` is `(none)`, restore nothing, and design on the current code. If you restore, draw up a restore list, each entry giving the turning point's name and commit; a repository-relative path to restore, which is a file or a directory standing for every path under it that differs between that commit and `HEAD`, on the same condition as a directory in the file list (step 3); why restoring it suits the task better; and the changes made since that commit that the restore discards. No entry's path may be another entry's path or lie under it: restore.sh refuses an entry under which an earlier restore changed a tracked file. To restore a directory from turning point A and a part of it from turning point B, give that part an entry from B, and list entries from A for the rest of the directory, each a file or a subdirectory on the condition above that does not contain that part. Together, the entries from A must cover every path outside that part that the directory would stand for as an entry from A, including a path only in `HEAD`, which the restore deletes. Count a path only in A's commit among those paths as well: `git diff` pairs a rename by default and names only one of its two paths, so list them with `git diff --no-renames --name-only {A's commit} HEAD -- {directory}`. Restore only from a turning point the handoff names whose commit resolves.
3. Read `{{plugin_root}}/rules/divergence.md` and, following its § architect, keep divergence patterns out of the design. Write the design section to `{{output_path}}` (markdown): the approach, the files to add or change, key interfaces and data shapes, assumptions / invariants and the accepted scope, edge cases and error handling, the impact on tests / build, and, when you restore, the restore list of step 2 apart from the file list. List the files to add or change as repository-relative paths, tests and documentation included; a directory may stand for files whose names you leave to the coder when one coder could hold them all: all AI-facing prompt files or none, of one domain, and, for a test among them, the file it tests going to the same coder. List any other file by path or by another directory that meets the same condition, and every restored path as well. The team re-formation assigns coders only to the files in this list. Follow `{{plugin_root}}/rules/document.md`. Keep code to short signatures, not full listings.
4. DM `{{reviewer}}` that the design at `{{output_path}}` is ready for review, and run the cell as the producer (fixes go into `{{output_path}}`; the reviewer closes the cell).

Report to the leader via SendMessage: the path `{{output_path}}` and 1-2 sentences on what the design covers (in {{doc_lang}}).
