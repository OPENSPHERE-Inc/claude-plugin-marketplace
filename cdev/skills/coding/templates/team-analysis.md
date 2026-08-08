---
name: team-analysis
description: Prompt for the team-analysis task (dev-helper) in cdev /coding Step 1, which scopes the coding task, selects reviewer agents from the destination project's agents (architects / coders run as general-purpose), and pairs each producer with a reviewer
template_id: d8760930-8d32-42c1-b033-d61f0cbd19c7
---

Scope the coding task, assemble the specialist team, and pair each producer with a reviewer.

Task: `{{task}}`
Output: `{{output_path}}`

Agent pool: build it per `{{plugin_root}}/rules/agents-detection.md` § Enumeration. That rule resolves one agent; here select several (below), recording each pick's `name` as its § Result specifies.

Procedure:

1. Understand the task: determine the target language(s), the subsystems / directories it touches, and the build / test surface. Determine whether the project has a test suite (a resolvable test command, a test framework, or a test directory) and set `has_test_suite`. Use Glob / Grep / Read on the existing codebase to ground this; read only enough to scope, and do not implement anything.
2. Select the team from the pool, matching each agent's `description` specialty to the task:
   - architects — own the design. An architect always runs as `general-purpose` (`name` = `general-purpose`). One suffices for a single-subsystem task; use multiple only when the task spans clearly separable subsystems. Give each a `slug` (kebab-case) and a `scope`, and note the domain its scope concerns in `reason`.
   - coders — agents to implement. A coder always runs as `general-purpose` (`name` = `general-purpose`), because some specialist agents emit tool calls as text and stall, so the implementation cannot continue. Split into one or more by implementation volume, each with a `slug` (kebab-case) and a `scope` of disjoint files / directories so two coders never edit the same file. In each coder's `reason`, note the domain / conventions its scope must follow (e.g. backend → Laravel).
   - reviewers — agents to review the design and the code. Select them so each producer's domain is individually covered (when backend / frontend / E2E / security are mixed, ensure a reviewer for each area). Give each a `slug`.
3. For a domain / role with no matching specialist in the pool, use `general-purpose` for that assignment.
4. Pair each architect and each coder with one reviewer whose domain matches that producer: set its `reviewer` to a reviewer's `slug`. Share one reviewer across several producers only when they are in the same domain. For a producer with no domain-matching reviewer, assign a `general-purpose` reviewer (do not make an out-of-domain reviewer cover it).
5. Write `task_summary` as a self-contained restatement of the task (in {{doc_lang}}) that the architects / coders can act on without the original chat.
6. Write the result to `{{output_path}}`. Write `scope` / `reason` / `rationale` / `task_summary` in {{doc_lang}}; keep `name` / `slug` / identifiers as-is.

`{{output_path}}` format:

```
{"task_summary": <string>, "target_languages": [<string>, ...], "has_test_suite": <bool>, "architects": [{"name": <string>, "slug": <string>, "scope": <string>, "reviewer": <string>, "reason": <string>}], "coders": [{"name": <string>, "slug": <string>, "scope": <string>, "reviewer": <string>, "reason": <string>}], "reviewers": [{"name": <string>, "slug": <string>, "reason": <string>}], "rationale": <string>}
```

Report completion to the leader (SendMessage with `to: "main"`) as one line naming `{{output_path}}` and the team size (architects / coders / reviewers).
