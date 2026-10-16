---
name: review-payload
description: Prompt for the sub-agent that composes the review comments and fix confirmations to post from the triaged review document in /creview:pr Step 6
template_id: 1c163d5b-2249-4ff2-bb85-5dcce19fe281
---

Compose the pull request review to post from the triaged review document `{{document_path}}` and the thread list `{{threads_path}}`, and Write it to `{{output_path}}`. Read `{{plugin_root}}/rules/sub-agent.md` and observe the common prohibitions. Restrict tool use to Read, Write for `{{output_path}}`, and Bash only to run `check-jsonl.py`.

`{{threads_path}}` is `{reuse: [{id, thread_id, url}], confirm: [{thread_id, url, reason}]}`; treat both lists as empty when it is `(none)`.

Selection: every finding in the Critical / Major / Minor sections whose last `Triage` value starts with `🔧 Will Fix`.

Post language: the language of the `title` and `body` of `{{pr_path}}`; `{{doc_lang}}` when the body is empty or its language is unclear.

One comment per selected finding:

- `id`, and `severity` — the finding's section (`Critical` / `Major` / `Minor`).
- `location` — the heading's location; `PR description` is translated into the post language.
- `path` / `line` — from a `file_path:line` location, the path relative to the repository root and the line as an integer (the first line of a range); `line` is null when the location has no line, and both are null for `PR description`.
- `thread_id` / `thread_url` — the `thread_id` and `url` of the finding's `reuse` entry, so that the comment is posted as a reply in that thread; both null when it has none.
- `body` — Markdown in the post language: a first line `**{id} {severity}** [{categories}]` (e.g. `**M-1 Major** [Security]`; `{id}` is the finding-id as written in the review document, and the categories are in the post language), then the finding rewritten for the PR author — the problem, its impact, and the direction of a fix. Leave out the reviewer names and the triage metadata. Base it only on the finding: write no absolute local path (use repository-relative paths), no content from files outside the pull request, and no credential or secret-looking string.

One confirmation per `confirm` entry: its `thread_id` and `url`, and a `body` of one or two sentences in the post language saying the problem the thread reported is confirmed fixed at the PR head, based on its `reason`.

Also compose, in the post language, `body` — one or two sentences summarizing the posted findings by severity count and the number of confirmations — and `outside_diff_heading` — a heading for findings that cannot be anchored in the diff.

`{{output_path}}` format (one JSON object):

```json
{"post_lang": "English", "body": "...", "outside_diff_heading": "...", "comments": [{"id": "M-1", "severity": "Major", "location": "src/a.py:42", "path": "src/a.py", "line": 42, "thread_id": null, "thread_url": null, "body": "..."}], "confirmations": [{"thread_id": "PRRT_...", "url": "...", "body": "..."}]}
```

`comments` and `confirmations` are empty arrays when nothing is selected or listed. Validate the file with `python3 {{plugin_root}}/scripts/check-jsonl.py {{output_path}}`.

Return value: `{path, comment_count, confirmation_count, by_severity: {critical, major, minor}, post_lang, template_id}`. Include `template_id` exactly as Read from this template's frontmatter.
