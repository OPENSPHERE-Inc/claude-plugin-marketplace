---
name: review-payload
description: Prompt for the sub-agent that composes the review comments to post from the triaged review document in /creview:pr Step 6
template_id: 1c163d5b-2249-4ff2-bb85-5dcce19fe281
---

Compose the pull request review to post from the triaged review document `{{document_path}}`, and Write it to `{{output_path}}`. Read `{{plugin_root}}/rules/sub-agent.md` and observe the common prohibitions.

Selection: every finding in the Critical / Major / Minor sections whose last `Triage` value starts with `🔧 Will Fix`.

Post language: the language of the `title` and `body` of `{{pr_path}}`; `{{doc_lang}}` when the body is empty or its language is unclear.

One comment per selected finding:

- `id`, and `severity` — the finding's section (`Critical` / `Major` / `Minor`).
- `location` — the heading's location; `PR description` is translated into the post language.
- `path` / `line` — from a `file_path:line` location, the path relative to the repository root and the line as an integer (the first line of a range); `line` is null when the location has no line, and both are null for `PR description`.
- `body` — Markdown in the post language: a first line `**{severity}** [{categories}]` with the categories in the post language, then the finding rewritten for the PR author — the problem, its impact, and the direction of a fix. Leave out the finding-id, the reviewer names, and the triage metadata.

Also compose, in the post language, `body` — one or two sentences summarizing the posted findings by severity count — and `outside_diff_heading` — a heading for findings that cannot be anchored in the diff.

`{{output_path}}` format (one JSON object):

```json
{"post_lang": "English", "body": "...", "outside_diff_heading": "...", "comments": [{"id": "M-1", "severity": "Major", "location": "src/a.py:42", "path": "src/a.py", "line": 42, "body": "..."}]}
```

`comments` is an empty array when nothing is selected. Validate the file with `python3 {{plugin_root}}/scripts/check-jsonl.py {{output_path}}`.

Return value: `{path, comment_count, by_severity: {critical, major, minor}, post_lang, template_id}`. Include `template_id` exactly as Read from this template's frontmatter.
