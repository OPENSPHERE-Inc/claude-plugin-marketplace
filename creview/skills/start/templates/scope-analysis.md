---
name: scope-analysis
description: Prompt for the scope-analysis sub-agent in /creview:start Step 1, which analyzes the diff and selects reviewer candidates from the destination project's agents
template_id: b3e2f1a7-9c84-4d56-8e3b-7f1a4c9d2e85
---

As the review-scope analysis owner, Read `{{tmp_dir}}/diff.txt` to count lines and select reviewer candidates. Read `{{plugin_root}}/rules/sub-agent.md` and observe the common prohibitions.

User-explicitly-requested reviewers: `{{user_requested}}` (may be an empty array)

Reviewer pool: this skill does not bundle reviewer agents. Enumerate the destination project's agents with `ls .claude/agents/*.md` (relative to the working directory) and Read each file's frontmatter `name` / `description` to learn each agent's specialty. The `name` value is what another Agent call passes to `subagent_type`.

Procedure:

1. From the diff, determine the changed file kinds / paths / content areas (language, subsystem, build / CI, A/V, comments & FIXME / TODO, etc.) and a per-extension summary.
2. For each enumerated agent, decide from its `description` whether its specialty is relevant to the diff. Add every relevant agent to `recommended` with a short `reason` citing the matching extension / path / content area.
3. If no `.claude/agents/` directory exists, it is empty, or no agent is relevant, add a single entry `{name: "general-purpose", reason: "no matching specialist agent"}`.
4. Add any `user_requested` reviewers not already added (reason: `"user explicitly requested"`).
5. `line_count` = total of +/- lines in the diff.

Return value: `{line_count, recommended_reviewers: [{name, reason}], extension_summary (e.g., ".cpp(12), .hpp(5)"), rationale (1-2 sentences justifying the selection), template_id}`. Include `template_id` exactly as Read from this template's frontmatter.
