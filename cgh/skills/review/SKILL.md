---
name: review
description: Review a GitHub pull request given by URL with /creview:start and /creview:triage, then, on the user's instruction, post the findings to it as a Request Changes or Comment review. Use when the user asks to review a pull request and post the review on GitHub. It never approves.
allowed-tools: Skill, Agent, Read, Write, Edit, Glob, Grep, Bash(mkdir:*), Bash(git rev-parse:*), Bash(python3 ${CLAUDE_PLUGIN_ROOT}/scripts/gh-review.py:*), Bash(${CLAUDE_PLUGIN_ROOT}/scripts/del-tmp.sh:*)
---

# Pull Request Review

Review a pull request, and post the triaged findings once the user has seen them and told you to. Whether the pull request is good to merge is the user's call: state no LGTM or approval.

If the argument is `$ARGUMENTS`, interpret it as the pull request URL (`{pr_url}`) and options.

`--adversarial` (default OFF) — Pass `--adversarial` to `/creview:start`.

`--trust` (default OFF) — Pass `--trust` to `/creview:start`, so that a worktree of the pull request has its agent files.

`--adr` (default OFF) — Pass `--adr` to `/creview:triage`.

Follow `${CLAUDE_PLUGIN_ROOT}/rules/leader.md`, with its `plugin_root` variable = `${CLAUDE_PLUGIN_ROOT}` and `{skill}` = `review`.

## Step 1 — Review and triage

1. Run `creview:start` with `{pr_url} --output {document_path}`, adding `--adversarial` and `--trust` when given.
2. When it reports no findings, tell the user there is nothing to post and finish.
3. Run `creview:triage` with `{document_path}`, adding `--adr` when given.

## Step 2 — Draft

Run `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/gh-review.py draft '{pr_url}' {tmp_dir} {document_path} --kind review --lang {lang}`. It writes `{tmp_dir}/draft.json`. Then follow § Comment wording with `{json_path}` = `{tmp_dir}/draft.json`.

## Step 3 — Confirm and post

Follow § Confirm and post with `{json_path}` = `{tmp_dir}/draft.json`. Select an Info finding only when the user tells you to. With no finding selected, say so when you show the preview: `post` refuses to send nothing.

The script computes the event and each finding's place from `{json_path}`: do not choose them yourself.

## Step 4 — Report

Report `review_url`, `event`, and the IDs in `fallbacks` (GitHub refused their place, so they went on the file or into the body). When `recovered_from` is not null, add that error: the call failed but the review went out. When `own_pr` is true and the findings called for Request Changes, add that GitHub refuses it on your own pull request, so it went out as Comment. Then finish.
