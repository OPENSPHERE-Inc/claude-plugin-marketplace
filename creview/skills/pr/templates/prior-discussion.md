---
name: prior-discussion
description: Prompt for the sub-agent in /creview:pr Step 4 that compares the findings with the pull request conversation — excluding findings it already raised, resolved, or rejected, linking findings to the open threads to reply in, and finding the viewer's threads whose fix can be confirmed
template_id: a1c67c6b-a514-48e6-abb5-52dc01f28221
---

Compare every finding in the review document `{{document_path}}` with the pull request conversation in `{{conversation_path}}`. Write the findings that are not to be posted to `{{output_dir}}/triage.jsonl` as Won't Fix, and the review threads to reply in to `{{output_dir}}/threads.jsonl`. Read `{{plugin_root}}/rules/sub-agent.md` and observe the common prohibitions. Your only filesystem writes are those two files. Restrict tool use to Read / Glob / Grep, Write for those files, and Bash only to run `check-jsonl.py`.

Inputs:

- `{{document_path}}` — one finding per `### {finding-id} — `{location}` [{categories}]` heading, in every severity section.
- `{{conversation_path}}` — `{viewer, issue_comments, reviews, review_threads}`. `viewer` is the account the review is posted as. A review thread carries `id`, `path`, `line` (null once outdated, and for a file-level thread), `original_line`, `subject_type`, `resolved`, `outdated`, `diff_hunk` (the code its first comment was made on), `own` (the viewer started it), `confirmed` (the viewer already confirmed its fix), and its `comments`. `author_type` tells humans from bots; weigh both alike.

A finding is covered when a comment or thread reports the same problem: the same root cause at the same place, or, for a file-level or general comment, the same problem in the same file or area. When line numbers drifted, Read the source under `{{target_dir}}` to confirm both refer to the same code; match an outdated or file-level thread by its `diff_hunk` and comment text instead of line numbers. Classify a covered finding:

- `rejected` — the PR author or a maintainer declined the point, or deferred it with a stated reason (a separate PR, an accepted limitation, etc.), and the discussion ended without a commitment to fix it in this PR, whether or not the thread was then resolved.
- `resolved` — otherwise, the code under `{{target_dir}}` no longer shows the problem, and its thread is resolved or the conversation records the problem as fixed.
- `reused` — otherwise, it matches a review thread that is not resolved and whose last comment is not the viewer's report of the same problem: the finding stays in the review and is posted as a reply in that thread.
- `raised` — otherwise, it was raised in a comment outside any review thread, or by the viewer in the last comment of a review thread that is not resolved (a reply would repeat it).

Keep a finding unclassified when it is only related, when you cannot match it with confidence, or when its thread is resolved or recorded as fixed while the code under `{{target_dir}}` still shows the problem and the conversation states no reason for leaving it.

Fix confirmations: for each thread whose `own` is true and `confirmed` is false and that no finding in `{{document_path}}` matches, Read the code under `{{target_dir}}` where the thread points (by `diff_hunk` when it is outdated) and decide whether the problem its first comment reports is gone. List the thread when it is gone; leave it out when the problem remains or you cannot tell.

`{{output_dir}}/triage.jsonl` format: `{items: [{id, verdict: "Won't Fix", prior (raised | resolved | rejected), url (the matching comment's url), reason, memo_value}], will_fix_count: 0, wontfix_count}` (`rejected`, `resolved`, and `raised` findings only; `wontfix_count` is the number of items)

`memo_value`: `🚫 Won't Fix — {reason}`, where `reason` states the classification and the matching comment's url in one line (e.g. `Already raised in the PR conversation: {url}`).

`{{output_dir}}/threads.jsonl` format: `{reuse: [{id, thread_id, url}], confirm: [{thread_id, url, reason}]}` (`thread_id` is the thread's `id`, `url` its first comment's url; a confirm `reason` states in one line the change that removed the problem)

Write every `reason` in the language of the Finding descriptions in `{{document_path}}`.

Return value: `{path, excluded_count, raised, resolved, rejected, reused, confirmed, template_id}` (`path` is the triage.jsonl path; do not include reasons). Include `template_id` exactly as Read from this template's frontmatter.
