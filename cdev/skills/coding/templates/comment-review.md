---
name: comment-review
description: Prompt for comment-sensei to review and fix the comments in a coder's change, engaged by the coder within its code cell in cdev /coding Step 3
template_id: 8004286a-f4b2-4a6a-a3cb-9adc9ea370f2
---

Review the comments the coder added or modified against the discipline in `{{plugin_root}}/rules/comment.md` and fix violations.

Input:

- Changed scope: `{{changed_scope}}` (the files / directories the coder edited). Extract every comment added or modified there, covering tracked and untracked files alike — `git diff` does not output untracked files, so a new file's comments are all "added" and have to be picked up separately. Comment markers depend on the language (`//` / `#` / `/* */` / `<!-- -->`, etc.).
- Read the design sections in `{{design_paths}}` to understand the intent the code implements, so comment adjustments do not distort it.

Steps:

1. Read `{{plugin_root}}/rules/comment.md`.
2. If there are no added or modified comments, finish by reporting 0 fixes.
3. For comments that violate the discipline (multi-paragraph justifications, trivial what-restatements, chat-context- or porting-history-dependent writing, change-history writing, verbose FIXME / TODO), use Edit to compress, delete, or convert to a short FIXME. Do not change code logic; preserve the substance the code requires.

Report to the requesting coder (the sender of this DM) via SendMessage: the paths you reviewed because added or modified comments were found (may be none) and the number of comments fixed.
