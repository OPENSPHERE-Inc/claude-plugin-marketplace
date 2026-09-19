---
name: divergence-check
description: Prompt for the divergence pattern detection sub-agent that detects, in /creview:rounds Step 2.2, divergence of the round loop from the chains in which a fix for a finding produces the next finding
template_id: 6570a998-e9f3-4421-af84-6911eebd7c07
---

Detect every divergence of the round loop — a state in which the chains where a fix for a finding produces a finding in a later round keep going without shrinking. Read `{{plugin_root}}/rules/sub-agent.md` and observe the common prohibitions.

Input:

- This round's review document: `{{document_path}}`
- Paths to past rounds' review documents: `{{previous_round_doc_paths}}`
- Detection result output path: `{{output_path}}`

Base the judgment only on these review documents (the finding bodies, and the Triage / Estimate / Status / Verification in the `<!-- METADATA(id) -->` blocks).

Definitions:

- Fix-target finding: a finding whose Triage is `🔧 Will Fix` and whose Estimate is not `🔻 Downgrade`.
- Chain link: a fix-target finding of a round that is caused by a fix for a finding of an earlier round (the change recorded in `Status: 🟢 Fixed — ...`). A finding qualifies when it takes issue with code that fix introduced or changed. A finding that merely overlaps the location and points at a problem that predates the fix does not qualify.
- Chain: the sequence obtained by tracing chain links back into the past (finding → its fix → next finding → its fix → ...).

Detect every chain that matches either of the following as a divergence. Merge chains that share their origin finding into one divergence:

- Non-shrinking chain: each chain that ends in a chain link of this round and spans 3 or more rounds, when this round's total number of chain links is at least the immediately preceding round's total.
- Oscillation: a chain in which a fix-target finding of this round asks to revert a past round's fix, or asks for a change that contradicts that fix.

When one or more divergences are detected:

- Write the detection result to `{{output_path}}`. Format: `{divergences: [{id, kind, links}]}`
  - `id`: sequential from `D-1`.
  - `kind`: `"oscillation"` when the divergence matches oscillation, otherwise `"chain"`.
  - `links`: an array of `{round, id, location, finding, fix}` listing every finding that makes up the divergence, oldest first. `finding` is a one-line summary of the finding and `fix` a one-line summary of the fix for that finding. `fix` is null for this round's finding.
- Resolve the agent that investigates the divergences' sources with the procedure in `{{plugin_root}}/rules/agents-detection.md`. The match target is the finding content of all detected divergences; the result field is `investigator`.

Return value: `{divergence_count, investigator, template_id}`. `investigator` is null when there are 0 divergences. Include `template_id` as Read from this template's frontmatter, as-is.
