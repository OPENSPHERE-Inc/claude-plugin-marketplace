---
name: estimate
description: Prompt for the estimate sub-agent that batch-estimates the cost of assigned findings in /creview:triage Step 2
template_id: 8b2d5f1c-7a93-4e64-b8d1-2c5e9a3f7b48
---

Batch-estimate the cost of the assigned findings `{{ids}}` (investigation and decision only; do not perform fixes). Read `{{plugin_root}}/rules/sub-agent.md` and observe the common prohibitions.

Inputs (look up by id == "{finding-id}"):

- Review document `{{document_path}}` — Obtain description / location / severity from around the METADATA marker.
- `{{tmp_dir}}/triage.jsonl` — Obtain verdict / reason from the items array by matching id.

For each id:

1. Read the related source and produce a concrete fix plan: for each edit, write `{file:line} — {what to change}`. For added comments (including FIXME / TODO), include the planned wording and insertion point. Cost / future / decision in the steps below must be grounded in this plan.
2. Diffusion-signal classification (multiple selections allowed; none also allowed):
   a. Introduction of a new concept (a library / API / language feature not yet used)
   b. Expansion of fix scope (files / modules not modified in the current branch)
   c. Asynchronous-execution timing interference (UI thread blocking, callback ordering, Qt connection-type changes, etc.)
   d. Future cost (interim workaround / FIXME deferral / missing abstraction)
   e. FIXME-originated Will Fix (originally derived from a FIXME / TODO, or a FIXME-insertion proposal that was triaged as Will Fix)
   f. Target change (e.g. version bumps of build / runtime targets)
3. Compute cost (S/M/L) and future (S/M/L). State the basis in 1–2 sentences.
4. Primary decision (Downgrade / Alternative may be chosen regardless of severity):
   - Maintain — Cost is reasonable; proceed with the fix.
   - Downgrade — Overturn the decision and do not fix. No alternative measure. Include "recommend separate PR" in the reason as needed.
   - Alternative — Overturn the decision and apply a lightweight measure such as adding a FIXME. Indicate the FIXME wording direction concisely. Include "recommend separate PR" as needed.

   cost == L is Downgrade (include "recommend separate PR" in the reason). L-scale is outside the auto-fix scope of /creview:respond and requires user judgment (this does not mean "no fix needed").

   When cost is S/M: The higher the severity, the stricter the bar for Downgrade. Critical / Major usually preferably go to Alternative or "Downgrade + recommend separate PR". Minor / Info more readily allow Downgrade.

5. Comment-addition necessity check (perform only when the fix plan includes adding a comment). Adding a comment does not solve the underlying code issue, so judge necessity strictly and independently even when the cost is low (a few-line addition). Low cost is not a justification for adoption. As a rule, exclude comments matching any of the criteria below. Finalize the primary decision based on what remains after exclusion:
   - Code changes still remain after exclusion → Maintain (update the fix plan to omit the comment)
   - Nothing remains after exclusion → Downgrade (decide whether to include "recommend separate PR" in the reason based on the finding's severity)

   Reject criteria (exclude matching comments):
   a. Violations of `{{plugin_root}}/rules/comment.md` (multi-paragraph justifications, descriptions dependent on change history or chat context, explanations of obvious what, etc.).
   b. Comments aimed at communicating with a specific reader (chat user, reviewer, a particular colleague, etc.). Comments are an information source for future third-party readers, not a communication channel.

   Downgrade criteria (the comment carries little information value; exclude matching comments):
   c. Comments whose content can be grasped by reading source within the same file (paraphrasing what / how that is obvious from naming, structure, or nearby expressions).
   d. In-function comments that explain the caller's behavior or usage premises. Explanations about the caller belong on the caller side.

   FIXME / TODO individual judgment (when considering Alternative):
   e. Items that are sufficient to record in the final report as "recommend follow-up PR" should not leave a FIXME in the source; switch to Alternative → Downgrade (include "recommend separate PR" in the reason). Leave a FIXME only when the future editor of that location must inevitably notice it during editing (a pitfall easily hit during editing, an interim implementation of logic, an unsupported specific condition, etc.).

6. ADR (only when `{{adr_flag}}` is on and the final verdict is Maintain or Alternative). Create / update an ADR only when the decision is a design decision — at least one of:
   - Multiple viable approaches existed and the plan commits to one with lasting trade-offs.
   - The fix changes or constrains architecture, public API, data format, concurrency behavior, or dependencies.
   - Alternative defers the root-cause fix for design reasons rather than pure cost.

   Mechanical fixes with one obvious approach get no ADR (`adr` = null). When a criterion holds:

   - List existing `*-adr-*.md` files in the directory of `{{document_path}}`. When one records a decision on the same location and subject, update that file instead of creating a new one: append a History entry (date = the date part of `{{timestamp}}` as YYYY-MM-DD); when the new decision replaces the recorded one, set the old file's Status to `Superseded by {new filename}` and Write the new ADR with a History entry referencing the old file.
   - Otherwise Write `{basename of {{document_path}} without .md}-adr-{finding-id}.md` in the same directory with Status `Proposed`, following the skeleton in `{{plugin_root}}/rules/adr-format.md`.
   - Set `adr` to the created / updated filename.

7. Write to `{{tmp_dir}}/estimates/{finding-id}.jsonl`.

`{{tmp_dir}}/estimates/{finding-id}.jsonl` format: `{id, specialist, verdict (Maintain | Downgrade | Alternative), cost (S|M|L), future (S|M|L), signals (["a","b",...] or []), fix_plan, rationale, adr (filename or null), memo_value}`

fix_plan format: array of strings, each entry `"{file:line} — {what to change}"`. Include comment wording for added comments. Reflect the plan finalized at Step 5:

- Maintain: code-change edits (after Step 5 comment-necessity exclusion)
- Alternative: FIXME / TODO insertion(s) only
- Downgrade: the rejected plan that was costed (record as-is)

Write the `rationale`, the `fix_plan` change descriptions, and the `memo_value` prose in the same language as the existing Finding descriptions in `{{document_path}}` (the `▶️ Maintain` / `🔻 Downgrade` / `🚧 Alternative` labels and emoji, the `Cost:` / `Future:` / `Signals:` / `ADR:` / `Plan:` keys, the signal letters a–f, S/M/L, the `(n)` markers, and file:line stay fixed).

memo_value format (for Maintain / Alternative, fold all fix_plan entries onto the single line as a trailing ` — Plan: ` segment; join entries with ` (n) ` numbered markers and include no newlines; do not summarize or omit; do not append for Downgrade; when `adr` is non-null, insert an ` — ADR: {adr}` segment immediately before ` — Plan: `):

- Maintain: `▶️ Maintain — Cost: {cost}, Future: {future}, Signals: {a,b,... or none} — Plan: (1) {fix_plan[0]} (2) {fix_plan[1]} ...`
- Downgrade: `🔻 Downgrade — Cost: ..., Future: ..., Signals: ... — {downgrade reason}`
- Alternative: `🚧 Alternative — Cost: ..., Future: ..., Signals: ... — FIXME insertion: {direction} — Plan: (1) {fix_plan[0]} ...`

Return value: `{items: [{id, verdict, adr}, ...], template_id}` (items covers all assigned ids; `adr` is the step 6 filename or null). Include `template_id` (Read from this template's frontmatter) verbatim in the return value.
