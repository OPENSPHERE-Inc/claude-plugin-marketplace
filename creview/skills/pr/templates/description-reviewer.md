---
name: description-reviewer
description: Instruction template for the sub-agent that reviews the pull request description against the change in /creview:pr Step 3
template_id: 2c90357b-cdd9-46bb-b2f7-fae29f38e810
---

Review the pull request description — the `title` and `body` fields of `{{pr_path}}` — against the change in `{{diff_path}}` and the code under `{{target_dir}}`. Read `{{plugin_root}}/rules/sub-agent.md` and observe the common prohibitions.

Check:

- Consistency — every claim the description makes about behavior, scope, compatibility, configuration, or testing holds in the code.
- Completeness — the description covers what a reviewer or user needs to know: user-visible behavior changes, breaking changes and their migration, new configuration or dependencies, and how the change was tested.
- Open issues — unchecked task-list items, TODO / TBD markers, open questions, and known limitations the description leaves unresolved or untracked.

Rules:

- Restrict tool use to Read / Glob / Grep / Bash(grep/ls/find), plus Write for `{{output_path}}`.
- Location: the code's `file_path:line` when a line the diff changes behaves contrary to what the description states; `PR description` for every other finding, including a claim no changed line implements.
- Severity labels: Critical (fatal, must fix) / Major (medium risk, should fix) / Minor (caution) / Info (informational). Grade a finding at `PR description` by the harm of trusting the description as written: Major when it leads a reviewer or user to a wrong decision (a check the code does not perform, an omitted breaking change), Minor for a gap that misleads no one, Info for wording.
- Category labels: one or more of `Bug` / `Maintainability` / `Readability` / `Testing` / `Performance` / `Security` / `Style` / `Documentation` / `Design`, or a new short noun phrase without `/` or `]`; join several with `/` inside one `[ ]`. Write the labels in `{{doc_lang}}`, translating the preset names.
- Read `{{plugin_root}}/rules/review.md` and follow it.

Output:

- Write only a numbered list in the format `[severity] [category] location — Description of the issue and its importance.` to `{{output_path}}` (no preamble or postamble; an empty file when there is no finding). For a `file_path:line` location, take the line number Read reports for the target file, not a position in `{{diff_path}}`.
- Write the description in `{{doc_lang}}`. Keep the location and the severity labels as-is.
- Return value: `{"path": "{{output_path}}", "critical": <int>, "major": <int>, "minor": <int>, "info": <int>, "template_id": "<template_id from this template>"}`
