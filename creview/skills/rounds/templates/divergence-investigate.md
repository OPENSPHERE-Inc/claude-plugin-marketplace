---
name: divergence-investigate
description: Prompt for the divergence investigation sub-agent that, in /creview:rounds Step 2.2, identifies the source of each detected divergence and writes fix proposals into a report
template_id: ad54f81e-81f1-43c0-acff-0941524b8a3e
---

For each detected divergence, identify the source that keeps the chain going, and write fix proposals that break the chain into the divergence investigation report. Read `{{plugin_root}}/rules/sub-agent.md` and observe the common prohibitions. Read `{{plugin_root}}/rules/contract-style-prompts.md` and judge AI-facing prompt files and the findings on them by it.

Input:

- Detection result: `{{divergence_path}}` (format: `{divergences: [{id, kind, links}]}`. `kind` is `"chain"` (the chain in which a fix for a finding produces the next finding keeps going without shrinking), `"oscillation"` (a finding of this round asks to revert a past fix or asks for a change that contradicts it), or `"over-specification"` (detail findings keep coming without shrinking in consecutive rounds on an AI-facing prompt file, or a chain or oscillation has only detail findings in this round; a fix-target finding is one whose Triage is `🔧 Will Fix` and whose Estimate is not `🔻 Downgrade`, and a detail finding is a fix-target finding that `contract-style-prompts.md` classifies as a procedure-detail finding). `links` lists the findings that make up the divergence, oldest first, as `{round, id, location, finding, fix}`)
- This round's review document: `{{document_path}}`
- Paths to past rounds' review documents: `{{previous_round_doc_paths}}`
- Report template: `{{template_path}}`
- Output path: `{{report_path}}`
- Language: `{{language}}`

Investigate with the review documents, the source code that `links` points to, and the git history. Do not edit sources.

Identify the following for each divergence:

- Source: not a defect of an individual finding or fix, but the root cause that keeps findings coming however many fixes are stacked. Cite the code locations, commits, and review document passages that support it. Typical patterns:
  - The first fix's approach does not fit the design.
  - Reviewers' demands contradict each other.
  - A specification or invariant is undecided, and once it is decided, a fix that satisfies it stops the findings. In an AI-facing prompt, decide it as a goal or a contract, not as added steps.
  - The adopted approach carries a problem class that cannot be closed in principle, so the approach cannot fully satisfy the specification or invariant even once it is decided. Each fix eliminates only one counterexample, and a reviewer (especially in adversarial mode) can construct further counterexamples of the same class without limit (e.g., a race window the architecture inherently cannot remove, regex-based parsing of input that is not constrained).
  - An AI-facing prompt specifies the procedure in more detail than its goal and contracts need, so each round's review finds another gap, ambiguity, or inconsistency in the details, and each fix that adds detail gives the next review more to find.
- Fix proposals: one or more responses that break the chain. For each, state its content, why it stops the chain, and its impact range, and mark one as recommended. Treating this round's finding as Won't Fix, or leaving a design decision to the user, may be among the proposals. When the source is a problem class that cannot be closed, propose not a response to the individual counterexample but replacing the approach, or stating explicitly the scope that is accepted (input constraints, preconditions, tolerated residual risk).

For a divergence whose `kind` is `"over-specification"`, substantiate the over-specification source: identify the excess instructions the findings concentrate on and the goal and contracts those instructions serve. When the prompt does not state them, derive the result to be obtained and the contracts to keep from those instructions and from the prompt's callers (the SKILL step that launches it, the side that receives its return value, and the like), and use them as the goal and contracts of the rewrite. When the evidence shows that the findings in fact concern a goal or a contract, identify the source as for the other kinds.

When the source is an over-specified prompt:

- Include no refinement of the instructions — adding steps, enumerating cases, pinning down wording or order — in the recommended proposal or the alternatives.
- Recommend rewriting the prompt contract-style, naming the prompt file, and state in the recommendation (1) the goal to state, (2) the contracts to state and keep, and (3) the instructions to remove and leave to the executing AI. When a strict command sequence is required, include extracting it into an external script.
- For each file to rewrite, name one finding of this round that carries the rewrite, from this round's detail findings on that file, or from this round's findings in the divergence's `links` when the file has none. Across all divergences, every file a rewrite edits has exactly one carrier: when the rewrites of several divergences edit the same file, merge them into one carrier's rewrite and refer to that carrier from the later divergence. State in the recommendation that the carrier makes the rewrite in place of the change its own Plan asks for, whatever its Estimate (`▶️ Maintain` or `🚧 Alternative`). List the IDs of every other fix-target finding of this round on each file the rewrite edits, and state that the carrier's rewrite covers them, with each contract finding's fix taken into the contracts to keep, and that they are not edited individually. The fix policy the user gives reaches every fix sub-agent without naming one, and the fix sub-agents run in parallel, so unless one carrier owns every file the rewrite edits, several of them edit the same file at once or none rewrites it.
- Keep the contracts with other files (variables, return values, paths). When one must change, list every file that changes with it in the impact range, and include those files in the same carrier's rewrite.
- When the prompt already states its goal and contracts, recommend treating this round's detail findings on that file as Won't Fix. When excess instructions still remain, include the rewrite that removes them in the same recommendation, and leave its carrier out of the Won't Fix.

In an oscillation, when a finding of this round removes procedural detail from an AI-facing prompt and moves it toward its goal and contracts, do not treat that finding as the source, and do not propose restoring the removed detail.

When several divergences share a source, refer to the earlier divergence from the later one's source section instead of duplicating the description.

Output: Read `{{template_path}}` to grasp the skeleton, fill it in `{{language}}`, and Write it to `{{report_path}}`.

Return value: `{report_path, template_id}`. Include `template_id` as Read from this template's frontmatter, as-is.
