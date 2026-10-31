---
name: resolve
description: URL で指定された GitHub プルリクエストに /cgh:review が投稿した指摘をコードに照らして検証し、ユーザーの指示を受けて、結果と確認したコミットを各指摘に返信する。投稿したレビューに作者が対応したか確認するよう求められたときに使う。
allowed-tools: Skill, Agent, Read, Write, Edit, Glob, Grep, Bash(mkdir:*), Bash(git rev-parse:*), Bash(python3 ${CLAUDE_PLUGIN_ROOT}/scripts/gh-review.py:*), Bash(${CLAUDE_PLUGIN_ROOT}/scripts/del-tmp.sh:*)
---

# 投稿済みレビューの検証

`/cgh:review` が投稿した指摘がプルリクエストのヘッドで解決しているかを確認し、返信をユーザーが確認して指示した後に投稿する。

引数が `$ARGUMENTS` なら、プルリクエスト URL（`{pr_url}`）として解釈する。

`${CLAUDE_PLUGIN_ROOT}/rules/leader.md` に従う。その `plugin_root` 変数は `${CLAUDE_PLUGIN_ROOT}`、`{skill}` は `resolve` とする。

## Step 1 — 投稿済みの指摘

`python3 ${CLAUDE_PLUGIN_ROOT}/scripts/gh-review.py prior '{pr_url}' {tmp_dir} --kind review --document {document_path}` を実行する。自分の GitHub アカウントによる `/cgh:review` の指摘を見つけ、`open`（まだ検証されていないもの）と `verified` を出力する。非ゼロ終了なら、そのエラーで中断する。`open` が空なら、確認するものがないことを `verified` の件数とともにユーザーに伝えて終了する。

## Step 2 — 検証

`{document_path}` で `creview:resolve` を実行する。すべての検証サブエージェントへのオーバーライド:

- `For a Resolved finding, begin the verification result in memo_value with [as-recommended] when the code now follows the fix the finding recommends, or [differs] when it is resolved another way or the finding recommends none.`

## Step 3 — 返信

`python3 ${CLAUDE_PLUGIN_ROOT}/scripts/gh-review.py replies '{pr_url}' {tmp_dir} {document_path} --lang {lang}` を実行する。`{tmp_dir}/replies.json` が書き出され、`unverified`（結果が得られなかった指摘）が出力される。

## Step 4 — 確認と投稿

`{json_path}` = `{tmp_dir}/replies.json` で § 確認と投稿 に従う。

## Step 5 — 報告

`posted` と `urls`、Step 3 の `unverified` を報告する。その後終了する。
