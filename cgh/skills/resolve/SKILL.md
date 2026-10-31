---
name: resolve
description: Verify against the code the findings that /cgh:review posted on a GitHub pull request given by URL, then, on the user's instruction, reply to each with the result and the commit it was checked at. Use when the user asks to check whether the author addressed the review they posted.
allowed-tools: Skill, Agent, Read, Write, Edit, Glob, Grep, Bash(mkdir:*), Bash(git rev-parse:*), Bash(python3 ${CLAUDE_PLUGIN_ROOT}/scripts/gh-review.py:*), Bash(${CLAUDE_PLUGIN_ROOT}/scripts/del-tmp.sh:*)
---

# Posted Review Verification

Check whether the findings `/cgh:review` posted are resolved at the pull request's head, and reply once the user has seen the replies and told you to.

If the argument is `$ARGUMENTS`, interpret it as the pull request URL (`{pr_url}`).

Follow `${CLAUDE_PLUGIN_ROOT}/rules/leader.md`, with its `plugin_root` variable = `${CLAUDE_PLUGIN_ROOT}` and `{skill}` = `resolve`.

## Step 1 — Posted findings

Run `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/gh-review.py prior '{pr_url}' {tmp_dir} --kind review --document {document_path}`. It finds the findings of `/cgh:review` under your GitHub account and prints `open`, those not yet verified, and `verified`. On a non-zero exit, abort with its error. When `open` is empty, tell the user there is nothing to check, with the count of `verified`, and finish.

## Step 2 — Verify

Run `creview:resolve` with `{document_path}`. Override for every verification sub-agent:

- `For a Resolved finding, begin the verification result in memo_value with [as-recommended] when the code now follows the fix the finding recommends, or [differs] when it is resolved another way or the finding recommends none.`

## Step 3 — Replies

Run `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/gh-review.py replies '{pr_url}' {tmp_dir} {document_path} --lang {lang}`. It writes `{tmp_dir}/replies.json` and prints `unverified`, the findings that got no result.

## Step 4 — Confirm and post

Follow § Confirm and post with `{json_path}` = `{tmp_dir}/replies.json`.

## Step 5 — Report

Report `posted` and `urls`, and `unverified` from Step 3. Then finish.
