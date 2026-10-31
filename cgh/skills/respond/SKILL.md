---
name: respond
description: Address the reviews posted on a GitHub pull request given by URL with /creview:triage and /creview:respond, then, after the user has pushed the fixes and told you to, reply to the review comments with what was done and the commit. Use when the user asks to handle the review comments on a pull request.
allowed-tools: Skill, Agent, Read, Write, Edit, Glob, Grep, Bash(mkdir:*), Bash(git rev-parse:*), Bash(python3 ${CLAUDE_PLUGIN_ROOT}/scripts/gh-review.py:*), Bash(${CLAUDE_PLUGIN_ROOT}/scripts/del-tmp.sh:*)
---

# Pull Request Review Response

Fix what the pull request's reviews call for, and reply to them once the fixes are on the pull request and the user has told you to.

If the argument is `$ARGUMENTS`, interpret it as the pull request URL (`{pr_url}`).

Follow `${CLAUDE_PLUGIN_ROOT}/rules/leader.md`, with its `plugin_root` variable = `${CLAUDE_PLUGIN_ROOT}` and `{skill}` = `respond`. `{document_path}` is the review document `creview:triage` reports, in place of the rule's value.

## Step 1 — Triage and fix

1. Run `creview:triage` with `{pr_url}`. When it reports that the comments hold no findings, tell the user and finish.
2. Run `creview:respond` with `{document_path} --commit`. Hold its warnings and the findings it left unfixed for Step 5.

## Step 2 — Push

Run `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/gh-review.py fixes '{pr_url}' {tmp_dir} {document_path}`. It writes `{tmp_dir}/fix-commits.json` and prints `commits`, `branch`, `head_ref`, and `head_repo`.

When `commits` is 0, continue at Step 3. Otherwise show the commits, and ask the user to push them to `head_ref` of `head_repo`, from `branch` when it is not null, and to tell you when that is done. End your turn.

When the user says so, run `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/gh-review.py pushed '{pr_url}' {tmp_dir}/fix-commits.json`. When `pushed` is false, tell the user that the pull request does not contain the commits under the hashes the replies would cite (a rebase changes them), and end your turn again.

## Step 3 — Draft the replies

1. Run `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/gh-review.py comments '{pr_url}' {tmp_dir}`.
2. Launch `Agent(subagent_type="cgh:reply-drafter", prompt=...)`, foreground, with this prompt:

```
As your first action, you MUST Read `${CLAUDE_PLUGIN_ROOT}/skills/respond/templates/reply-draft.md`. Do not perform any other judgment, action, or tool call before the Read completes. After reading, follow its instructions.

Variables (substitute into the template's {{...}} placeholders):
- document_path: {document_path}
- comments_path: {tmp_dir}/comments.json
- commits_path: {tmp_dir}/fix-commits.json
- output_path: {tmp_dir}/replies.json
- doc_lang: {doc_lang}

Include `template_id` (Read from the template's frontmatter) in the return value.
```

The returned `template_id` must be `6f0b2c84-93d1-4e7a-b5c6-1a8e7d42f903`; on mismatch, launch it again, and abort when it happens twice. Return value: `{path, replies, unmatched, template_id}`.

## Step 4 — Confirm and post

Follow § Confirm and post with `{json_path}` = `{tmp_dir}/replies.json`, passing `post` the option `--commits {tmp_dir}/fix-commits.json`: it refuses to send anything until the pull request contains the commits.

## Step 5 — Report

Report `posted` and `urls`, `unmatched` from Step 3 (findings whose comment the drafter could not identify), and what Step 1 held. Then finish.
