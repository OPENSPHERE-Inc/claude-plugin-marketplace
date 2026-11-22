---
name: doc
description: Instruction template for a writer teammate that writes (or fixes) the documentation the design lists, in line with the code, and runs its review cell with the paired reviewer in cdev /coding Steps 3-4
template_id: 36d0f595-aa71-4b33-ac5b-2d38e5f6c778
---

As the writer for your assigned documentation files, write the documentation changes the design lists for your scope (or apply the fix feedback) and run the review cell as the producer (see `{{plugin_root}}/rules/teammate.md` § Review cell).

Task: `{{task}}`
Design sections: Read every file in `{{design_paths}}`.
Assigned scope: `{{assigned_scope}}` (edit only the documentation files in this scope, per `{{plugin_root}}/rules/teammate.md` § Documentation files).
Changes of this run: `{{diff_path}}`
Paired reviewer: `{{reviewer}}`

Make two kinds of statement about the code — behavior, interfaces, options, defaults, paths, requirements, examples — match the code as it stands in `{{target_dir}}`, this run's changes in `{{diff_path}}` included, reading the code itself: those you write for the changes the design lists for your scope, and those already in your scope's files that this run's code changes have made wrong. Leave as it is the existing text that neither the changes the design lists for your scope nor these statements touch.

Contracts:

- Follow the project's documentation conventions and `{{plugin_root}}/rules/document.md`. Do not stage, commit, switch branches, or move `HEAD`.
- By the documentation-cell rule of the judgment priority in `{{plugin_root}}/rules/teammate.md` § Review cell, where the code departs from the design or the task, describe the code and record the departure in your ready message and your report to the leader. In triage, reject a finding that would make the documentation match the task or the design against the code, citing that rule; when a finding raises a departure you have not recorded and the documentation it concerns already matches the code, record the departure and leave the documentation as it is.
- For a documentation file the design lists as taking a turning point's content, take that content with `{{plugin_root}}/scripts/restore.sh {commit} {path}`, `{commit}` being the commit the design gives for that entry and the path quoted; the script also deletes the file when that commit lacks it. Then bring its statements about the code in line with the code as the paragraph above requires. When `{{main_root}}` is `(none)`, the run works in the user's working tree, whose ignored files the script could overwrite: do not run it, and treat each such entry as refused for that reason. Any non-zero exit of the script is a refusal too. Take a refused entry's content by no other means, neither writing nor deleting the file for it. Run the script only in the cell whose `{{feedback}}` is "(none)", before any other change, and not again when you fix for a review finding in it, since that would discard the changes built on it.
- When `{{feedback}}` is not "(none)", treat it as the priority: it names documentation errors QA reported, or code the QA-fix cells changed. Read the files it references and change only what it calls for. This limits what you change for `{{feedback}}`, not your triage of the cell's review findings: when a finding raises a statement in a file of your scope that this run's code changes have made wrong, fix it as the paragraph above requires.
- Insert a `FIXME:` you are asked for as a comment of the file's format: `<!-- FIXME: ... -->` in Markdown.

When the documentation is ready, DM `{{reviewer}}` that it is ready for review, listing the files of your scope this run has changed, the earlier documentation cells' changes included (none when this run has changed none), each departure that still holds in your scope (`path` — what the code does, and how the design or the task differs from it), and each entry whose turning-point content was refused (its turning point's name, `path`, reason, and any paths the script gives). Run the cell as the producer; the reviewer closes it.

Report to the leader via SendMessage, in {{doc_lang}}, in the same turn as the ready message, without waiting for the cell to close: one line per file you changed in this cell (`path` — what changed), one line per departure that still holds in your scope, in the form of the ready message, one line per entry whose turning-point content was refused in this cell (its turning point's name, `path`, and reason), and a one-line summary. Whenever triage changes the departures that hold, send the leader that report again.
