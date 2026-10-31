---
name: review
description: URL で指定された GitHub プルリクエストを /creview:start と /creview:triage でレビューし、ユーザーの指示を受けて指摘を Request Changes または Comment のレビューとして投稿する。プルリクエストをレビューして GitHub に投稿するよう求められたときに使う。承認は行わない。
allowed-tools: Skill, Agent, Read, Write, Edit, Glob, Grep, Bash(mkdir:*), Bash(git rev-parse:*), Bash(python3 ${CLAUDE_PLUGIN_ROOT}/scripts/gh-review.py:*), Bash(${CLAUDE_PLUGIN_ROOT}/scripts/del-tmp.sh:*)
---

# プルリクエストレビュー

プルリクエストをレビューし、トリアージ済みの指摘をユーザーが確認して指示した後に投稿する。マージしてよいかの判断はユーザーが行う: LGTM や承認を述べない。

引数が `$ARGUMENTS` なら、プルリクエスト URL（`{pr_url}`）とオプションとして解釈する。

`--adversarial`（デフォルト OFF）— `/creview:start` に `--adversarial` を渡す。

`--trust`（デフォルト OFF）— `/creview:start` に `--trust` を渡し、プルリクエストの worktree がエージェントファイルを持つようにする。

`--adr`（デフォルト OFF）— `/creview:triage` に `--adr` を渡す。

`${CLAUDE_PLUGIN_ROOT}/rules/leader.md` に従う。その `plugin_root` 変数は `${CLAUDE_PLUGIN_ROOT}`、`{skill}` は `review` とする。

## Step 1 — レビューとトリアージ

1. `{pr_url} --output {document_path}` で `creview:start` を実行する。`--adversarial` と `--trust` が指定されていれば追加する。
2. 指摘なしと報告されたら、投稿するものがないとユーザーに伝えて終了する。
3. `{document_path}` で `creview:triage` を実行する。`--adr` が指定されていれば追加する。

## Step 2 — ドラフト

`python3 ${CLAUDE_PLUGIN_ROOT}/scripts/gh-review.py draft '{pr_url}' {tmp_dir} {document_path} --kind review --lang {lang}` を実行する。`{tmp_dir}/draft.json` が書き出される。その後、`{json_path}` = `{tmp_dir}/draft.json` で § コメントの文面 に従う。

## Step 3 — 確認と投稿

`{json_path}` = `{tmp_dir}/draft.json` で § 確認と投稿 に従う。Info の指摘はユーザーが指示したときだけ選択する。選択された指摘がなければ、プレビューを示すときにそう伝える: `post` は何も送らない投稿を拒否する。

イベントと各指摘の投稿先はスクリプトが `{json_path}` から算出する: 自分で選ばない。

## Step 4 — 報告

`review_url`、`event`、`fallbacks` の ID（GitHub が投稿先を拒否したためファイルまたは本文に回った指摘）を報告する。`recovered_from` が null でなければ、その呼び出しは失敗したがレビューは投稿されたとしてそのエラーを添える。`own_pr` が true で指摘が Request Changes を求めていたなら、GitHub は自分のプルリクエストへの Request Changes を拒否するため Comment で送ったことを添える。その後終了する。
