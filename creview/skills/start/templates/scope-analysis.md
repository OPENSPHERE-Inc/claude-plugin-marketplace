---
name: scope-analysis
description: Prompt for the scope-analysis sub-agent in /creview:start Step 1, which splits the diff into review scopes and selects each scope's reviewers from the destination project's agents
template_id: b3e2f1a7-9c84-4d56-8e3b-7f1a4c9d2e85
---

As the review-scope analysis owner, Read `{{tmp_dir}}/diff.txt` to count lines, split the diff into review scopes, and select each scope's reviewers. Read `{{plugin_root}}/rules/sub-agent.md` and observe the common prohibitions.

User-explicitly-requested reviewers: `{{user_requested}}` (may be an empty array)

Reviewer pool: enumerate `*.md` from the following locations in priority order, and Read each file's frontmatter `name` / `description` to learn each agent's specialty. The `name` value is what another Agent call passes to `subagent_type`. When the same `name` exists in more than one location, adopt the higher-priority one. Skip any location that does not exist.

1. Project: `.claude/agents/**/*.md` (relative to the working directory)
2. User: `~/.claude/agents/**/*.md`
3. Plugin-bundled: `{{plugin_root}}/agents/**/*.md`

Procedure:

1. From the diff, determine the changed file kinds / paths / content areas (language, subsystem, build / CI, A/V, comments & FIXME / TODO, etc.) and a per-extension summary. `line_count` = total of +/- lines in the diff.
2. Split the changed files into review scopes per the sizing rule below. Every changed file belongs to exactly one scope. Number the scopes `s1`, `s2`, ... in the order formed.
3. For each scope, decide from each enumerated agent's `description` whether its specialty is relevant to **that scope's files** — not to the whole diff — and add every relevant agent to that scope's `reviewers` with a short `reason` citing the matching extension / path / content area. A scope no agent is relevant to gets `{name: "general-purpose", reason: "no matching specialist agent"}` instead.
4. Add every `user_requested` reviewer not already present to every scope (reason: `"user explicitly requested"`).

Sizing rule:

- `line_count` 800 or less and 20 or fewer changed files: one scope holding every changed file.
- Otherwise: split so each scope holds at most 400 changed lines and at most 10 files. The bound is what buys coverage: a reviewer owning more stops exploring after a few findings, and the review degrades into local sampling.
- Never split one file's changed lines across scopes. A file that alone exceeds 400 changed lines forms its own scope.
- Group by cohesion first (same subsystem / directory / language / concern), then apply the size bound inside that grouping.
- Cap the split at 8 scopes. When the cap binds, let the scopes exceed the size bound evenly and say so in `rationale`.

Return value: `{line_count, scopes: [{scope_id, paths (the scope's changed file paths), line_count, reviewers: [{name, reason}]}], extension_summary (e.g., ".cpp(12), .hpp(5)"), rationale (1-2 sentences justifying the split and the selection), template_id}`. Include `template_id` exactly as Read from this template's frontmatter.
