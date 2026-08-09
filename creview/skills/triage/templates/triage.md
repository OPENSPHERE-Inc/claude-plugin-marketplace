---
name: triage
description: Prompt for the triage sub-agent that performs stage classification and adversarial triage (propose → parallel challenges → majority-gated adjudication) for each finding in /creview:triage Step 1
template_id: 1e9c4f7a-5b82-4d63-a1c8-3f7d2e9b4a15
---

As the triage owner of the review document, Read `{{document_path}}`, perform stage classification and adversarial triage (propose → parallel challenges → majority-gated adjudication) for each finding, and Write the final result to `{{tmp_dir}}/triage.jsonl`. Read `{{plugin_root}}/rules/sub-agent.md` and observe the common prohibitions.

Preconditions:

- `{{tmp_dir}}` is created in advance by the leader via `mkdir -p`. The Sub must not perform existence checks (`Test-Path` / `ls`, etc.) or mkdir. Your own filesystem writes are the two files `triage-draft.jsonl` and `triage.jsonl`. The challenge sub-agents and the adjudication sub-agent you launch write the `challenge-{n}.jsonl` / `adjudication.jsonl` that their own templates specify.
- The paths passed (`{{document_path}}` / `{{tmp_dir}}`) are relative. Do not convert them to absolute paths.

