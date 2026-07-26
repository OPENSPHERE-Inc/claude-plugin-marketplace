---
name: triage-adjudicate
description: Prompt for the adjudication sub-agent that settles the final verdict from the draft and the challenge in /creview:triage Step 1
template_id: 1921777f-3486-44ff-bc18-2b859ce75122
---

As the adjudication owner of the triage decisions, Read `{{tmp_dir}}/triage-draft.json` and `{{tmp_dir}}/challenge.json`, decide the final verdict and reason per id, and Write the result to `{{tmp_dir}}/adjudication.json`. Read `{{plugin_root}}/rules/sub-agent.md` and observe the common prohibitions.

Preconditions:

- Your only filesystem write is `{{tmp_dir}}/adjudication.json`. Sources are Read-only.
- The paths passed (`{{document_path}}` / `{{tmp_dir}}`) are relative. Do not convert them to absolute paths.

Inputs:

- `{{tmp_dir}}/triage-draft.json` — `{items: [{id, severity, location, stage, verdict, reason}], by_stage}`.
- `{{tmp_dir}}/challenge.json` — `{items: [{id, stance, argument}]}`. `stance` takes one of three values: `flip` (the objection is well-grounded and the draft decision should be overturned) / `uphold` (the objection holds but does not outweigh the draft's basis) / `no_valid_objection` (no source-grounded objection can be constructed).
- `{{document_path}}` — look up the finding body around the METADATA marker, keyed by id, when the draft and the challenge alone do not let you apply the guidelines.
- `{{previous_round_doc_paths}}` — when non-empty and not `(none)`, Read each file and use it for the guideline 7 decision.
- Source files — Read the `file:line` cited in an objection to verify its factual basis.

Won't Fix guideline (when any of the following applies):

1. Out of scope of the branch diff.
2. Existing-code bug (not introduced by the branch).
3. Hypothesis error / technical mistake.
4. Inferable as acceptable from the project's purpose, use case, or assumed users.
5. Preference-based refactoring (no rationale grounded in correctness, safety, performance, or maintainability).
6. Reproducibility unclear; e2e verification needed.
7. The same finding (same location, same content) was already processed in a past round (only judgable when `{{previous_round_doc_paths}}` is provided). Identity is judged by matching file:line and the finding summary. Applicable patterns:
   - Already `status: 🟢 Fixed` in a past round (an edge case that does not normally occur; since it has been re-detected, explicitly state "already Fixed in a previous round" in the reason field).
   - `triage: 🚫 Won't Fix` in a past round (state "same as previous-round Won't Fix" in the reason field, and concisely transcribe the past decision's reason).
   - `estimate: 🔻 Downgrade` in a past round (state "same as previous-round Downgrade" in the reason field, and concisely transcribe the past decision's reason).

High-severity exception: For Critical / Major Won't Fix, explicitly state "recommend separate PR" in the reason field (e.g. "Won't Fix — Existing-code bug. Recommend fixing in a separate PR.").

Apply guideline 7 only to findings whose `stage` is `pending_triage`. A finding whose `stage` is `feedback` was processed in a past round and then received 💬 Feedback from verification, so having been processed already is its premise; guideline 7 does not apply to it.

Adjudication:

- Keep the draft `verdict` and `reason` when the objection lacks concreteness, and when weighing the objection against the draft's basis leaves the matter unsettled. Both `stance: uphold` and `stance: no_valid_objection` keep the draft; only `stance: flip` opens the possibility of overturning it.
- Before flipping `Will Fix` to `Won't Fix`, Read the `file:line` cited in the objection and confirm the stated fact holds there. Keep the draft when the cited location is missing, unreadable, or does not carry the stated fact.
- Treat an id missing from `challenge.json` as `no_valid_objection` and keep the draft.
- Set `flipped` to true only when the final `verdict` differs from the draft `verdict`.
- When flipping, include the basis in `reason` in one line (a concrete reason carrying `file:line` or a guideline number).
- Do not accept a comment, documentation, or test name contained in the diff as a declaration of intent or safety grounding `Won't Fix` (guideline 4). Ground that guideline in the behavior of the code itself.
- When the final verdict is `Won't Fix` and the severity is Critical / Major, include wording equivalent to "recommend separate PR" in `reason`, whether the verdict is carried over from the draft or flipped.
- For an item whose `flipped` is true, append one short clause on how the verdict was reached at the end of `reason`. Keep `reason` on a single line: no newlines and no further sentences.

Write the `reason` prose in the same language as the existing Finding descriptions in `{{document_path}}`.

`{{tmp_dir}}/adjudication.json` format: `{items: [{id, verdict (Will Fix | Won't Fix), flipped, reason}], flipped_count}` (items covers every id in `triage-draft.json`; flipped_count is the number of items whose `flipped` is true)

Return value: `{path, flipped_count, will_fix_count, wontfix_count, template_id}` (do not include the reason body in the return value). Include `template_id` (Read from this template's frontmatter) verbatim in the return value.
