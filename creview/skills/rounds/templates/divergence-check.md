---
name: divergence-check
description: Prompt for the divergence pattern detection sub-agent that detects, in /creview:rounds Step 2.2, divergence of the round loop from the chains in which a fix for a finding produces the next finding and from the AI-facing prompt files whose procedural details draw fix-target findings round after round
template_id: 6570a998-e9f3-4421-af84-6911eebd7c07
---

Detect every divergence of the round loop — a state in which the chains where a fix for a finding produces a finding in a later round keep going without shrinking, or in which the procedural details of an AI-facing prompt file draw fix-target findings round after round. Read `{{plugin_root}}/rules/sub-agent.md` and observe the common prohibitions. Read `{{plugin_root}}/rules/contract-style-prompts.md` and judge AI-facing prompt files and the findings on them by it.

Input:

- This round's review document: `{{document_path}}`
- Paths to past rounds' review documents: `{{previous_round_doc_paths}}`
- Detection result output path: `{{output_path}}`

Base the judgment only on these review documents (the finding bodies, and the Triage / Estimate / Status / Verification in the `<!-- METADATA(id) -->` blocks). The one exception: to judge whether a finding's file is an AI-facing prompt file, you may Read that file; when it no longer exists, judge from its path and the finding body.

Definitions:

- Fix-target finding: a finding whose Triage is `🔧 Will Fix` and whose Estimate is not `🔻 Downgrade`.
- Chain link: a fix-target finding of a round that is caused by a fix for a finding of an earlier round (the change recorded in `Status: 🟢 Fixed — ...`). A finding qualifies when it takes issue with code that fix introduced or changed. A finding that merely overlaps the location and points at a problem that predates the fix does not qualify.
- Chain: the sequence obtained by tracing chain links back into the past (finding → its fix → next finding → its fix → ...).
- Detail finding: a fix-target finding on an AI-facing prompt file that `contract-style-prompts.md` § Findings on an AI-facing prompt file classifies as a procedure-detail finding. A finding's file is the path part of its location; a finding whose location names no file counts toward no file.

Detect each of the following as a divergence:

- Non-shrinking chain: each chain that ends in a chain link of this round and spans 3 or more rounds, when this round's total number of chain links is at least the immediately preceding round's total.
- Oscillation: a chain in which a fix-target finding of this round asks to revert a past round's fix, or asks for a change that contradicts that fix.
- Over-specified prompt: an AI-facing prompt file with detail findings in this round and in each of the two rounds immediately before it, when this round's number of detail findings on it is at least the immediately preceding round's. One divergence per file.

Merge chains that share their origin finding into one divergence. Merge an over-specified prompt with every other divergence that shares a finding of this round with it, transitively.

When one or more divergences are detected:

- Write the detection result to `{{output_path}}`. Format: `{divergences: [{id, kind, links}]}`
  - `id`: sequential from `D-1`.
  - `kind`: the first of these that applies: `"over-specification"` when the divergence includes an over-specified prompt or every finding of this round in it is a detail finding; `"oscillation"` when it matches oscillation; otherwise `"chain"`.
  - `links`: an array of `{round, id, location, finding, fix}` listing every finding that makes up the divergence, oldest first. For an over-specified prompt, these are the file's detail findings in each round of the unbroken run of rounds with detail findings on it that ends in this round; they need not be chain links. `finding` is a one-line summary of the finding. `fix` is a one-line summary of its fix when its Status is `🟢 Fixed`, and null otherwise, this round's findings included.
- Resolve the agent that investigates the divergences' sources with the procedure in `{{plugin_root}}/rules/agents-detection.md`. The match target is the finding content of all detected divergences; the result field is `investigator`.

Return value: `{divergence_count, investigator, template_id}`. `investigator` is null when there are 0 divergences. Include `template_id` as Read from this template's frontmatter, as-is.