If `{{previous_round_doc_paths}}` is provided (empty in the standard Round 1 flow), Read each file and extract past-round decision information (id / location / description / METADATA's triage / estimate / status / verification) for reference during triage. No need to consult when empty or `(none)`.

Extraction targets: Critical / Major / Minor sections (skip Info). For each finding, obtain id (C-1, M-1, mi-1, etc.) / severity / location / description (the body up to the marker) / current_meta (the current values of triage / estimate / status / verification; when the same field appears multiple times, use the last value).

Stage classification (based on current_meta):

- Marker is empty → pending_triage
- triage: 🔧 Will Fix, no estimate → pending_estimate
- estimate: ▶️ Maintain or 🚧 Alternative, no status → pending_fix
- verification last value is 💬 Feedback → feedback (re-fix target)
- triage: 🚫 Won't Fix → wontfix_skip
- estimate: 🔻 Downgrade → downgrade_skip
- status: 🟢 Fixed, no verification or last value is ✅ Verified → fixed_skip

Only findings whose stage is pending_triage or feedback are decision targets. For other stages, count only and do not perform a triage decision.

Decision categories:

- Will Fix — Valid; should be addressed.
- Won't Fix — Not applicable / false positive / risk accepted (reason required).
- Needs Investigation — Settle on Will Fix / Won't Fix after investigating the source.

Read `{{plugin_root}}/rules/wontfix.md` and apply it when the verdict is `Won't Fix`.

Procedure:

1. Make the primary decision for each decision target and Write `{{tmp_dir}}/triage-draft.jsonl`. Do not resolve the assignee at this stage.
2. When the draft `items` is empty, skip steps 3 and 4, Write `{{tmp_dir}}/triage.jsonl` with `items: []`, `will_fix_count: 0`, `wontfix_count: 0`, and the draft's `by_stage`, and return with `flipped_count: 0`.
3. Launch three challenge sub-agents in a single message with `Agent(subagent_type="general-purpose", prompt=...)`, giving them `challenge_index` 1, 2 and 3. Do not specify the model. Fill the values you received into the launch prompt (`{n}` is that instance's `challenge_index`):

```
As your first action, you MUST Read `{{plugin_root}}/skills/triage/templates/triage-challenge.md`. Do not perform any other judgment, action, or tool call before the Read completes. After reading, follow its instructions.

Variables (substitute into the template's {{...}} placeholders):
- plugin_root: {{plugin_root}}
- document_path: {{document_path}}
- tmp_dir: {{tmp_dir}}
- previous_round_doc_paths: {{previous_round_doc_paths}}
- challenge_index: {n}

Round-specific overrides (apply after following the template's instructions):
- (none)

Include `template_id` (Read from the template's frontmatter) in the return value.
```

Verify that every returned `template_id` matches `b8701509-403b-488b-8b13-c867f9c6700b`. On mismatch, relaunch that index alone as a fresh instance of the same `subagent_type` with the same `challenge_index`. An index that mismatches twice in a row, or whose `Agent` launch itself fails (the nested-spawn depth limit is reached, etc.), produces no challenge output; carry on with the indices that did return a match.

Overturning a draft decision takes two flip votes, so when fewer than two indices produced a challenge output, skip step 4, adopt the draft `verdict` / `reason` as the final verdicts, Write `{{tmp_dir}}/triage.jsonl` following step 5, and return with `flipped_count: 0` and a note that the adjudication stage was skipped.

4. Launch the adjudication sub-agent with `Agent(subagent_type="general-purpose", prompt=...)`. Launch it only after every step 3 sub-agent has returned. Do not launch it in the same message as step 3. Do not specify the model. Fill the values you received into the launch prompt:

```
As your first action, you MUST Read `{{plugin_root}}/skills/triage/templates/triage-adjudicate.md`. Do not perform any other judgment, action, or tool call before the Read completes. After reading, follow its instructions.

Variables (substitute into the template's {{...}} placeholders):
- plugin_root: {{plugin_root}}
- document_path: {{document_path}}
- tmp_dir: {{tmp_dir}}
- previous_round_doc_paths: {{previous_round_doc_paths}}
- challenge_indices: {comma-separated challenge_index values that produced a challenge output}

Round-specific overrides (apply after following the template's instructions):
- (none)

Include `template_id` (Read from the template's frontmatter) in the return value.
```

Verify that the returned `template_id` matches `1921777f-3486-44ff-bc18-2b859ce75122`. On mismatch, launch a fresh instance of the same `subagent_type` and retry. When it mismatches twice in a row, do not proceed to step 5: return `{path: null, error: "adjudicate template_id mismatch twice", template_id}` without writing `triage.jsonl`. When the `Agent` launch itself fails, adopt the draft `verdict` / `reason` as the final verdicts, Write `{{tmp_dir}}/triage.jsonl` following step 5, and return with `flipped_count: 0` and a note that the adjudication stage was skipped.

5. Adopt the `verdict` and `reason` of `{{tmp_dir}}/adjudication.jsonl` as-is (do not rework the reason), resolve the assignee for the confirmed Will Fix set only via the procedure in `{{plugin_root}}/rules/agents-detection.md` (match target is the finding content — language, subsystem, comment-discipline, build, etc.; the result field is the assignee), and Write `{{tmp_dir}}/triage.jsonl`. For an id missing from `adjudication.jsonl`, or whose `verdict` is neither `Will Fix` nor `Won't Fix`, adopt the draft's `verdict` and `reason` and count it as not flipped. When the Read of `{{tmp_dir}}/adjudication.jsonl` fails (the file does not exist, etc.), adopt the draft `verdict` and `reason` for all ids as the final verdicts, resolve the assignee for the Will Fix set as usual, Write `{{tmp_dir}}/triage.jsonl`, and set `flipped_count: 0`.

`{{tmp_dir}}/triage-draft.jsonl` format: `{items: [{id, severity, location, stage, verdict (Will Fix | Won't Fix), reason}], by_stage: {<stage>: <int>}}` (settle Needs Investigation into either verdict before writing)

`{{tmp_dir}}/triage.jsonl` format: `{items: [{id, verdict, assignee (null for Won't Fix), reason, memo_value}], will_fix_count, wontfix_count, by_stage: {<stage>: <int>}}`

Counting basis: `will_fix_count` / `wontfix_count` / `by_assignee` / `memo_value` follow the final verdicts. `by_stage` carries over from the draft. `flipped_count` is the number of items with `flipped == true` in `adjudication.jsonl`.

Write the `reason` and `memo_value` prose in the same language as the existing Finding descriptions in `{{document_path}}` (the `🔧 Will Fix` / `🚫 Won't Fix` labels and emoji, and `(assignee: ...)`, stay fixed).

memo_value format:

- Will Fix: `🔧 Will Fix (assignee: {assignee}) — {reason}`
- Won't Fix: `🚫 Won't Fix — {reason}`

Return value: `{path, will_fix_count, wontfix_count, flipped_count, by_stage, by_assignee: [{assignee, ids: [id, ...]}], template_id}` (by_assignee groups Will Fix only by assignee. Do not include reason / memo_value or other body content in the return value). Include `template_id` (Read from this template's frontmatter) verbatim in the return value.
