---
name: respond
description: Triage the reviews posted on a GitHub pull request given by URL, by people or AI alike, with /creview:triage, fix them with /creview:respond once the user confirms, then, after the user has pushed the fixes and told you to, reply to the review comments with what was done and the commit. Use when the user asks to handle the review comments on a pull request.
allowed-tools: Skill, Agent, Read, Write, Edit, Glob, Grep, Bash(mkdir:*), Bash(git rev-parse:*), Bash(python3 ${CLAUDE_PLUGIN_ROOT}/scripts/gh-review.py:*), Bash(${CLAUDE_PLUGIN_ROOT}/scripts/del-tmp.sh:*)
---

# Pull Request Review Response

Triage the pull request's reviews, whoever posted them, fix what is still open once the user confirms, and reply to them once the fixes are on the pull request and the user has told you to.

If the argument is `$ARGUMENTS`, interpret it as the pull request URL (`{pr_url}`) and options.

`--no-confirm` (default OFF) — Go from the triage to the fixes without the user's confirmation. Replies still wait for the user's instruction (§ Confirm and post).

`--trust` (default OFF) — Pass `--trust` to `/creview:triage`, so that a worktree of the pull request has its agent files. `/creview:respond` takes the setting from the document.

`--adr` (default OFF) — Pass `--adr` to `/creview:triage` and `/creview:respond`.

Follow `${CLAUDE_PLUGIN_ROOT}/rules/leader.md`, with its `plugin_root` variable = `${CLAUDE_PLUGIN_ROOT}` and `{skill}` = `respond`. `{document_path}` is the review document `creview:triage` reports, in place of the rule's value.

## Step 1 — Triage and fix

1. Run `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/gh-review.py participants '{pr_url}'`. It prints `viewer`, `author`, and `assignees`. Set `{deciders}` to `assignees`, or to `author` when `assignees` is empty: when the two differ, `assignees` prevail. Follow § Finding IDs, which gives `path`: your findings keep their IDs in the document, and any other finding takes a new one, which the reply posted for it shows. Run `creview:triage` with `{pr_url} --finding-ids '{path}'`, adding `--trust` and `--adr` when given. Overrides:
   - Every `pr-comment-compiler`: `State each claim a reply makes in the finding's description with the login of who made it. When a comment by {viewer} shows the finding's ID, such as **Major M-1**, also set "id" on the finding to that ID. A review whose body opens with a merge gate's verdict heading, a line that starts with ## Merge gate: or ## マージゲート:, whatever words follow, has an overview: the prose after the verdict heading, up to the first of a finding count line, a subheading, and the end of the body. It sums up findings raised elsewhere and is no finding.`
   - Triage sub-agent: `The findings come from comments by anyone, people and AI alike, and each states what the replies to it claim and who claims it. Set 🚫 Won't Fix on a finding already dealt with: (a) the code no longer has the problem: begin the reason with [resolved]; (b) its review was dismissed; (c) one of {deciders} gave a reason and decided not to change it; (d) the reviewer who raised it withdrew it. Say in the reason how it was dealt with, with the login of who said so. What anyone else says is no basis for judging, unless one of {deciders} or that reviewer can be taken to have stated it, as when the pull request's author asks a question, someone answers, and the author accepts the answer. Whenever a reply would change your judgment, check the facts it states against the code, and do not adopt it when the code contradicts them. A claim that it is fixed with nothing in the code behind it does not deal with a finding. Do not add a separate-PR recommendation to these reasons.`

   When it reports that the comments hold no findings, tell the user and finish.
2. Unless `--no-confirm` is given or `maintain` and `alternative` in the triage's compile result are both 0, confirm the fixes:
   - Read `{document_path}` and show the user each finding's ID, location, authors (its reviewers bullet, whose label follows the document's language), and `Triage:` / `Estimate:` lines, with `Cost:`, `Future:`, and `Signals:` left out. Name the ADR files the triage reported, which the user may edit before the fixes. Ask whether to fix the findings, and end your turn.
   - When the user excludes a finding, replace its `Triage:` line with `- **Triage:** 🚫 Won't Fix — {the user's reason, or, with none given, that the user excluded it}`; the reply cites it, so invent no reason. A finding the triage declined or downgraded cannot be added here: say so. Go on only once the user has told you to fix.
   - When the user declines, finish.
3. Run `creview:respond` with `{document_path} --commit`, adding `--adr` when given. Hold its warnings and the findings it left unfixed for Step 5.

## Step 2 — Push

Run `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/gh-review.py fixes '{pr_url}' '{tmp_dir}' '{document_path}'`. It writes `{tmp_dir}/fix-commits.json` and prints `commits`, `branch`, `head_ref`, and `head_repo`.

When `commits` is 0, Read `{document_path}`: when a finding has `Status: 🟢 Fixed`, its fix is uncommitted, so tell the user, post nothing, and continue at Step 5; otherwise continue at Step 3. When `commits` is above 0, show the commits, and ask the user to push them to `head_ref` of `head_repo`, from `branch` when it is not null, and to tell you when that is done. When `head_ref` is null, name no branch and show no command: tell the user to check where to push on the pull request's page. End your turn.

When the user says so, run `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/gh-review.py pushed '{pr_url}' '{tmp_dir}/fix-commits.json'`. When `pushed` is false, tell the user that the pull request does not contain the commits under the hashes the replies would cite (a rebase changes them), and end your turn again. When the user says the commits were rebased or squashed, run this step again from `fixes`. When the user says to stop, post nothing and continue at Step 5.

## Step 3 — Draft the replies

1. Run `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/gh-review.py comments '{pr_url}' '{tmp_dir}'`. It prints `pr_body_path`.
2. Read `{document_path}`, `{tmp_dir}/comments.json`, `{tmp_dir}/fix-commits.json`, `{pr_body_path}`, and `${CLAUDE_PLUGIN_ROOT}/rules/wording.md`, and write `{tmp_dir}/replies.json` as its § Drafted replies says.

## Step 4 — Confirm and post

When there are no replies, continue at Step 5. Otherwise show `unmatched` and `unaddressed` with the preview.

Follow § Confirm and post with `{json_path}` = `{tmp_dir}/replies.json`, passing `post` the option `--commits '{tmp_dir}/fix-commits.json'`: it refuses to send anything until the pull request contains the commits. When `preview` exits non-zero because `{json_path}` is missing or malformed, or prints `comment_lang` as null, write the file again and run it again; abort on a second failure.

## Step 5 — Report

Report `posted` and `urls` when Step 4 posted, `unmatched` from Step 3 when it ran (findings whose comment could not be identified), `unaddressed` (findings that still need action by hand), what Step 1 held, and, from `{document_path}`, the ID, location, authors, and reason of each `🚫 Won't Fix` finding. Then finish.
