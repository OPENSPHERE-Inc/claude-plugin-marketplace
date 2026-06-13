---
name: code
description: Instruction template for a coder teammate implementing the design or applying fix feedback in cdev /coding Steps 4-6
template_id: 278bf9bd-53e2-4695-ad40-3fb91374519a
---

As the coder for your assigned files, implement the design (or apply the fix feedback) within your scope.

Task: `{{task}}`
Design sections: Read every file in `{{design_paths}}`.
Assigned scope: `{{assigned_scope}}` (edit only files in this scope).
Test-driven: `{{tdd}}` (true when the project has a test suite).

Steps:

1. Read the design sections and the existing code in your scope.
2. Resolve any feedback as the priority:
   - `{{feedback}}` (when not "(none)") names a QA build/test failure — Read the referenced result / log and fix the error.
   - Reviewer findings sent to you by message — resolve the Critical / Major ones in your scope.
3. Implement or modify the source to satisfy the design and any feedback, following the project's conventions and `{{plugin_root}}/rules/comment.md` for comments. When `{{tdd}}` is true, work test-first: write or extend the tests that capture the intended behavior and confirm they fail, then implement until they pass, then refactor with the tests green. Do not weaken or delete existing tests to force a pass.
4. Self-review: confirm the code matches the design, the feedback is resolved, and no obvious new issue is introduced.

Report to the leader (via SendMessage): `{files_changed: ["path:summary", ...], has_comments: <bool>, summary}`. `has_comments` is true when you added or modified any code comment. Write `summary` in {{doc_lang}}. Mark the task done via TaskUpdate.
