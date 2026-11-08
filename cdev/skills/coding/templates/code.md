---
name: code
description: Instruction template for a coder teammate that implements (or fixes) the design and runs its review cell with the paired reviewer in cdev /coding Steps 3-4
template_id: 278bf9bd-53e2-4695-ad40-3fb91374519a
---

As the coder for your assigned files, implement the design (or apply the fix feedback) and run the review cell as the producer (see `{{plugin_root}}/rules/teammate.md` § Review cell).

Task: `{{task}}`
Design sections: Read every file in `{{design_paths}}`.
Assigned scope: `{{assigned_scope}}` (edit only files in this scope and the template files the prompt review of step 5 adds by externalizing from them).
Test-driven: `{{tdd}}` (true when the project has a test suite).
Paired reviewer: `{{reviewer}}`
Comment reviewer: `{{comment_reviewer}}`
Prompt reviewer: `{{prompt_reviewer}}`

Steps:

1. Read the design sections and the existing code in your scope.
2. If `{{feedback}}` is not "(none)", treat it as the priority: it names a QA failure — a build / test error, or the unclear items of a prompt interpretation test — Read the files it references and fix what they report.
3. Implement or modify the source to satisfy the design and any feedback, following the project's conventions, `{{plugin_root}}/rules/comment.md` for comments, and `{{plugin_root}}/rules/prompt.md` for AI-facing prompt files. When `{{tdd}}` is true, work test-first on everything but AI-facing prompt files: write or extend the tests that capture the intended behavior and confirm they fail, then implement until they pass, then refactor with the tests green. Do not weaken or delete existing tests to force a pass.
4. If you added or modified any code comment, DM `{{comment_reviewer}}` naming `{{plugin_root}}/skills/coding/templates/comment-review.md` with `changed_scope = {{assigned_scope}}` and `design_paths = {{design_paths}}`; it fixes comment violations and reports the count back to you.
5. If you created or edited an AI-facing prompt file (per `{{plugin_root}}/rules/prompt.md`) and `{{prompt_reviewer}}` is not "(none)", then, after any comment review of step 4 has reported back, DM `{{prompt_reviewer}}` naming `{{plugin_root}}/skills/coding/templates/prompt-review.md` with `changed_files = {the prompt files you changed, marking each one you created in this run as created and each one you moved or renamed as moved with the parts you changed, and giving the parts you changed for an existing file git does not track}`, `design_paths = {{design_paths}}`, and `feedback = {{feedback}}`; it self-checks, fixes, and compresses them and reports back to you.
6. DM `{{reviewer}}` that your change is ready for review, listing the files you changed, any template file the prompt review added, and each violation the prompt review left remaining, and run the cell as the producer; the reviewer closes it.

Report to the leader via SendMessage, in {{doc_lang}}: one line per changed file, any template file the prompt review added included (`path` — what changed), whether the change added or modified comments, the prompt review's counts (violations detected / fixed / remaining, files compressed) when you requested one, and a one-line summary.
