---
name: comment-review
description: Prompt for comment-sensei to review comments added or modified by the fix sub-agents (Step 2) against the comment discipline and fix violations in /creview:respond Step 3
template_id: 4a8e2d6f-9b15-4c73-8a2d-7f1e5c9b3d68
---

Review the comments changed by the fix sub-agents (Step 2) in each file against the discipline in `{{plugin_root}}/rules/comment.md` and fix violations. Read `{{plugin_root}}/rules/sub-agent.md` and observe the common prohibitions.

## Input

- Read `{{tmp_dir}}/statuses/*.json` and obtain the list of modified file paths from `items[].path`.
- Read `{{document_path}}` (the review document) to understand the intent of the findings each fix responded to (Finding body, location, triage / estimate metadata). Use it as a reference so comment adjustments do not distort that intent.

## Steps

1. Read `{{plugin_root}}/rules/comment.md`.
2. For each modified file, extract added or modified comment lines from both `git diff HEAD -- {path}` and `git diff HEAD~ -- {path}`. Comment markers depend on the language (`//` / `#` / `/* */` / `<!-- -->`, etc.).
3. If no added or modified comments exist across all files, skip directly to Step 5 (`fix_count: 0`).
4. If extracted added or modified comments violate the discipline in `comment.md` (multi-paragraph justifications, trivial what-restatements, chat-context- or porting-history-dependent writing, change-history writing, verbose FIXME / TODO, etc.), use Edit to either compress, delete, or convert them to FIXME. Do not change code logic.
   - Adjust only the formal violation. Preserve the substance the corresponding finding requires (match the comment to a Finding in `{{document_path}}` by file:line and content) — especially the gist of a FIXME whose direction was specified by an Alternative estimate — and do not distort its intent. When discipline compliance and intent preservation conflict, do not delete; compress or convert to FIXME so the gist remains.
5. Return the result.

## Return value

`{reviewed_paths, fix_count, template_id}`

- `reviewed_paths`: file paths reviewed because added or modified comments were detected (may be empty)
- `fix_count`: number of comments fixed (0 means no comment fixes were applied)

Include `template_id` (Read from this template's frontmatter) verbatim in the return value.
