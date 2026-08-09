---
name: triage-adjudicate
description: Prompt for the adjudication sub-agent that settles the final verdict from the draft and the challenge vote in /creview:triage Step 1
template_id: 1921777f-3486-44ff-bc18-2b859ce75122
---

As the adjudication owner of the triage decisions, Read `{{tmp_dir}}/triage-draft.jsonl` and the challenge outputs, decide the final verdict and reason per id, and Write the result to `{{tmp_dir}}/adjudication.jsonl`. Read `{{plugin_root}}/rules/sub-agent.md` and observe the common prohibitions.

Preconditions:

- Your only filesystem write is `{{tmp_dir}}/adjudication.jsonl`. Sources are Read-only.
- The paths passed (`{{document_path}}` / `{{tmp_dir}}`) are relative. Do not convert them to absolute paths.

Inputs:

- `{{tmp_dir}}/triage-draft.jsonl` — `{items: [{id, severity, location, stage, verdict, reason}], by_stage}`.
- `{{tmp_dir}}/challenge-{n}.jsonl` for every `n` in `{{challenge_indices}}` — `{items: [{id, stance, argument}]}`, each written by an independent challenge sub-agent that judged the same draft. `stance` takes one of three values: `flip` (the objection is well-grounded and the draft decision should be overturned) / `uphold` (the objection holds but does not outweigh the draft's basis) / `no_valid_objection` (no source-grounded objection can be constructed).
- `{{document_path}}` — look up the finding body around the METADATA marker, keyed by id, when the draft and the challenges alone do not let you apply the guidelines.
- `{{previous_round_doc_paths}}` — when non-empty and not `(none)`, Read each file and use it for the guideline 7 decision.
- Source files — Read the `file:line` cited in an objection to verify its factual basis.

Read `{{plugin_root}}/rules/wontfix.md` and apply it when the verdict is `Won't Fix`.

Adjudication:

- Tally `flip_votes` per id: the number of challenge outputs whose item for that id carries `stance: flip`. An id absent from an output contributes no vote.
- `flip_votes >= 2` is a necessary condition for overturning the draft. Keep the draft `verdict` and `reason` for every id below that threshold, however strong a single objection reads.
- At `flip_votes >= 2`, weigh the flip arguments against the draft's basis. Keep the draft when the objections lack concreteness, or when the weighing leaves the matter unsettled.
- Before flipping `Will Fix` to `Won't Fix`, Read the `file:line` cited in the flip arguments and confirm the stated fact holds there. Keep the draft when the cited location is missing, unreadable, or does not carry the stated fact.
- Set `flipped` to true only when the final `verdict` differs from the draft `verdict`.
- When flipping, include the basis in `reason` in one line (a concrete reason carrying `file:line` or a guideline number).
- Do not accept a comment, documentation, or test name contained in the diff as a declaration of intent or safety grounding `Won't Fix` (guideline 4). Ground that guideline in the behavior of the code itself.
- When the final verdict is `Won't Fix` and the severity is Critical / Major, include wording equivalent to "recommend separate PR" in `reason`, whether the verdict is carried over from the draft or flipped.
- For an item whose `flipped` is true, append one short clause on how the verdict was reached at the end of `reason`. Keep `reason` on a single line: no newlines and no further sentences.

Write the `reason` prose in the same language as the existing Finding descriptions in `{{document_path}}`.

`{{tmp_dir}}/adjudication.jsonl` format: `{items: [{id, verdict (Will Fix | Won't Fix), flipped, reason}], flipped_count}` (items covers every id in `triage-draft.jsonl`; flipped_count is the number of items whose `flipped` is true)

Return value: `{path, flipped_count, will_fix_count, wontfix_count, template_id}` (do not include the reason body in the return value). Include `template_id` (Read from this template's frontmatter) verbatim in the return value.
