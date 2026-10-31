---
name: resolve
description: Verify against the code the findings that /cgh:review posted on a GitHub pull request given by URL, then, on the user's instruction, reply to each with the result and the commit it was checked at. Use when the user asks to check whether the author addressed the review they posted.
allowed-tools: Skill, Agent, Read, Write, Edit, Glob, Grep, Bash(mkdir:*), Bash(git rev-parse:*), Bash(python3 ${CLAUDE_PLUGIN_ROOT}/scripts/gh-review.py:*), Bash(${CLAUDE_PLUGIN_ROOT}/scripts/del-tmp.sh:*)
---

# Posted Review Verification

Check whether the findings `/cgh:review` posted are resolved at the pull request's head, and reply once the user has seen the replies and told you to.

If the argument is `$ARGUMENTS`, interpret it as the pull request URL (`{pr_url}`) and options.

`--trust` (default OFF) — Pass `--trust` to `gh-review.py prior`, so that a worktree of the pull request has its agent files. `/creview:resolve` takes the setting from the document it writes.

Follow `${CLAUDE_PLUGIN_ROOT}/rules/leader.md`, with its `plugin_root` variable = `${CLAUDE_PLUGIN_ROOT}` and `{skill}` = `resolve`.

## Step 1 — Posted findings

Run `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/gh-review.py prior '{pr_url}' {tmp_dir} --kind review --document {document_path}`, adding `--trust` when given. It finds the findings of `/cgh:review` under your GitHub account and prints `open`, those not yet verified, and `verified`. On a non-zero exit, abort with its error. When `open` is empty, tell the user there is nothing to check, with the count of `verified`, and finish.

## Step 2 — Verify

Run `creview:resolve` with `{document_path}`. Override for every verification sub-agent:

- `For a Resolved finding, begin the verification result in memo_value with [as-recommended] when the code now follows the fix the finding recommends, or [differs] when it is resolved another way or the finding recommends none.`
- `Write the verification text in {doc_lang}.`

## Step 3 — Replies

Run `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/gh-review.py replies '{pr_url}' {tmp_dir} {document_path} --lang {lang}`. It writes `{tmp_dir}/replies.json` and prints `unverified`, the findings that got no result, and `pr_body_path`.

Replies go out in the language of the pull request's description. Launch `Agent(subagent_type="cgh:comment-writer", prompt=...)`:

```
As your first action, you MUST Read `${CLAUDE_PLUGIN_ROOT}/skills/resolve/templates/reply-translate.md`. Do not perform any other judgment, action, or tool call before the Read completes. After reading, follow its instructions.

Variables (substitute into the template's {{...}} placeholders):
- replies_path: {tmp_dir}/replies.json
- pr_body_path: {pr_body_path}
- output_path: {tmp_dir}/wording-1.json

Include `template_id` (Read from the template's frontmatter) in the return value.
```

The returned `template_id` must be `c41e8f37-2a95-4d6b-8b10-93e7a5d1c6f2`; on mismatch, launch it again, and abort when it happens twice. Then run `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/gh-review.py wording '{pr_url}' {tmp_dir}/replies.json`.

## Step 4 — Confirm and post

Follow § Confirm and post with `{json_path}` = `{tmp_dir}/replies.json`.

## Step 5 — Report

Report `posted` and `urls`, and `unverified` from Step 3. Then finish.
