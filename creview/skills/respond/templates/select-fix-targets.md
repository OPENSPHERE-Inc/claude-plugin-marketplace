---
name: select-fix-targets
description: Prompt for the select-fix-targets sub-agent in /creview:respond Step 1 that extracts fix targets, their assignees, and their stages from the review document metadata
template_id: 7c3e9a1d-5b48-4f62-9a8c-2d6f1b3e7a95
---

As the fix-target selection owner, Read the review document `{{document_path}}`, apply the fix-target selection rule, set the stages of each fix target, and Write `{{tmp_dir}}/targets.jsonl`. Read `{{plugin_root}}/rules/sub-agent.md` and observe the common prohibitions.

Preconditions:

- `{{tmp_dir}}` is created in advance by the leader. The only filesystem write is targets.jsonl. Do not run existence checks or mkdir.
- Use `{{document_path}}` / `{{tmp_dir}}` in the form given. Do not convert them.

Extraction targets: Critical / Major / Minor sections (skip Info). For each finding, read the values inside `<!-- METADATA(id) -->` … `<!-- /METADATA(id) -->`. When a field repeats, use the last value.

A finding is a fix target when **all** of the following hold:

- `Triage:` is `🔧 Will Fix`. Parse the assignee from `(assignee: {specialist})`. When no assignee is parseable, use `general-purpose`.
- `Estimate:` is `▶️ Maintain` or `🚧 Alternative`.
- No `Status:` line is present, or `Verification:` is `💬 Feedback`. Metadata is append-only, so a finding sent back for a re-fix still carries the earlier `Status:`.

Skip (not a fix target): `Triage: 🚫 Won't Fix`, `Estimate: 🔻 Downgrade`, a finding whose `Status:` is present with no `Verification:` or with `✅ Verified`, a finding with no `Triage:` whose `Verification:` is `✅ Verified` (verified against the code; nothing to fix), and any other finding that has no `Triage:`, or that has `Triage: 🔧 Will Fix` but no `Estimate:` (run `/creview:triage` first — record these in `not_ready` with the reason).

For each fix target, extract fix_plan from the part after ` — Plan: ` on the `Estimate:` line. Split on the leading `(1) ` and subsequent ` (n) ` numbered markers into a string array, one entry per element. When there is no ` — Plan: ` segment, set fix_plan to an empty array.

When the `Estimate:` line carries an ` — ADR: {filename}` segment immediately before ` — Plan: `, set `adr` to the filename; otherwise `adr` is null. The segment is not part of fix_plan.

Set each fix target's `stages` from what its fix requirements (sub-agent.md § Fix requirements) state: `docs` when they call for editing a documentation file (§ Documentation files of the same file), and `code` when they call for editing any other file. An ADR file counts as neither. Judge only from what they state and the paths they name, without reading the source, searching the repository, or reading the project's CLAUDE.md, and count an edit of a file whose kind that leaves unclear as `code`. When they show neither, set `["code"]`.

`{{tmp_dir}}/targets.jsonl` format: `{items: [{id, assignee, stages (["code"], ["docs"], or ["code", "docs"]), estimate (Maintain|Alternative), adr (filename or null), fix_plan (string array, [] when absent)}], fix_count, not_ready: [{id, reason}]}`

Return value: `{path, fix_count, by_assignee: [{assignee, ids: [id, ...]}], code_stage: [{assignee, ids: [id, ...]}], docs_stage: [{assignee, ids: [id, ...]}], not_ready: [{id, reason}], template_id}` (`by_assignee` groups all the fix targets by assignee; `code_stage` and `docs_stage` group by assignee the fix targets whose `stages` includes `code` and `docs` respectively; `not_ready` is the same as in targets.jsonl, each `reason` a short fixed phrase; do not include finding bodies). Include `template_id` (Read from this template's frontmatter) verbatim in the return value.
