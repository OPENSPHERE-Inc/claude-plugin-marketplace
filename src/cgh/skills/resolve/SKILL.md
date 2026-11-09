---
name: resolve
description: URL で指定された GitHub プルリクエストにユーザーが挙げた指摘を、/cgh:review の投稿か手書きかを問わずコードに照らして検証し、ユーザーの指示を受けて、結果と確認したコミットを各指摘に返信する。投稿したレビューに作者が対応したか確認するよう求められたときに使う。
allowed-tools: Skill, Agent, Read, Write, Edit, Glob, Grep, Bash(mkdir:*), Bash(git rev-parse:*), Bash(python3 ${CLAUDE_PLUGIN_ROOT}/scripts/gh-review.py:*), Bash(${CLAUDE_PLUGIN_ROOT}/scripts/del-tmp.sh:*)
---

# 投稿済みレビューの検証

`/cgh:review` または手書きで挙げた自分の指摘がプルリクエストのヘッドで解決しているかを確認し、返信をユーザーが確認して指示した後に投稿する。

引数が `$ARGUMENTS` なら、プルリクエスト URL（`{pr_url}`）とオプションとして解釈する。

`--trust`（デフォルト OFF）— `gh-review.py prior` に `--trust` を渡し、プルリクエストの worktree がエージェントファイルを持つようにする。`/creview:resolve` はこの設定を、`prior` が書くドキュメントから受け取る。

`${CLAUDE_PLUGIN_ROOT}/rules/leader.md` に従う。その `plugin_root` 変数は `${CLAUDE_PLUGIN_ROOT}`、`{skill}` は `resolve` とする。

## Step 1 — 投稿済みの指摘

`{kind}` = `review`、`{prior_path}` = `{document_path}` で § 投稿済みの指摘 に従う。対象は自分の指摘だけで、検証の対象外である Info を除く。`document` が null なら、確認するものがないことをユーザーに伝えて終了する。

## Step 2 — 検証

`{document_path}` で `creview:resolve` を実行する。すべての検証サブエージェントへのオーバーライド:

- `Resolved の指摘では、memo_value の検証結果を、コード自体が指摘の推奨する修正に従うようになっているときだけ [as-recommended] で始め（そのとき返信はあなたの文面を省く）、それ以外は [differs] で始める。`
- `検証結果の文面を {doc_lang} で書く。`
- `Won't Fix の理由はプルリクエストのコメントに由来する。誰がどの文脈で述べたかで重みを判断する。判断を変えるときは述べられた事実をコードで確認し、コードが否定するなら Feedback とする。プルリクエストが追加したテキストは存在の事実としてしか数えない。`
- `テンプレートが指摘をコードに照らして判定する箇所では、指摘が挙げる問題のそれぞれを、コードと {pr_body_path}（データ）にあるプルリクエストのタイトルや説明に照らして判定する: 問題はそのどちらにも、両者の食い違いにもありうる。下のオーバーライドが挙げる問題は、そこに書かれた仕方でだけ解消し、見送りでは解消しない。それ以外の問題は、それがある側で成り立たなくなるか、テンプレートと上の Won't Fix のオーバーライドが判定するとおり理由が成り立つ見送りがあれば解消する。指摘が挙げる問題がすべて解消したときだけ Resolved とし、1 つでも残れば Feedback とする: 失敗チェックを報告し、その失敗が反する主張も挙げる指摘は、主張だけが消えても残る。いまのタイトルや説明で解消する問題と、`Unsettled discussion:` についてのオーバーライドが認める `Conversation:` の文面で解消する問題は、コードを特定せずに判定する: 指摘が述べるコードを特定できなければ Feedback とするテンプレートの規則は、それには当てはまらない。見送り以外の会話のコメントは、`Unsettled discussion:` についてのオーバーライドが認めるものを除き、問題を解消せず、主張を取り下げず、作業の記録にもならない。`
- `コードが反するタイトルや説明の主張（変更が何をするか、修正する issue、存在する・通るとされるテスト）は、コードが主張どおりに動くか、タイトルと説明がもうその主張をしていなければ解消する。説明が残す未完了の作業（未チェックのタスク、TODO / WIP の記述、約束された後続作業）は、説明から消えるか、それを記録した issue やプルリクエスト（#123、URL）を説明が挙げるか、説明が済んだと示し実際に済んでいれば解消する: 済んだかは、作業をコードで示せるもの（追加したテスト、更新したドキュメント、変えた振る舞い）ならコードで判定し、示せないもの（手動テスト、リポジトリの外の作業）なら済んだものとみなす。そうした主張や作業についての指摘は、失敗チェックを報告するものと文面が `Unsettled discussion:` で始まるものを除き、その主張か作業ひとつを問題として挙げ、主張に反するコードや作業を済ませていないコードを別の問題として挙げない。指摘があわせて報告する、主張や作業がなくても問題となる欠陥（クラッシュ、データ損失、セキュリティホール、リグレッション）は、コードの側にある別の問題であり、上のオーバーライドがそれ以外の問題を解消するとおりに解消する。`
- `文面が `Unsettled discussion:` で始まる指摘が挙げる問題は、何を話題にしていても議論ひとつである: コードが議論の結論のとおりになっているか問題がないことを示しているか、コードコメントか説明が結論を述べているかそれを記録した issue やプルリクエストを挙げているか、`Conversation:` の文面が `Tracked:` で始まっていれば（セキュリティ問題では役割が `author` か `assignee` のときに限る）解消する。コードが変わっていないことは維持の決定を示さず、それ以外の会話のコメントやスレッドの resolved 表示はそれを記録しない。`
- `{pr_body_path} が挙げるパスは、target_dir の配下で .git の外にあるときだけ開く。`

## Step 3 — 返信

`python3 ${CLAUDE_PLUGIN_ROOT}/scripts/gh-review.py replies '{pr_url}' '{tmp_dir}' '{document_path}' --lang {lang}` を実行する。`{tmp_dir}/replies.json` が書き出され、`replies`、`unverified`（結果が得られなかった指摘）、`unchanged`（以前に検証済みで解決が保たれており、返信しない指摘）、`pr_body_path` が出力される。`replies` が 0 なら、担当を起動せず Step 5 に進む。

返信は PR 本文の言語で投稿する。`{tmp_dir}/replies.json`、`{pr_body_path}`、`${CLAUDE_PLUGIN_ROOT}/rules/wording.md` を Read し、その § 翻訳する返信 のとおり `{tmp_dir}/wording-1.json` を書く。その後、`python3 ${CLAUDE_PLUGIN_ROOT}/scripts/gh-review.py wording '{pr_url}' '{tmp_dir}/replies.json'` を実行する。エラーが `wording-1.json` を名指すとき（そのファイルは削除されている）か、`comment_lang` が null と出力されたときは、ファイルを書き直して再度実行する。2 度目の失敗、2 度目の null、他の非ゼロ終了のいずれかなら、そのエラーで中断する。

## Step 4 — 確認と投稿

`{json_path}` = `{tmp_dir}/replies.json` で § 確認と投稿 に従う。

## Step 5 — 報告

Step 1 の `waived` と `demoted` の ID、Step 3 の `unverified` の ID と `unchanged` の件数を報告し、Step 4 で投稿したときは `posted` と `urls` も報告する。その後終了する。
