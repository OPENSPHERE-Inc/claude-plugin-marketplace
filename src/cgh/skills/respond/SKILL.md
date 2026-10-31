---
name: respond
description: URL で指定された GitHub プルリクエストに投稿されたレビューに /creview:triage と /creview:respond で対応し、ユーザーが修正を push して指示した後に、対応内容とコミットをレビューコメントへ返信する。プルリクエストのレビューコメントへの対応を求められたときに使う。
allowed-tools: Skill, Agent, Read, Write, Edit, Glob, Grep, Bash(mkdir:*), Bash(git rev-parse:*), Bash(python3 ${CLAUDE_PLUGIN_ROOT}/scripts/gh-review.py:*), Bash(${CLAUDE_PLUGIN_ROOT}/scripts/del-tmp.sh:*)
---

# プルリクエストレビューへの対応

プルリクエストのレビューが求める修正を行い、修正がプルリクエストに載ってユーザーが指示した後に返信する。

引数が `$ARGUMENTS` なら、プルリクエスト URL（`{pr_url}`）として解釈する。

`${CLAUDE_PLUGIN_ROOT}/rules/leader.md` に従う。その `plugin_root` 変数は `${CLAUDE_PLUGIN_ROOT}`、`{skill}` は `respond` とする。`{document_path}` はルールの値に代えて、`creview:triage` が報告するレビュードキュメントとする。

## Step 1 — トリアージと修正

1. `{pr_url}` で `creview:triage` を実行する。コメントに指摘がないと報告されたら、ユーザーに伝えて終了する。
2. `{document_path} --commit` で `creview:respond` を実行する。その警告と未修正の指摘を Step 5 のために保持する。

## Step 2 — push

`python3 ${CLAUDE_PLUGIN_ROOT}/scripts/gh-review.py fixes '{pr_url}' {tmp_dir} {document_path}` を実行する。`{tmp_dir}/fix-commits.json` が書き出され、`commits`、`branch`、`head_ref`、`head_repo` が出力される。

`commits` が 0 なら Step 3 に進む。それ以外は、コミットを示し、`head_repo` の `head_ref` へ（`branch` が null でなければそこから）push して完了を知らせるようユーザーに依頼する。ターンを終える。

ユーザーが完了を伝えたら、`python3 ${CLAUDE_PLUGIN_ROOT}/scripts/gh-review.py pushed '{pr_url}' {tmp_dir}/fix-commits.json` を実行する。`pushed` が false なら、返信が引用するハッシュのコミットがプルリクエストに含まれていないこと（リベースするとハッシュが変わる）をユーザーに伝え、再びターンを終える。

## Step 3 — 返信のドラフト

1. `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/gh-review.py comments '{pr_url}' {tmp_dir}` を実行する。
2. `Agent(subagent_type="cgh:reply-drafter", prompt=...)` をフォアグラウンドで次のプロンプトで起動する:

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

返される `template_id` は `6f0b2c84-93d1-4e7a-b5c6-1a8e7d42f903` でなければならない。不一致なら再度起動し、2 回続いたら中断する。戻り値: `{path, replies, unmatched, template_id}`。

## Step 4 — 確認と投稿

`{json_path}` = `{tmp_dir}/replies.json` で § 確認と投稿 に従い、`post` にオプション `--commits {tmp_dir}/fix-commits.json` を渡す: プルリクエストがコミットを含むまで何も送らない。

## Step 5 — 報告

`posted` と `urls`、Step 3 の `unmatched`（ドラフト担当がコメントを特定できなかった指摘）、Step 1 で保持した内容を報告する。その後終了する。
