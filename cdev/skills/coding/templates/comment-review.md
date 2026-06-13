---
name: comment-review
description: Prompt for comment-sensei to review comments added or modified by the coders against the comment discipline and fix violations in cdev /coding Step 6
template_id: 8004286a-f4b2-4a6a-a3cb-9adc9ea370f2
---

Review the comments added or modified by the coders against the discipline in `{{plugin_root}}/rules/comment.md` and fix violations.

Input:

- Read `{{diff_path}}` (the current working-tree diff) and use it to extract added or modified comment lines per file.
- Read the design sections in `{{design_paths}}` to understand the intent the code implements, so comment adjustments do not distort it.

Steps:

1. Read `{{plugin_root}}/rules/comment.md`.
2. From `{{diff_path}}`, extract the added or modified comments per file (markers depend on the language: `//` / `#` / `/* */` / `<!-- -->`, etc.).
3. If there are none across all files, finish with `fix_count: 0`.
4. For comments that violate the discipline (multi-paragraph justifications, trivial what-restatements, chat-context- or porting-history-dependent writing, change-history writing, verbose FIXME / TODO), use Edit to compress, delete, or convert to a short FIXME. Do not change code logic; preserve the substance the code requires.

Report to the leader (via SendMessage): `{reviewed_paths, fix_count}`. `reviewed_paths`: files reviewed because added or modified comments were found (may be empty). `fix_count`: number of comments fixed. Mark the task done via TaskUpdate.
