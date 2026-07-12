---
name: comment-review
description: Prompt for comment-sensei to review and fix the comments in a coder's change, engaged by the coder within its code cell in cdev /coding Step 3
template_id: 8004286a-f4b2-4a6a-a3cb-9adc9ea370f2
---

Review the comments the coder added or modified against the discipline in `{{plugin_root}}/rules/comment.md` and fix violations.

Input:

- Changed scope: `{{changed_scope}}` (the files / directories the coder edited). Extract the added or modified comments via the two paths below (markers depend on the language: `//` / `#` / `/* */` / `<!-- -->`, etc.).
  - Tracked files: run `git diff -- {{changed_scope}}` to extract the added or modified comment lines.
  - Untracked (new) files: run `git status --porcelain -uall -- {{changed_scope}}` and list the paths of entries starting with `??`. Since `git diff` does not output untracked files, Read each file and target all comments it contains as added comments.
- Read the design sections in `{{design_paths}}` to understand the intent the code implements, so comment adjustments do not distort it.

Steps:

1. Read `{{plugin_root}}/rules/comment.md`.
2. If there are no added or modified comments, finish with `fix_count: 0`.
3. For comments that violate the discipline (multi-paragraph justifications, trivial what-restatements, chat-context- or porting-history-dependent writing, change-history writing, verbose FIXME / TODO), use Edit to compress, delete, or convert to a short FIXME. Do not change code logic; preserve the substance the code requires.

Report to the requesting coder (the sender of this DM) via SendMessage as a JSON string: `{reviewed_paths, fix_count}`. `reviewed_paths`: files reviewed because added or modified comments were found (may be empty). `fix_count`: number of comments fixed.
