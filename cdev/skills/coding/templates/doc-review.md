---
name: doc-review
description: Instruction template for a reviewer teammate that reviews a writer's documentation change, its consistency with the code included, and resolves the review cell with the paired writer in cdev /coding Steps 3-4 (in-loop quality gate)
template_id: 9771b927-1003-44a9-be83-dd33ddfa5d99
---

Review the documentation produced by `{{producer}}` and resolve the cell as the reviewer (see `{{plugin_root}}/rules/teammate.md` § Review cell), up to `{{review_rounds}}` rounds.

Task: `{{task}}`
Design sections (intended changes): Read every file in `{{design_paths}}`.
Changes of this run: `{{diff_path}}`
Producer: `{{producer}}` | Cell task: `{{cell_task}}`
Producer's scope: `{{assigned_scope}}` (a scope holds a file when it names the file or a directory above it)

When the producer signals ready, take the departures its ready message records, Read the files it lists there, and check what this run changed in each with the read-only `git diff HEAD -- {path}`, a file `HEAD` lacks counting as changed whole. Glob / Grep / Read the other documentation files of the producer's scope (per `{{plugin_root}}/rules/teammate.md` § Documentation files) as far as the judgments below need. Judge:

- whether what the changed files say about the code — behavior, interfaces, options, defaults, paths, requirements, examples — matches the code as it stands in `{{target_dir}}`, this run's changes in `{{diff_path}}` included, read from the code itself;
- whether this run's code changes have made wrong a statement the producer left unchanged in a documentation file of its scope, changed or not;
- whether the documentation changes the design asks of the producer's scope are all there;
- whether the changed files contradict one another;
- whether they follow the project's documentation conventions and `{{plugin_root}}/rules/document.md`;
- whether each departure the producer records holds: the code does what it says, and the design or the task differs from it there.

By the documentation-cell rule of the judgment priority in `{{plugin_root}}/rules/teammate.md` § Review cell, a statement that follows code departing from the design or the task, or a documentation change the design asks for that the producer leaves out because the code lacks what it would describe, is no finding when the producer records the departure; otherwise raise a Major whose fix direction is to record the departure, never to change the documentation. When the producer's ready message lists as refused a documentation change that takes a turning point's content, the content left untaken does not count as a missing documentation change the design asks for, since the producer may take it by no other means; judge that file on every other point above. A statement this run neither changed nor made wrong is out of scope: Info at most. Restrict tool use to Read / Glob / Grep / Bash(grep/ls/find) and the read-only `git log` / `git show` / `git diff`, to read this run's changes to the producer's files, or a file's content at the commit the design sections give for a documentation change that takes a turning point's content; do not edit anything.

Severity labels: Critical (a statement a reader relies on contradicts the code) / Major (a documentation change the design asks for is missing, a statement follows code that departs from the design or the task with the departure unrecorded, a recorded departure does not hold (fix direction: correct or withdraw the record), a statement leads the reader to a wrong use, or notation breaks the rendering) / Minor (wording or presentation that does not mislead) / Info (note); actionable = Critical / Major.

Run the cell protocol on cell `{{cell_task}}`: DM each actionable finding to `{{producer}}` as `file:line` plus the issue and the recommended fix direction (`line` is the real line number from Read-ing the file; prose in {{doc_lang}}, severity labels as-is), and report the severity counts to the leader as one line (`Critical N / Major N / Minor N / Info N`).
