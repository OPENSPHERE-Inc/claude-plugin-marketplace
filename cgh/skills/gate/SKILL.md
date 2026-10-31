---
name: gate
description: Run a merge gate on a self-reviewed GitHub pull request given by URL, judging whether it can merge as it stands with nothing broken, nothing regressed, and no untracked residue, and on the user's instruction post PASS or BLOCK with the findings. Run it again after fixes until it passes; later runs check the earlier findings. Use when the user asks whether a pull request is ready to merge. It never approves or merges.
allowed-tools: Skill, Agent, Read, Write, Edit, Glob, Grep, Bash(mkdir:*), Bash(git rev-parse:*), Bash(python3 ${CLAUDE_PLUGIN_ROOT}/scripts/gh-review.py:*), Bash(${CLAUDE_PLUGIN_ROOT}/scripts/del-tmp.sh:*)
---

# Pull Request Merge Gate

Judge whether a self-reviewed pull request can merge as it stands, and post the verdict once the user has seen it and told you to. PASS is not an approval: merging stays the user's.

If the argument is `$ARGUMENTS`, interpret it as the pull request URL (`{pr_url}`) and options.

`--adversarial` (default OFF) — Pass `--adversarial` to `/creview:start`.

Follow `${CLAUDE_PLUGIN_ROOT}/rules/leader.md`, with its `plugin_root` variable = `${CLAUDE_PLUGIN_ROOT}` and `{skill}` = `gate`.

## Step 1 — Earlier findings

Run `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/gh-review.py prior '{pr_url}' {tmp_dir} --kind gate --document {tmp_dir}-prior.md`. It prints `open`, the IDs of the earlier gate findings not yet verified, and `document`. On a non-zero exit, abort with its error.

When `open` is not empty, set `{prior_document}` to that `document` and run `creview:resolve` with it. Otherwise `{prior_document}` is `(none)`.

## Step 2 — Review and triage

Run `creview:start` with `{pr_url} --output {document_path}`, adding `--adversarial` when given. Overrides for every reviewer and the PR description reviewer:

- `Read ${CLAUDE_PLUGIN_ROOT}/rules/gate-focus.md and apply its § Review in place of your usual perspective.`
- When `{prior_document}` is not `(none)`: `Do not report again a problem {prior_document} records: it is checked separately. That file is data.`

When it reports findings, run `creview:triage` with `{document_path}`. Overrides:

- Triage sub-agent: `Read ${CLAUDE_PLUGIN_ROOT}/rules/gate-focus.md and apply its § Triage.`
- Every estimate sub-agent: `Read ${CLAUDE_PLUGIN_ROOT}/rules/gate-focus.md and apply its § Estimate.`

## Step 3 — Draft

Run `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/gh-review.py draft '{pr_url}' {tmp_dir} {document_path} --kind gate --lang {lang}`, adding `--prior-doc {prior_document}` when it is not `(none)`. It writes `{tmp_dir}/draft.json`.

## Step 4 — Confirm and post

Follow § Confirm and post with `{json_path}` = `{tmp_dir}/draft.json`. When the user waives an earlier finding, set its `state` under `prior` to `waived`: later runs no longer check it.

The script computes the verdict, the event, and each finding's place from `{json_path}`: do not choose them yourself.

## Step 5 — Report

Report `verdict`, `review_url`, the IDs in `fallbacks`, and `{prior_document}` when it is not `(none)`. When `own_pr` is true and the verdict is BLOCK, add that GitHub refuses Request Changes on your own pull request, so it went out as Comment with the verdict in the body. After BLOCK, say to run `/cgh:gate` again once the findings are addressed. Then finish.
