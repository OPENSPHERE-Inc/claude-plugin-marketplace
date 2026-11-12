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

1. Invoke the `creview:triage` skill with the argument `{{document_path}}`, appending `--adr` when `{{adr_flag}}` is on. Then act as its triage leader through its Steps 1-3, including the compile step. Unless the skill aborts, leave the working directory in place — `summary_path` is read from it after you return.
2. Add the following to the "Round-specific overrides" section of every sub-agent launch prompt you issue:
   - Triage sub-agent: `previous_round_doc_paths` is `{{previous_round_doc_paths}}`. State the Will Fix count explicitly in the triage report, including when it is 0.
   - Estimate sub-agent: do not reference any past round's review document (bias avoidance). When determining diffusion signal e (Will Fix originating from FIXME), check whether the finding originates from a `FIXME:` / `TODO:` in the review body or the target file.
   - Each entry in `{{overrides}}`: attach it to the launch prompt of the sub-agent it names, or to every sub-agent when it names none.
3. Run the compile step even when `will_fix_count` is 0 — it persists the Won't Fix triage values.
4. When the skill stops on an error, as `error` below defines it, do not run its remaining steps: return with every count as 0 and `summary_path` and `summary_line` as null. A `creview:triage` Step 1 return value that carries `error` is such an error, with the received message as `error`.

Return value: `{will_fix_count, wontfix_count, flipped_count, maintain_count, alternative_count, downgrade_count, summary_path, summary_line, tmp_dir, error, template_id}`. `tmp_dir` is the working directory the skill created, reported on an error as well, and null when the skill stopped before creating it. `flipped_count` is the number of decisions the adjudication stage overturned, copied from the triage sub-agent's return value. `error` is null when the skill ran through its Steps 1-3, warnings included. When the skill aborted or terminated, or stopped at a step that failed with no way on, such as a script exiting non-zero or a sub-agent's `template_id` mismatching twice in a row, `error` is the error the skill showed, or, when it showed none, a message you write naming the step it stopped at and what failed there: a command's exit code and error output, or the mismatched `template_id`. When the estimate stage was skipped, report `maintain_count` / `alternative_count` / `downgrade_count` as 0 and `summary_path` as null. Include `template_id` exactly as Read from this template's frontmatter.
