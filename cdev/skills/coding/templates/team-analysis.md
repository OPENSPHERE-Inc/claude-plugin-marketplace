---
name: team-analysis
description: Prompt for the team-analysis task (dev-helper) in cdev /coding Step 1, which scopes the coding task and selects architect / coder / reviewer agents from the destination project's agents
template_id: d8760930-8d32-42c1-b033-d61f0cbd19c7
---

Scope the coding task and assemble the specialist team.

Task: `{{task}}`

Agent pool: enumerate `*.md` from the following scopes in priority order, and Read each file's frontmatter `name` / `description` to learn each agent's specialty. The `name` value is what the leader passes to `subagent_type` when spawning a teammate. When the same `name` exists in multiple scopes, adopt the higher-priority scope's entry. Skip any scope that does not exist.

1. Project scope: `.claude/agents/**/*.md` (relative to the working directory)
2. User scope: `~/.claude/agents/**/*.md`
3. Plugin-bundled: `{{plugin_root}}/agents/**/*.md`

Procedure:

1. Understand the task: determine the target language(s), the subsystems / directories it touches, and the build / test surface. Determine whether the project has a test suite (a resolvable test command, a test framework, or a test directory) and set `has_test_suite`. Use Glob / Grep / Read on the existing codebase to ground this; read only enough to scope, and do not implement anything.
2. Select the team from the pool, matching each agent's `description` specialty to the task:
   - architects — one or more agents to own the design. One architect suffices for a single-subsystem task; use multiple only when the task spans clearly separable subsystems. Give each a `slug` (kebab-case) and a `scope` (the design area it owns).
   - coders — one or more agents to implement. Give each a `slug` (kebab-case) and a `scope` of disjoint files / directories so two coders never edit the same file.
   - reviewers — one or more agents to review both the design and the code.
3. For a role with no matching specialist in any scope, use a single `general-purpose` entry for that role.
4. Write `task_summary` as a self-contained restatement of the task (in {{doc_lang}}) that the architects / coders can act on without the original chat.

Report to the leader (via SendMessage): `{task_summary, target_languages: [..], has_test_suite: <bool>, architects: [{name, slug, scope, reason}], coders: [{name, slug, scope, reason}], reviewers: [{name, reason}], rationale}`. Write `scope` / `reason` / `rationale` / `task_summary` in {{doc_lang}}; keep `name` / `slug` / language identifiers as-is. Mark the task done via TaskUpdate.
