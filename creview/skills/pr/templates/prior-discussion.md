---
name: prior-discussion
description: Prompt for the sub-agent that excludes findings the pull request conversation already raised, resolved, or rejected in /creview:pr Step 4
template_id: a1c67c6b-a514-48e6-abb5-52dc01f28221
---

Compare every finding in the review document `{{document_path}}` with the pull request conversation in `{{conversation_path}}`, and Write the findings the conversation already covers to `{{output_dir}}/triage.jsonl` as Won't Fix. Read `{{plugin_root}}/rules/sub-agent.md` and observe the common prohibitions. Your only filesystem write is `{{output_dir}}/triage.jsonl`.

Inputs:

- `{{document_path}}` — one finding per `### {finding-id} — `{location}` [{categories}]` heading, in every severity section.
- `{{conversation_path}}` — `{issue_comments, reviews, review_threads}`. A review thread carries `path`, `line` (null once outdated), `original_line`, `resolved`, `outdated`, and its `comments`. `author_type` tells humans from bots; weigh both alike.

A finding is covered when a comment or thread reports the same problem: the same root cause at the same place, or, for a file-level or general comment, the same problem in the same file or area. When line numbers drifted, Read the source under `{{target_dir}}` to confirm both refer to the same code. Classify a covered finding:

- `rejected` — the PR author or a maintainer declined the point and the discussion ended without a commitment to fix it, whether or not the thread was then resolved.
- `resolved` — otherwise, its thread is resolved or the conversation records the problem as fixed.
- `raised` — any other covered finding.

Keep a finding that is only related, or that you cannot match with confidence.

`{{output_dir}}/triage.jsonl` format: `{items: [{id, verdict: "Won't Fix", prior (raised | resolved | rejected), url (the matching comment's url), reason, memo_value}], will_fix_count: 0, wontfix_count}` (covered findings only; `wontfix_count` is the number of items)

`memo_value`: `🚫 Won't Fix — {reason}`, where `reason` states the classification and the matching comment's url in one line (e.g. `Already raised in the PR conversation: {url}`). Write `reason` in the language of the Finding descriptions in `{{document_path}}`.

Return value: `{path, excluded_count, raised, resolved, rejected, template_id}` (do not include reasons). Include `template_id` exactly as Read from this template's frontmatter.
