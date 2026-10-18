---
name: reviewer
description: Instruction template for an individual reviewer (specialist sub-agent) performing the diff review in /creview:start Step 2
template_id: 4d8c2e5b-1f73-4a96-b2e8-9c1d3a7f4b62
---

Read `{{diff_path}}` and conduct a code review. Read `{{plugin_root}}/rules/sub-agent.md` and observe the common prohibitions.

Targets: `{{targets}}` (base: `{{base}}`)

Scope: `{{scope_paths}}` — the changed files assigned to you. The other changed files in `{{diff_path}}` belong to another reviewer.

Rules:

- Restrict tool use to Read / Glob / Grep / Bash(grep/ls/find). Re-running git diff/log/show is unnecessary (the diff is already consolidated in `{{diff_path}}`). Use Read when inspecting surrounding code as well.
- Review every change under the scope paths, and cover all of them before returning; do not stop at a finding count. Anchor every finding at a line inside a scope path — a cause lying outside the scope may be cited in the description, but a finding located outside it belongs to another reviewer.
- A change without hunks is in scope too: a binary file (`Binary files ... differ`), a mode change, an empty file added or deleted, a rename. Whether a binary file needs review depends on what uses it in the source and on your perspective: e.g., in a web app, an updated image can change a page's layout or lack the resolution its target DPI needs. Read the file under `{{target_dir}}` when you review it (Read displays images); judge a deleted one, or one in a format Read cannot display (e.g., a font, an archive, an executable), from its uses; that you could not view its content is not itself a finding.
- A text file — source, a script, configuration, a lockfile, Markdown, judged by its path or by what Read shows — that is added or modified but that the diff shows as binary (git does so for a NUL byte in its first 8,000 bytes or a `binary` / `-diff` attribute) hides its whole change from the diff. Review it whatever uses it: Read the whole file under `{{target_dir}}`, review it as text, and anchor findings at the lines Read reports. When it is modified, so the diff does not tell which lines changed, or when Read cannot show all of it, also report as a finding at line 1 that its change could not be located.
- Severity labels: Critical (fatal, must fix) / Major (medium risk, should fix) / Minor (caution) / Info (informational).
- Category labels: assign one or more category labels indicating the nature of the finding. Presets: `Bug` / `Maintainability` / `Readability` / `Testing` / `Performance` / `Security` / `Style` / `Documentation` / `Design`. If no preset fits, create a new label (short noun phrase, must not contain `/` or `]`). When multiple apply, join with `/` inside a single `[ ]`. Write the labels in `{{doc_lang}}`, translating the preset names.
- Read `{{plugin_root}}/rules/review.md` and follow it.

Output:

- Write only a numbered list in the format `[severity] [category] file_path:line — Description of the issue and its importance.` to `{{output_path}}` (no preamble or postamble).
  - Category examples: `[Bug]` / `[Maintainability/Readability]` / `[Testing]`.
  - `line` is the actual line number in the target file. Do not use a hunk header (`@@ -a,b +c,d @@`) or a position within `{{diff_path}}` as the line number (diff positions do not match real file line numbers). Use the diff only to locate what changed; obtain the line number by Read-ing the target file and using the line number Read reports (which is the real file line number). Added/changed lines point to the matching line in the current file; deleted lines point to the nearest surrounding line. A finding about a change without lines (a binary file, a mode change, an empty file) takes line 1.
- Write the issue description in `{{doc_lang}}`. Keep `file_path:line` and the severity labels (Critical / Major / Minor / Info) as-is.
- Return value: `{"path": "{{output_path}}", "critical": <int>, "major": <int>, "minor": <int>, "info": <int>, "template_id": "<template_id from this template>"}`
