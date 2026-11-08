---
name: prompt-review
description: Prompt for prompt-sensei to self-check, fix, and compress the AI-facing prompt files in a coder's change against the prompt discipline, engaged by the coder within its code cell in cdev /coding Steps 3-4
template_id: 32593105-187d-4d84-874e-dce7958761f8
---

Bring what the coder created or changed in this run in its AI-facing prompt files to a state that violates no item of `{{plugin_root}}/rules/prompt.md` and carries no verbosity, without changing the actions they ask of the agent. That target range is the whole file for a file the request marks as created in this run, and when the design sections cover the whole file (e.g. a task that asks to compress or rewrite it). For any other file, it is the parts the request names as changed, or, when it names none, the hunks of `git diff HEAD -- {path}`, in either case plus the text they depend on and the text that depends on them. A file with neither parts named as changed nor hunks has no target range.

Input:

- Changed prompt files: `{{changed_files}}`. A file created in this run is marked as created, and an edited file git does not track, and one moved or renamed, comes with the parts changed. Edit only these; the only files you may add are the template files that externalizing embedded Markdown output templates calls for (Write them under the skill's `templates/`).
- Design sections: Read every file in `{{design_paths}}` for the behavior the prompts specify; a fix or a compression must not change it.
- Feedback the coder applied: `{{feedback}}`. When it is not "(none)", it names the unclear items of a prompt interpretation test or another QA failure; keep what the coder wrote to resolve them.

Steps:

1. Read the rule and each file, and list every violation in the target range as `path:line`, including those inside embedded sub-agent prompts. In a skill (its SKILL.md and the templates it has an agent Read), list each Markdown output template embedded in a code block as a violation of its embedding; do not judge the template's content against the rule. Leave an existing violation outside the target range unedited, and do not list it as remaining.
2. Fix the violations with Edit, then re-check that the fixes introduced no new ones. Repeat up to 2 times; what remains after the second pass is reported as remaining.
3. Compress the target range, embedded sub-agent prompts included; the rule still applies. Remove with Edit:
   - Polite forms such as "please ..." → use the imperative.
   - The same rule repeated in multiple places → consolidate or replace with a reference.
   - Statements the AI would naturally infer (e.g. per-edge-case instructions for self-evident cases).
   - "A is the case, therefore not B" wording → keep only the first half.
   - Unnecessarily verbose code examples or templates → trim to the minimum skeleton.

   Decision criterion: if removing the text does not change the action the AI should take, remove it. Keep judgment WHY (constraints, premises, anti-misunderstanding notes).

Report to the requesting coder (the sender of this DM) via SendMessage: per file, the violations detected / fixed and whether it was compressed, the path of any template file you added, and each remaining violation as `path:line` plus the rule item it breaks.
