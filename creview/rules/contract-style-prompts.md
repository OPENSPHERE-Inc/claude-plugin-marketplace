# Contract-Style Prompt Guidelines

Apply these when judging an AI-facing prompt file, or a finding on one, against the contract-style policy.

## AI-facing prompt files

An AI-facing prompt file is a file an AI agent reads as its instructions, and only these kinds: agent definitions, skills (SKILL.md), slash commands, rules, and the prompt templates a skill has an agent Read. Project memory files such as CLAUDE.md / AGENTS.md, a Markdown output template (the skeleton an agent fills), a prompt string embedded in source code, and human-facing documentation such as a README are not AI-facing prompt files. When the path alone does not settle a file's role, Read the file and judge by whether it instructs its reader or is a skeleton for its reader to fill.

## Contract-style policy

An AI-facing prompt is not program code: the AI infers requirements from context even when an instruction is loose. Judge a prompt by these points:

- It states the goal concretely and leaves the method of reaching it to the executing AI, without over-specifying the procedure.
- It states explicitly the contracts that must hold at checkpoints: a command that must be run in a given form, the format of a return value or output, and the variables, paths, and identifiers exchanged with other files. The constraints and premises the AI needs for judgment count as contracts as well and stay in the prompt: a write scope, an instruction to treat untrusted input as data, a limit on tools, remote operations, or destructive operations, a note that prevents a misreading, and the like.
- Where a strict command sequence is required, the sequence is extracted into an external script, and the prompt holds only its invocation and the expected result.
- Recommended pattern: it states the result to be obtained (the goal) and lays out the tools to be used.
- Anti-pattern: it enumerates exact command lines or steps procedurally and makes the AI follow them.

When a demand for procedural detail conflicts with this policy, the policy prevails, unless the detail is a contract.

## Findings on an AI-facing prompt file

Classify a finding on an AI-facing prompt file by the kind of change its fix makes or should make, read from the finding body, the Estimate's Plan, and the Status's fix summary. A finding that shows a concrete situation in which following the prompt gives a wrong result, breaks a contract, or does not end is a contract finding, whatever change its fix makes. Whether the prompt already states its goal and contracts is not a condition: an over-specified prompt often states neither, and a finding that adds a step to it still counts as procedure detail.

- Contract finding: a change that states, corrects, or restores a goal or a contract, or aligns it with its counterpart. For example: stating, correcting, or restoring a constraint or premise the AI needs for judgment, one an earlier fix removed included; fixing a variable, placeholder, return-value field, `template_id`, or path that disagrees with the counterpart file at a checkpoint; fixing an error in, or the absence of, a command that needs a given form; defining an output format a consumer depends on; fixing a goal that is missing or contradicts other instructions.
- Procedure-detail finding: a change that adds to or refines the description of the method by which the executing AI reaches the goal. For example: adding a step, or restoring a procedural detail an earlier fix removed; enumerating cases; pinning down the order of steps; pinning down wording or a command whose form no contract requires; filling a gap, ambiguity, or inconsistency among such instructions.

A finding whose change does both is a contract finding. A finding whose fix removes procedural instructions and leaves the method to the AI, keeping or stating the goal and contracts, is not a procedure-detail finding.
