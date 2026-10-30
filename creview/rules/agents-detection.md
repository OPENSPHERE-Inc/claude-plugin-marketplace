# Agent detection & assignment shared rule

Common procedure by which creview sub-agents resolve a single specialist agent for a finding or verification error. The calling template specifies only the "match target" and the "result field".

## Enumeration

Enumerate agent `**/*.md` from the following scopes in priority order and Read each file's frontmatter `name` / `description`. When the same `name` exists in multiple scopes, adopt the higher-priority scope's entry; skip any scope that does not exist. `{{plugin_root}}` is the launch variable from the prompt that had you Read this rule (same value the calling template uses).

1. Project scope: `.claude/agents/**/*.md` (relative to `main_root` when your launch prompt gives one other than `(none)`, otherwise to `{{target_dir}}`)
2. User scope: `~/.claude/agents/**/*.md`
3. Plugin-bundled: `{{plugin_root}}/agents/**/*.md`, except `review-helper`, `review-leader`, `pr-description-reviewer`, and `pr-comment-compiler`, fixed-role agents the skills launch by name

## Selection

Match each agent's `description`-stated specialty against the match target supplied by the caller (finding content / verification-error content / the finding's `Reviewers`, etc.) and pick the single best-fitting agent. When no scope has a reasonable match, use `general-purpose`.

## Result

Store the selected agent's `name` (the value another Agent call passes to `subagent_type`) into the result field designated by the caller. For a plugin-bundled (scope 3) agent, store the namespaced value (e.g. `creview:comment-sensei`).
