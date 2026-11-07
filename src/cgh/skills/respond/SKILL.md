---
name: respond
description: URL で指定された GitHub プルリクエストに人間や AI が投稿したレビューを /creview:triage でトリアージし、ユーザーの確認後に /creview:respond で修正して、ユーザーが修正を push して指示した後に、対応内容とコミットをレビューコメントへ返信する。プルリクエストのレビューコメントへの対応を求められたときに使う。
allowed-tools: Skill, Agent, Read, Write, Edit, Glob, Grep, Bash(mkdir:*), Bash(git rev-parse:*), Bash(python3 ${CLAUDE_PLUGIN_ROOT}/scripts/gh-review.py:*), Bash(${CLAUDE_PLUGIN_ROOT}/scripts/del-tmp.sh:*)
---

# プルリクエストレビューへの対応

誰が投稿したかを問わずプルリクエストのレビューをトリアージし、ユーザーの確認後に未対応のものを修正し、修正がプルリクエストに載ってユーザーが指示した後に返信する。

引数が `$ARGUMENTS` なら、プルリクエスト URL（`{pr_url}`）とオプションとして解釈する。

`--no-confirm`（デフォルト OFF）— ユーザーの確認なしでトリアージから修正へ進む。返信はそれでもユーザーの指示を待つ（§ 確認と投稿）。

`--trust`（デフォルト OFF）— `/creview:triage` に `--trust` を渡し、プルリクエストの worktree がエージェントファイルを持つようにする。`/creview:respond` はこの設定をドキュメントから受け取る。

`--adr`（デフォルト OFF）— `/creview:triage` と `/creview:respond` に `--adr` を渡す。

`${CLAUDE_PLUGIN_ROOT}/rules/leader.md` に従う。その `plugin_root` 変数は `${CLAUDE_PLUGIN_ROOT}`、`{skill}` は `respond` とする。`{document_path}` はルールの値に代えて、`creview:triage` が報告するレビュードキュメントとする。

## Step 1 — トリアージと修正

1. `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/gh-review.py participants '{pr_url}'` を実行する。`viewer`、`author`、`assignees` が出力される。`{deciders}` を `assignees` とし、`assignees` が空なら `author` とする: 両者が異なるときは `assignees` を優先する。§ 指摘 ID に従う。`path` が得られる。自分の指摘はドキュメントでも ID を保ち、それ以外の指摘は新しい ID を受け取り、その指摘に投稿する返信がそれを示す。`{pr_url} --finding-ids '{path}'` で `creview:triage` を実行する。`--trust` と `--adr` が指定されていれば追加する。オーバーライド:
   - すべての `pr-comment-compiler`: `返信の主張を、発言者の login とともに指摘の説明に書く。{viewer} のコメントが **Major M-1** のように指摘の ID を示しているときは、指摘の "id" にその ID も設定する。本文がマージゲートの判定の見出し（## Merge gate: か ## マージゲート: で始まる行。その後の文言は問わない）で始まるレビューには概要がある: 判定の見出しの後から、件数の行、小見出し、本文末のうち最初のものまでの文章である。概要は他で挙げた指摘をまとめるもので、指摘ではない。`
   - トリアージサブエージェント: `指摘は人間や AI を問わず誰かのコメントに由来し、それぞれ返信が主張する内容と発言者を述べている。既に対応済みの指摘には 🚫 Won't Fix を設定する: (a) コードに問題がもうない: 理由を [resolved] で始める。(b) そのレビューが dismiss された。(c) {deciders} の誰かが理由を述べて変更しないと決めた。(d) 指摘したレビュアー本人が取り下げた。理由にはどう対応されたかを、そう述べた人の login とともに書く。それ以外の人の発言は判断基準にしない。ただし、プルリクエストの作者の質問に誰かが答え作者がそれを受けている場合のように、{deciders} の誰かかそのレビュアーが述べたと見なせるときは採用する。返信で判断を変えるときは必ず述べられた事実をコードで確認し、コードが否定するなら採用しない。コードの裏付けのない修正済みという主張は対応にならない。これらの理由には別 PR の推奨を付けない。`

   コメントに指摘がないと報告されたら、ユーザーに伝えて終了する。
