---
name: compile
description: Prompt for the aggregator sub-agent that compiles triage / estimate decisions and reflects them into the markdown via events.jsonl in /creview:triage Step 3
template_id: 3b7f1c5d-8a29-4e63-b1c8-9d3a7f5e2b41
---

As the triage compile owner, aggregate the triage / estimate decisions and reflect them into the markdown via events.jsonl. `status` and `verification` are out of scope (set by `/creview:respond` and `/creview:resolve`). Read `{{plugin_root}}/rules/sub-agent.md` and observe the common prohibitions.

Inputs:

- triage: `{{tmp_dir}}/triage.json`
- estimate: `{{tmp_dir}}/estimates/` (one JSON per Will Fix finding; absent when will_fix_count == 0)
- Target markdown: `{{document_path}}`

Outputs:

- events.jsonl: `{{tmp_dir}}/events.jsonl`
- The updated `{{document_path}}`

What to do:

1. Read `{{tmp_dir}}/triage.json` and `{{tmp_dir}}/estimates/*.json` and collect each item's `memo_value` as an event for the corresponding field (`triage` from triage.json items, `estimate` from each estimates JSON).
2. Write JSONL to `{{tmp_dir}}/events.jsonl`, one event per line. Format: `{"id":"...","field":"triage|estimate","value":"..."}`
3. Run `python {{plugin_root}}/scripts/render-review.py {{document_path}} {{tmp_dir}}/events.jsonl {{document_path}}`.

Return value: `{fixed_count (always 0 for this step), code_changed (false), summary_line (<=200 chars; e.g. "5 triaged: 3 Will Fix (2 Maintain + 1 Alternative), 2 Won't Fix"), template_id}`. Include `template_id` (Read from this template's frontmatter) verbatim in the return value.
