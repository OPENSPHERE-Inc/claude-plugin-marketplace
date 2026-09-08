---
name: comment-review
description: Prompt for comment-sensei to review comments added or modified by the fix sub-agents (Step 2) against the comment discipline and the FIXME basis rule, and fix violations, in /creview:respond Step 3
template_id: 4a8e2d6f-9b15-4c73-8a2d-7f1e5c9b3d68
---

Review the comments changed by the fix sub-agents (Step 2) in each file against the discipline in `{{plugin_root}}/rules/comment.md` and fix violations. Do not change code logic. Read `{{plugin_root}}/rules/sub-agent.md` and observe the common prohibitions.

## Input

- Read `{{diff_path}}` (`fetch-diff.sh` output; the current fix diff) and use it as the source for extracting added or modified comments.
- Read `{{document_path}}` (the review document) to understand the intent of the findings each fix responded to (Finding body, location, triage / estimate metadata). Use it as a reference so comment adjustments do not distort that intent.

## Steps

1. Read `{{plugin_root}}/rules/comment.md`.
2. From `{{diff_path}}`, extract the added or modified comment lines for each file it contains. Comment markers depend on the language (`//` / `#` / `/* */` / `<!-- -->`, etc.).
3. If no added or modified comments exist across all files, skip directly to Step 6 (`fix_count: 0`).
4. Check the basis of every added or modified `FIXME:` / `TODO:`. In code such an annotation stands permanently as grounds for excluding that spot from review — a deferral whose problem and direction are on record — so it is allowed only when one of the following holds:
   - It is the FIXME whose insertion a finding with `Estimate:` 🚧 Alternative in `{{document_path}}` directed (match by file:line and content).
   - It records a design decision already settled in the destination project (CLAUDE.md, an ADR, an existing comment at the same location).
   Delete every other one with Edit, including one a fix sub-agent wrote on its own judgment for a residual gap it noticed while fixing.
5. If extracted added or modified comments violate the discipline in `comment.md` (multi-paragraph justifications, trivial what-restatements, chat-context- or porting-history-dependent writing, change-history writing, verbose FIXME / TODO, etc.), use Edit to compress or delete them, or convert them to FIXME when Step 4's basis holds.
   - Adjust only the formal violation. Preserve the substance the corresponding finding requires (match the comment to a Finding in `{{document_path}}` by file:line and content) — especially the gist of a FIXME whose direction was specified by an Alternative estimate — and do not distort its intent. When discipline compliance and intent preservation conflict, do not delete; compress it so the gist remains.
6. Return the result.

## Return value

`{reviewed_paths, fix_count, template_id}`

- `reviewed_paths`: file paths reviewed because added or modified comments were detected (may be empty)
- `fix_count`: number of comments fixed, counting the annotations deleted in Step 4 (0 means no comment fixes were applied)

Include `template_id` (Read from this template's frontmatter) verbatim in the return value.
