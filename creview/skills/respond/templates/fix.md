---
name: fix
description: Prompt for the fix sub-agent that fixes assigned findings in /creview:respond Step 2
template_id: 2f8a1c5d-7b94-4e63-a1c8-5d3f9b2e7a14
---

Fix the assigned findings `{{ids}}` sequentially, in the `{{stage}}` stage. Read `{{plugin_root}}/rules/sub-agent.md` and observe the common prohibitions.

An id's fix makes the edits its fix requirements (sub-agent.md § Fix requirements) call for, and those the project's CLAUDE.md requires along with them, such as a translation's counterpart. This stage's files are the files of the kind the Source editing rule of sub-agent.md allows the fix sub-agent in this stage, whether or not the fix touches them. Make the edits of the fix that fall on this stage's files, and on the ADR file of step 5 when this stage runs it. Leave the following unedited, and name the file and the change of each in the id's `description` and `memo_value`, except an edit of the fix that another stage of the id makes:

- An edit of the fix that falls on a file outside this stage's files.
- An edit of the fix that falls on a file your Round-specific overrides forbid you to create.
- A change beyond the edits of the fix that you notice is needed and do not make: a gap within this finding's scope on a file outside this stage's files, or documentation the fix has left out of line with the code.

Inputs (look up by id == "{finding-id}"):

- Review document `{{document_path}}` — Obtain the `- **Source:**` bullet from the header, description / location from around the METADATA marker, and the finding's resolved decision from the metadata block: `Triage:` (Will Fix + reason), `Estimate:` (▶️ Maintain or 🚧 Alternative, with Cost / Future / Signals and, for Alternative, the FIXME-insertion direction), and `Verification:`. When a field repeats, use the last value.
- `{{tmp_dir}}/targets.jsonl` — `items[]` gives each id's `assignee`, `stages` (the stages set to fix this id: `["code"]`, `["docs"]`, or `["code", "docs"]`; the `docs` stage also fixes an id whose `code` stage returned `docs_left: true`), `estimate` (Maintain | Alternative), `adr` (the finding's ADR filename in the review document's directory, or null), and `fix_plan` (the fix plan finalized during `/creview:triage` estimation; a string array of `{file:line — what to change}` entries, possibly empty).
- `docs` stage only: `{{diff_path}}` — the `fetch-diff.sh` output comparing the working tree with HEAD after the code stage, a guide to where the code changed; it may also hold uncommitted changes made before this run.

For each id:

1. Take this id's fix requirements as the starting point and Read the related source as it now stands. In the `docs` stage, that includes the code the documentation describes, with this run's code fixes; also read `{{diff_path}}` unless it is `(none)`, and this id's `{{tmp_dir}}/statuses/{finding-id}.jsonl` when it exists.
2. Make this stage's edits of the fix (conform to the coding conventions in CLAUDE.md):
   - Estimate ▶️ Maintain: a normal fix. In the `docs` stage, keep the edits within this finding's scope and look for no documentation file to edit beyond the edits of the fix. Where an edit states what the code does, have it state what the code it describes now does; where the fix requirements would have it state otherwise, follow the code and state the difference in `description` and `memo_value`.
   - Estimate 🚧 Alternative: add a FIXME: comment only (no logic change, and no change to a documentation file's existing text), in the wording its fix requirements give.
3. Self-review: Re-read the changed locations, check for new issues introduced (regressions, thread safety, resource leaks, etc.), and fix any found before reporting.
4. When the fix includes added or changed comments, Read `{{plugin_root}}/rules/comment.md` and self-check the added/changed comments against that discipline. Fix any violations before reporting.
   - Write a `FIXME:` / `TODO:` only for the 🚧 Alternative case in step 2. Such an annotation stands permanently as grounds for excluding that spot from review, so do not mark a residual gap you noticed while fixing: under ▶️ Maintain, fix it when it falls within this finding's scope, on one of this stage's files; otherwise leave it unannotated, and name it in `description` and `memo_value` only as the list of unedited changes above directs.
5. ADR, in the `code` stage, and in the `docs` stage only when this id's `stages` lacks `code`:
   - `adr` non-null: update the ADR — set Status to `Accepted`, append a History entry (date = the date part of `{{timestamp}}` as YYYY-MM-DD, `{review document filename} / {finding-id}`, one-line fix summary). Record any deviation from its Decision and any design decision made during implementation in Decision / Consequences.
   - `adr` null, `{{adr_flag}}` on, and the implementation itself chose one of multiple viable approaches with lasting trade-offs: Write `{basename of {{document_path}} without .md}-adr-{finding-id}.md` in the review document's directory with Status `Accepted` and a Created History entry, following the skeleton in `{{plugin_root}}/rules/adr-format.md`, and append ` — ADR: {filename}` to memo_value.
6. Write to `{{tmp_dir}}/statuses/{finding-id}.jsonl`. In the `docs` stage, when this id's `stages` includes `code`, merge into the file the code stage wrote: keep `id`, `specialist`, `verdict`, and every path already in `files`; add the documentation files this stage changed to `files`; and rewrite `description` and `memo_value` as one fix covering both stages, keeping each change the code stage left unedited that this stage does not make either, with its file, and keeping any ` — ADR: {filename}` at the end. When that file is missing or unreadable, write a new one with only this stage's changes in `files`, and state in `description` and `memo_value` that the code side of the fix could not be confirmed.

Parallelization constraints (when handling multiple ids):

- Multiple ids that affect the same file are processed sequentially (to prevent write conflicts).
- ids that affect different files may be processed in parallel.

`{{tmp_dir}}/statuses/{finding-id}.jsonl` format: `{id, specialist, verdict (the targets.jsonl estimate; Maintain | Alternative), description (concise description of the fix), memo_value, files (repo-relative paths of the files this fix changed, documentation files included and ADR files left out)}`

Write the `description` and `memo_value` prose in the same language as the existing Finding descriptions in `{{document_path}}` (the `🟢 Fixed` label and emoji stay fixed).

memo_value format (when step 5 created a new ADR, append ` — ADR: {filename}`):

- Maintain: `🟢 Fixed — {fix description}`
- Alternative: `🟢 Fixed — FIXME comment inserted at {file:line}` (description carries the same intent)

Return value: `{items: [{id, path, docs_left}, ...], template_id}` (items covers all assigned ids). `docs_left` is true when, in the `code` stage, this id's `stages` lacks `docs` and you left unedited, under the first item of the list above, an edit of the fix on a documentation file; otherwise false. Include `template_id` (Read from this template's frontmatter) verbatim in the return value.
