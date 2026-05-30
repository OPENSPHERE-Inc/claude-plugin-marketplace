# Agent detection & assignment shared rule

Common procedure by which creview sub-agents resolve a single specialist agent for a finding or verification error. The calling template specifies only the "match target" and the "result field".

## Enumeration

Enumerate agent `**/*.md` from the following scopes in priority order and Read each file's frontmatter `name` / `description`. When the same `name` exists in multiple scopes, adopt the higher-priority scope's entry; skip any scope that does not exist.

1. Project scope: `.claude/agents/**/*.md` (relative to the working directory)
2. User scope: `~/.claude/agents/**/*.md`
3. Plugin-bundled: the `agents/` directory one level up from this file. Resolve `../agents/**/*.md` against the absolute path from which this file was Read.

## Selection

Match each agent's `description`-stated specialty against the match target supplied by the caller (finding content / verification-error content / the finding's `Reviewers`, etc.) and pick the single best-fitting agent. When no scope has a reasonable match, use `general-purpose`.

## Result

Store the selected agent's `name` (the value another Agent call passes to `subagent_type`) into the result field designated by the caller.
