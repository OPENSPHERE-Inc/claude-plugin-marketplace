---
name: divergence-investigate
description: Prompt for the divergence investigation sub-agent that, in /creview:rounds Step 2.2, identifies the source of each detected divergence and writes fix proposals into a report
template_id: ad54f81e-81f1-43c0-acff-0941524b8a3e
---

For each detected divergence, identify the source that keeps the chain going, and write fix proposals that break the chain into the divergence investigation report. Read `{{plugin_root}}/rules/sub-agent.md` and observe the common prohibitions.

Input:

- Detection result: `{{divergence_path}}` (format: `{divergences: [{id, kind, links}]}`. `kind` is `"chain"` (the chain in which a fix for a finding produces the next finding keeps going without shrinking) or `"oscillation"` (a finding of this round asks to revert a past fix or asks for a change that contradicts it). `links` lists the findings that make up the divergence, oldest first, as `{round, id, location, finding, fix}`)
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
  - A specification or invariant is undecided, and once it is decided, a fix that satisfies it stops the findings.
  - The adopted approach carries a problem class that cannot be closed in principle, so the approach cannot fully satisfy the specification or invariant even once it is decided. Each fix eliminates only one counterexample, and a reviewer (especially in adversarial mode) can construct further counterexamples of the same class without limit (e.g., a race window the architecture inherently cannot remove, regex-based parsing of input that is not constrained).
- Fix proposals: one or more responses that break the chain. For each, state its content, why it stops the chain, and its impact range, and mark one as recommended. Treating this round's finding as Won't Fix, or leaving a design decision to the user, may be among the proposals. When the source is a problem class that cannot be closed, propose not a response to the individual counterexample but replacing the approach, or stating explicitly the scope that is accepted (input constraints, preconditions, tolerated residual risk).

When several divergences share a source, refer to the earlier divergence from the later one's source section instead of duplicating the description.

Output: Read `{{template_path}}` to grasp the skeleton, fill it in `{{language}}`, and Write it to `{{report_path}}`.

Return value: `{report_path, template_id}`. Include `template_id` as Read from this template's frontmatter, as-is.
