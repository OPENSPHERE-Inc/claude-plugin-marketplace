---
name: select-fix-targets
description: Prompt for the select-fix-targets sub-agent in /creview:respond Step 1 that extracts fix targets and their assignees from the review document metadata
template_id: 7c3e9a1d-5b48-4f62-9a8c-2d6f1b3e7a95
---

As the fix-target selection owner, Read the review document `{{document_path}}`, apply the fix-target selection rule, and Write `{{tmp_dir}}/targets.json`. Read `{{plugin_root}}/rules/sub-agent.md` and observe the common prohibitions.

Preconditions:

- `{{tmp_dir}}` is created in advance by the leader. The only filesystem write is targets.json. Do not run existence checks or mkdir.
- `{{document_path}}` / `{{tmp_dir}}` are relative paths. Do not convert them to absolute.

Extraction targets: Critical / Major / Minor sections (skip Info). For each finding, read the values inside `<!-- METADATA(id) -->` … `<!-- /METADATA(id) -->`. When a field repeats, use the last value.

A finding is a fix target when **all** of the following hold:

- `Triage:` is `🔧 Will Fix`. Parse the assignee from `(assignee: {specialist})`. When no assignee is parseable, use `general-purpose`.
- `Estimate:` is `▶️ Maintain` or `🚧 Alternative`.
- No `Status:` line is present.

Skip (not a fix target): `Triage: 🚫 Won't Fix`, `Estimate: 🔻 Downgrade`, any finding already carrying `Status:`, and findings with no `Triage:` or no `Estimate:` (run `/creview:triage` first — record these in `not_ready` with the reason).

`{{tmp_dir}}/targets.json` format: `{items: [{id, assignee, estimate (Maintain|Alternative)}], fix_count, not_ready: [{id, reason}]}`

Return value: `{path, fix_count, by_assignee: [{assignee, ids: [id, ...]}], template_id}` (`by_assignee` groups the fix targets by assignee; do not include finding bodies). Include `template_id` (Read from this template's frontmatter) verbatim in the return value.
