---
name: fix
description: Prompt for the fix sub-agent that fixes assigned findings in /creview:respond Step 2
template_id: 2f8a1c5d-7b94-4e63-a1c8-5d3f9b2e7a14
---

Fix the assigned findings `{{ids}}` sequentially. Read `{{plugin_root}}/rules/sub-agent.md` and observe the common prohibitions.

Inputs (look up by id == "{finding-id}"):

- Review document `{{document_path}}` — Obtain description / location from around the METADATA marker, and the finding's resolved decision from the metadata block: `Triage:` (Will Fix + reason) and `Estimate:` (▶️ Maintain or 🚧 Alternative, with Cost / Future / Signals and, for Alternative, the FIXME-insertion direction). When a field repeats, use the last value.
- `{{tmp_dir}}/targets.jsonl` — `items[]` gives each id's `assignee`, `estimate` (Maintain | Alternative), and `fix_plan` (the fix plan finalized during `/creview:triage` estimation; a string array of `{file:line — what to change}` entries, possibly empty).

For each id:

1. Take the `fix_plan` of this id from targets.jsonl as the starting point. Read the related source to grasp the current context. Its line numbers are from estimation time and may have drifted due to source changes, so treat fix_plan as intent and apply it against the current source. When `fix_plan` is empty (legacy docs with no `Plan:` segment, etc.), derive the fix approach from description / `Estimate:`.
2. Implement the fix (conform to the coding conventions in CLAUDE.md):
   - Estimate ▶️ Maintain: a normal fix applying each edit in fix_plan.
   - Estimate 🚧 Alternative: add a FIXME: comment only (no logic change). Use the comment wording in fix_plan (or, if absent, the FIXME-insertion direction in `Estimate:`).
3. Self-review: Re-read the changed locations, check for new issues introduced (regressions, thread safety, resource leaks, etc.), and fix any found before reporting.
4. When the fix includes added or changed comments, Read `{{plugin_root}}/rules/comment.md` and self-check the added/changed comments against that discipline. Fix any violations before reporting.
5. Write to `{{tmp_dir}}/statuses/{finding-id}.jsonl`.

Parallelization constraints (when handling multiple ids):

- Multiple ids that affect the same file are processed sequentially (to prevent write conflicts).
- ids that affect different files may be processed in parallel.

`{{tmp_dir}}/statuses/{finding-id}.jsonl` format: `{id, specialist, verdict (the targets.jsonl estimate; Maintain | Alternative), description (concise description of the fix), memo_value}`

Write the `description` and `memo_value` prose in the same language as the existing Finding descriptions in `{{document_path}}` (the `🟢 Fixed` label and emoji stay fixed).

memo_value format:

- Maintain: `🟢 Fixed — {fix description}`
- Alternative: `🟢 Fixed — FIXME comment inserted at {file:line}` (description carries the same intent)

Return value: `{items: [{id, path}, ...], template_id}` (items covers all assigned ids). Include `template_id` (Read from this template's frontmatter) verbatim in the return value.
