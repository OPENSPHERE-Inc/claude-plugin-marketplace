---
name: respond
description: URL で指定された GitHub プルリクエストに投稿されたレビューを /creview:triage でトリアージし、ユーザーの確認後に /creview:respond で修正して、ユーザーが修正を push して指示した後に、対応内容とコミットをレビューコメントへ返信する。プルリクエストのレビューコメントへの対応を求められたときに使う。
allowed-tools: Skill, Agent, Read, Write, Edit, Glob, Grep, Bash(mkdir:*), Bash(git rev-parse:*), Bash(python3 ${CLAUDE_PLUGIN_ROOT}/scripts/gh-review.py:*), Bash(${CLAUDE_PLUGIN_ROOT}/scripts/del-tmp.sh:*)
---

# プルリクエストレビューへの対応

プルリクエストのレビューをトリアージし、ユーザーの確認後にレビューが求める修正を行い、修正がプルリクエストに載ってユーザーが指示した後に返信する。

引数が `$ARGUMENTS` なら、プルリクエスト URL（`{pr_url}`）とオプションとして解釈する。

`--no-confirm`（デフォルト OFF）— ユーザーの確認なしでトリアージから修正へ進む。返信はそれでもユーザーの指示を待つ（§ 確認と投稿）。

`--trust`（デフォルト OFF）— `/creview:triage` に `--trust` を渡し、プルリクエストの worktree がエージェントファイルを持つようにする。`/creview:respond` はこの設定をドキュメントから受け取る。

`--adr`（デフォルト OFF）— `/creview:triage` と `/creview:respond` に `--adr` を渡す。

`${CLAUDE_PLUGIN_ROOT}/rules/leader.md` に従う。その `plugin_root` 変数は `${CLAUDE_PLUGIN_ROOT}`、`{skill}` は `respond` とする。`{document_path}` はルールの値に代えて、`creview:triage` が報告するレビュードキュメントとする。

## Step 1 — トリアージと修正

1. `{pr_url}` で `creview:triage` を実行する。`--trust` と `--adr` が指定されていれば追加する。コメントに指摘がないと報告されたら、ユーザーに伝えて終了する。
2. `--no-confirm` が指定されているか、トリアージの compile 結果の `maintain` と `alternative` がともに 0 である場合を除き、修正を確認する:
   - `{document_path}` を Read し、各指摘の ID、場所、作者（その reviewers の項目。ラベルはドキュメントの言語による）、`Triage:` / `Estimate:` 行を、`Cost:`、`Future:`、`Signals:` を除いてユーザーに示す。トリアージが報告した ADR ファイルを挙げる（ユーザーは修正の前に編集できる）。修正してよいか尋ね、ターンを終える。
   - ユーザーが指摘を除外したら、その `Triage:` 行を `- **Triage:** 🚫 Won't Fix — {ユーザーの理由。なければユーザーが除外した旨}` に置き換える。返信がこれを引用するので、理由を創作しない。トリアージが却下した指摘や Downgrade された指摘はここでは追加できない: その旨を伝える。ユーザーが修正を指示してから先へ進む。
   - ユーザーが断ったら終了する。
3. `{document_path} --commit` で `creview:respond` を実行する。`--adr` が指定されていれば追加する。その警告と未修正の指摘を Step 5 のために保持する。

## Step 2 — push

`python3 ${CLAUDE_PLUGIN_ROOT}/scripts/gh-review.py fixes '{pr_url}' {tmp_dir} {document_path}` を実行する。`{tmp_dir}/fix-commits.json` が書き出され、`commits`、`branch`、`head_ref`、`head_repo` が出力される。

`commits` が 0 なら Step 3 に進む。それ以外は、コミットを示し、`head_repo` の `head_ref` へ（`branch` が null でなければそこから）push して完了を知らせるようユーザーに依頼する。`head_ref` が null なら、ブランチ名もコマンドも示さず、push 先をプルリクエストのページで確認するよう伝える。ターンを終える。

ユーザーが完了を伝えたら、`python3 ${CLAUDE_PLUGIN_ROOT}/scripts/gh-review.py pushed '{pr_url}' {tmp_dir}/fix-commits.json` を実行する。`pushed` が false なら、返信が引用するハッシュのコミットがプルリクエストに含まれていないこと（リベースするとハッシュが変わる）をユーザーに伝え、再びターンを終える。コミットをリベースまたはスカッシュしたとユーザーが伝えたら、`fixes` からこのステップをやり直す。やめるとユーザーが伝えたら、何も投稿せずに終了する。

## Step 3 — 返信のドラフト

1. `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/gh-review.py comments '{pr_url}' {tmp_dir}` を実行する。`pr_body_path` が出力される。
2. `Agent(subagent_type="cgh:reply-drafter", prompt=...)` をフォアグラウンドで次のプロンプトで起動する:

```
最初の行動として `${CLAUDE_PLUGIN_ROOT}/skills/respond/templates/reply-draft.md` を必ず Read する。Read 完了前に他の判断・行動・ツール呼び出しを行わない。Read 後はその指示に従う。

変数（テンプレート中の {{...}} placeholder を置換）:
- document_path: {document_path}
- comments_path: {tmp_dir}/comments.json
- commits_path: {tmp_dir}/fix-commits.json
- pr_body_path: {pr_body_path}
- output_path: {tmp_dir}/replies.json
- doc_lang: {doc_lang}

戻り値に `template_id`（テンプレートの frontmatter から Read）を含める。
```

返される `template_id` は `6f0b2c84-93d1-4e7a-b5c6-1a8e7d42f903` でなければならない。不一致なら再度起動し、2 回続いたら中断する。戻り値: `{path, replies, unmatched, template_id}`。

## Step 4 — 確認と投稿

ドラフト担当が返した `replies` が 0 なら Step 5 に進む。それ以外は、その `unmatched` をプレビューとともに示す。

`{json_path}` = `{tmp_dir}/replies.json` で § 確認と投稿 に従い、`post` にオプション `--commits {tmp_dir}/fix-commits.json` を渡す: プルリクエストがコミットを含むまで何も送らない。`{json_path}` の欠落または不正で `preview` が非ゼロ終了したら、Step 3 のドラフト担当をもう一度起動して再実行し、2 回目の失敗で中断する。ファイルを自分で修復しない: その文面はプルリクエストに由来する。

## Step 5 — 報告

`posted` と `urls`、Step 3 の `unmatched`（ドラフト担当がコメントを特定できなかった指摘）、Step 1 で保持した内容を報告する。その後終了する。
