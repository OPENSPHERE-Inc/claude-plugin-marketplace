---
name: prior-discussion
description: Prompt for the sub-agent that excludes findings the pull request conversation already raised, resolved, or rejected in /creview:pr Step 4
template_id: a1c67c6b-a514-48e6-abb5-52dc01f28221
---

Compare every finding in the review document `{{document_path}}` with the pull request conversation in `{{conversation_path}}`, and Write the findings the conversation already covers to `{{output_dir}}/triage.jsonl` as Won't Fix. Read `{{plugin_root}}/rules/sub-agent.md` and observe the common prohibitions. Your only filesystem write is `{{output_dir}}/triage.jsonl`. Restrict tool use to Read / Glob / Grep, Write for that file, and Bash only to run `check-jsonl.py`.

Inputs:

- `{{document_path}}` — one finding per `### {finding-id} — `{location}` [{categories}]` heading, in every severity section.
- `{{conversation_path}}` — `{issue_comments, reviews, review_threads}`. A review thread carries `path`, `line` (null once outdated, and for a file-level thread), `original_line`, `subject_type`, `resolved`, `outdated`, `diff_hunk` (the code its first comment was made on), and its `comments`. `author_type` tells humans from bots; weigh both alike.

A finding is covered when a comment or thread reports the same problem: the same root cause at the same place, or, for a file-level or general comment, the same problem in the same file or area. When line numbers drifted, Read the source under `{{target_dir}}` to confirm both refer to the same code; match an outdated or file-level thread by its `diff_hunk` and comment text instead of line numbers. Classify a covered finding:

- `rejected` — the PR author or a maintainer declined the point, or deferred it with a stated reason (a separate PR, an accepted limitation, etc.), and the discussion ended without a commitment to fix it in this PR, whether or not the thread was then resolved.
- `resolved` — otherwise, the code under `{{target_dir}}` no longer shows the problem, and its thread is resolved or the conversation records the problem as fixed.
- `raised` — otherwise, its thread is still open, or it was raised in a comment outside any thread.

Keep a finding that is only related, that you cannot match with confidence, or whose thread is resolved or recorded as fixed while the code under `{{target_dir}}` still shows the problem and the conversation states no reason for leaving it.

`{{output_dir}}/triage.jsonl` format: `{items: [{id, verdict: "Won't Fix", prior (raised | resolved | rejected), url (the matching comment's url), reason, memo_value}], will_fix_count: 0, wontfix_count}` (covered findings only; `wontfix_count` is the number of items)

`memo_value`: `🚫 Won't Fix — {reason}`, where `reason` states the classification and the matching comment's url in one line (e.g. `Already raised in the PR conversation: {url}`). Write `reason` in the language of the Finding descriptions in `{{document_path}}`.

Return value: `{path, excluded_count, raised, resolved, rejected, template_id}` (do not include reasons). Include `template_id` exactly as Read from this template's frontmatter.
