---
name: phase-triage
description: Prompt for the phase leader sub-agent that runs /creview:triage as its leader in /creview:rounds Step 2.2 and in the Step 2.5 feedback loop
template_id: 6d2a8f4c-1e93-4b57-9c8a-3f7b2d6e1a95
---

Run the `creview:triage` skill as its triage leader for one round of `/creview:rounds`. Read `{{plugin_root}}/rules/sub-agent.md` and observe the common prohibitions.

Input:

- Review document: `{{document_path}}`
- Past rounds' review document paths: `{{previous_round_doc_paths}}` (`(none)` in Round 1)
- `--adr`: `{{adr_flag}}`
- Round-specific overrides: `{{overrides}}`

What to do:

1. Invoke the `creview:triage` skill with the argument `{{document_path}}`, appending `--adr` when `{{adr_flag}}` is on. Then act as its triage leader through its Steps 1-3, including the compile step.
2. Add the following to the "Round-specific overrides" section of every sub-agent launch prompt you issue:
   - Triage sub-agent: `previous_round_doc_paths` is `{{previous_round_doc_paths}}`. State the Will Fix count explicitly in the triage report, including when it is 0.
   - Estimate sub-agent: do not reference any past round's review document (bias avoidance). When determining diffusion signal e (Will Fix originating from FIXME), check whether the finding originates from a `FIXME:` / `TODO:` in the review body or the target file.
   - Each entry in `{{overrides}}`: attach it to the launch prompt of the sub-agent it names, or to every sub-agent when it names none.
3. Run the compile step even when `will_fix_count` is 0 — it persists the Won't Fix triage values.
4. When the `creview:triage` Step 1 return value carries `error`, do not run the estimate or compile steps: return with every count as 0, `summary_path` as null, and `error` set to the received message.

Return value: `{will_fix_count, wontfix_count, flipped_count, maintain_count, alternative_count, downgrade_count, summary_path, summary_line, error, template_id}`. `flipped_count` is the number of decisions the adjudication stage overturned, copied from the triage sub-agent's return value. `error` is null on success. When the estimate stage was skipped, report `maintain_count` / `alternative_count` / `downgrade_count` as 0 and `summary_path` as null. Include `template_id` exactly as Read from this template's frontmatter.
