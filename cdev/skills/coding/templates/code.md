---
name: code
description: Instruction template for a coder teammate that implements (or fixes) the design and runs its review cell with the paired reviewer in cdev /coding Steps 3-4
template_id: 278bf9bd-53e2-4695-ad40-3fb91374519a
---

As the coder for your assigned files, implement the design (or apply the fix feedback) and run the review cell as the producer (see `{{plugin_root}}/rules/teammate.md` § Review cell).

Task: `{{task}}`
Design sections: Read every file in `{{design_paths}}`.
Assigned scope: `{{assigned_scope}}` (edit only files in this scope).
Test-driven: `{{tdd}}` (true when the project has a test suite).
Paired reviewer's agentId: `{{reviewer}}`
comment-sensei's agentId: `{{comment_reviewer}}`

Steps:

1. Read the design sections and the existing code in your scope.
2. If `{{feedback}}` is not "(none)", treat it as the priority: it names a QA build/test failure — Read the referenced result / log and fix the error.
3. Implement or modify the source to satisfy the design and any feedback, following the project's conventions and `{{plugin_root}}/rules/comment.md` for comments. When `{{tdd}}` is true, work test-first: write or extend the tests that capture the intended behavior and confirm they fail, then implement until they pass, then refactor with the tests green. Do not weaken or delete existing tests to force a pass.
4. If you added or modified any code comment, DM comment-sensei (agentId `{{comment_reviewer}}`) naming `{{plugin_root}}/skills/coding/templates/comment-review.md` with `changed_scope = {{assigned_scope}}` and `design_paths = {{design_paths}}`; it fixes comment violations and reports the count back to you.
5. DM `{{reviewer}}` that your change is ready for review, listing the files you changed. Run the cell: triage each finding the reviewer sends — fix it in your scope, or reject it with a one-line reason — then signal ready for re-review. The reviewer resolves and closes the cell.

Report to the leader (via SendMessage) as a JSON string: `{files_changed: ["path:summary", ...], has_comments: <bool>, summary}` (`summary` in {{doc_lang}}).
