---
name: resolve
description: URL で指定された GitHub プルリクエストに /cgh:review が投稿した指摘をコードに照らして検証し、ユーザーの指示を受けて、結果と確認したコミットを各指摘に返信する。投稿したレビューに作者が対応したか確認するよう求められたときに使う。
allowed-tools: Skill, Agent, Read, Write, Edit, Glob, Grep, Bash(mkdir:*), Bash(git rev-parse:*), Bash(python3 ${CLAUDE_PLUGIN_ROOT}/scripts/gh-review.py:*), Bash(${CLAUDE_PLUGIN_ROOT}/scripts/del-tmp.sh:*)
---

# 投稿済みレビューの検証

`/cgh:review` が投稿した指摘がプルリクエストのヘッドで解決しているかを確認し、返信をユーザーが確認して指示した後に投稿する。

引数が `$ARGUMENTS` なら、プルリクエスト URL（`{pr_url}`）とオプションとして解釈する。

`--trust`（デフォルト OFF）— `gh-review.py prior` に `--trust` を渡し、プルリクエストの worktree がエージェントファイルを持つようにする。`/creview:resolve` はこの設定を、`prior` が書くドキュメントから受け取る。

`${CLAUDE_PLUGIN_ROOT}/rules/leader.md` に従う。その `plugin_root` 変数は `${CLAUDE_PLUGIN_ROOT}`、`{skill}` は `resolve` とする。

## Step 1 — 投稿済みの指摘

`python3 ${CLAUDE_PLUGIN_ROOT}/scripts/gh-review.py prior '{pr_url}' {tmp_dir} --kind review --document {document_path}` を実行する。`--trust` が指定されていれば追加する。自分の GitHub アカウントによる `/cgh:review` の指摘を見つけ、`open`（まだ検証されていないもの。検証の対象外である Info を除く）と `verified` を出力する。非ゼロ終了なら、そのエラーで中断する。`open` が空なら、確認するものがないことを `verified` の件数とともにユーザーに伝えて終了する。

## Step 2 — 検証

`{document_path}` で `creview:resolve` を実行する。すべての検証サブエージェントへのオーバーライド:

- `Resolved の指摘では、コードが指摘の推奨する修正に従うようになっていれば memo_value の検証結果を [as-recommended] で始め、別の方法で解決しているか指摘が修正を推奨していなければ [differs] で始める。`
- `検証結果の文面を {doc_lang} で書く。`

## Step 3 — 返信

`python3 ${CLAUDE_PLUGIN_ROOT}/scripts/gh-review.py replies '{pr_url}' {tmp_dir} {document_path} --lang {lang}` を実行する。`{tmp_dir}/replies.json` が書き出され、`replies`、`unverified`（結果が得られなかった指摘）、`pr_body_path` が出力される。`replies` が 0 なら、担当を起動せず Step 5 に進む。

返信は PR 本文の言語で投稿する。`Agent(subagent_type="cgh:comment-writer", prompt=...)` を起動する:

```
最初の行動として `${CLAUDE_PLUGIN_ROOT}/skills/resolve/templates/reply-translate.md` を必ず Read する。Read 完了前に他の判断・行動・ツール呼び出しを行わない。Read 後はその指示に従う。

変数（テンプレート中の {{...}} placeholder を置換）:
- replies_path: {tmp_dir}/replies.json
- pr_body_path: {pr_body_path}
- output_path: {tmp_dir}/wording-1.json

戻り値に `template_id`（テンプレートの frontmatter から Read）を含める。
```

返される `template_id` は `c41e8f37-2a95-4d6b-8b10-93e7a5d1c6f2` でなければならない。不一致なら再度起動し、2 回続いたら中断する。その後、`python3 ${CLAUDE_PLUGIN_ROOT}/scripts/gh-review.py wording '{pr_url}' {tmp_dir}/replies.json` を実行する。

## Step 4 — 確認と投稿

`{json_path}` = `{tmp_dir}/replies.json` で § 確認と投稿 に従う。

## Step 5 — 報告

`posted` と `urls`、Step 3 の `unverified` を報告する。その後終了する。