2. `--no-confirm` が指定されているか、トリアージの compile 結果の `maintain` と `alternative` がともに 0 である場合を除き、修正を確認する:
   - `{document_path}` を Read し、各指摘の ID、場所、作者（その reviewers の項目。ラベルはドキュメントの言語による）、`Triage:` / `Estimate:` 行を、`Cost:`、`Future:`、`Signals:` を除いてユーザーに示す。トリアージが報告した ADR ファイルを挙げる（ユーザーは修正の前に編集できる）。修正してよいか尋ね、ターンを終える。
   - ユーザーが指摘を除外したら、その `Triage:` 行を `- **Triage:** 🚫 Won't Fix — {ユーザーの理由。なければユーザーが除外した旨}` に置き換える。返信がこれを引用するので、理由を創作しない。トリアージが却下した指摘や Downgrade された指摘はここでは追加できない: その旨を伝える。ユーザーが修正を指示してから先へ進む。
   - ユーザーが断ったら終了する。
3. `{document_path} --commit` で `creview:respond` を実行する。`--adr` が指定されていれば追加する。その警告と未修正の指摘を Step 5 のために保持する。

## Step 2 — push

`python3 ${CLAUDE_PLUGIN_ROOT}/scripts/gh-review.py fixes '{pr_url}' '{tmp_dir}' '{document_path}'` を実行する。`{tmp_dir}/fix-commits.json` が書き出され、`commits`、`branch`、`head_ref`、`head_repo` が出力される。

`commits` が 0 なら `{document_path}` を Read する: `Status: 🟢 Fixed` の指摘があればその修正は未コミットなので、ユーザーに伝えて何も投稿せず Step 5 に進み、なければ Step 3 に進む。`commits` が 1 以上なら、コミットを示し、`head_repo` の `head_ref` へ（`branch` が null でなければそこから）push して完了を知らせるようユーザーに依頼する。`head_ref` が null なら、ブランチ名もコマンドも示さず、push 先をプルリクエストのページで確認するよう伝える。ターンを終える。

ユーザーが完了を伝えたら、`python3 ${CLAUDE_PLUGIN_ROOT}/scripts/gh-review.py pushed '{pr_url}' '{tmp_dir}/fix-commits.json'` を実行する。`pushed` が false なら、返信が引用するハッシュのコミットがプルリクエストに含まれていないこと（リベースするとハッシュが変わる）をユーザーに伝え、再びターンを終える。コミットをリベースまたはスカッシュしたとユーザーが伝えたら、`fixes` からこのステップをやり直す。やめるとユーザーが伝えたら、何も投稿せずに Step 5 に進む。

## Step 3 — 返信のドラフト

1. `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/gh-review.py comments '{pr_url}' '{tmp_dir}'` を実行する。`pr_body_path` が出力される。
2. `{document_path}`、`{tmp_dir}/comments.json`、`{tmp_dir}/fix-commits.json`、`{pr_body_path}`、`${CLAUDE_PLUGIN_ROOT}/rules/wording.md` を Read し、その § 起草する返信 のとおり `{tmp_dir}/replies.json` を書く。

## Step 4 — 確認と投稿

返信がなければ Step 5 に進む。それ以外は `unmatched` と `unaddressed` をプレビューとともに示す。

`{json_path}` = `{tmp_dir}/replies.json` で § 確認と投稿 に従い、`post` にオプション `--commits '{tmp_dir}/fix-commits.json'` を渡す: プルリクエストがコミットを含むまで何も送らない。`{json_path}` の欠落または不正で `preview` が非ゼロ終了したとき、または `comment_lang` に null を出力したときは、ファイルを書き直して再度実行する。2 回目の失敗で中断する。

## Step 5 — 報告

Step 4 で投稿したときは `posted` と `urls`、Step 3 を実行したときはその `unmatched`（コメントを特定できなかった指摘）、`unaddressed`（まだ手作業での対応が必要な指摘）、Step 1 で保持した内容、`{document_path}` から各 `🚫 Won't Fix` の指摘の ID、場所、作者、理由を報告する。その後終了する。
