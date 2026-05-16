---
name: compile
description: Prompt for the aggregator sub-agent that compiles fix statuses and reflects them into the markdown via events.jsonl in /creview:respond Step 4
template_id: 3b7f1c5d-8a29-4e63-b1c8-9d3a7f5e2b41
---

As the respond compile owner, aggregate the fix statuses and reflect them into the markdown via events.jsonl. The `triage` / `estimate` fields are already persisted in the document by `/creview:triage`; this step reflects only `status`. Read `{{plugin_root}}/rules/sub-agent.md` and observe the common prohibitions.

Inputs:

- status: `{{tmp_dir}}/statuses/` (one JSON per fixed finding; may be empty when there were no fix targets)
- Target markdown: `{{document_path}}`

Outputs:

- events.jsonl: `{{tmp_dir}}/events.jsonl`
- The updated `{{document_path}}`

What to do:

1. Read `{{tmp_dir}}/statuses/*.json` and collect each item's `memo_value` as a `status` event.
2. Write JSONL to `{{tmp_dir}}/events.jsonl`, one event per line. Format: `{"id":"...","field":"status","value":"..."}`. When no statuses exist, write an empty file.
3. Run `python {{plugin_root}}/scripts/render-review.py {{document_path}} {{tmp_dir}}/events.jsonl {{document_path}}`.

Return value: `{fixed_count (number of files in statuses = Maintain fixes + Alternative FIXME insertions), code_changed (true if at least one status; false otherwise), summary_line (<=200 chars; e.g. "3 fixed (2 Maintain + 1 Alternative)"), template_id}`. Include `template_id` (Read from this template's frontmatter) verbatim in the return value.
