---
name: prior-discussion
description: /creview:pr ステップ 4 で指摘をプルリクエストの会話と照合するサブエージェントのプロンプト — 会話で既出・解決済・却下済の指摘を除外し、返信先とする未解決スレッドを指摘に対応付け、修正を確認できる閲覧者のスレッドを見つける
template_id: a1c67c6b-a514-48e6-abb5-52dc01f28221
---

レビュードキュメント `{{document_path}}` のすべての指摘を `{{conversation_path}}` のプルリクエストの会話と照合する。投稿しない指摘を Won't Fix として `{{output_dir}}/triage.jsonl` に、返信先のレビュースレッドを `{{output_dir}}/threads.jsonl` に Write する。`{{plugin_root}}/rules/sub-agent.md` を Read し共通禁止事項を遵守する。あなたのファイルシステムへの書き込みはこの 2 ファイルのみ。使用ツールは Read / Glob / Grep、この 2 ファイルへの Write、`check-jsonl.py` の実行に限る Bash に限定。

入力:

- `{{document_path}}` — すべての重要度セクションで、`### {finding-id} — `{location}` [{categories}]` 見出しごとに 1 件の指摘。
- `{{conversation_path}}` — `{viewer, issue_comments, reviews, review_threads}`。`viewer` はレビューを投稿するアカウント。レビュースレッドは `id`、`path`、`line`（outdated になると null。ファイル単位のスレッドでも null）、`original_line`、`subject_type`、`resolved`、`outdated`、`diff_hunk`（最初のコメントが付いたコード）、`own`（閲覧者が立てたスレッド）、`confirmed`（閲覧者が修正確認を投稿済み）とその `comments` を持つ。`author_type` で人間とボットを区別できるが、両者を同等に扱う。

コメントまたはスレッドが同じ問題を報告している場合、その指摘は扱い済みとする: 同じ箇所の同じ根本原因、あるいはファイル単位や全般的なコメントであれば同じファイルまたは領域の同じ問題。行番号がずれている場合は `{{target_dir}}` 配下のソースを Read し、両者が同じコードを指すことを確認する。outdated のスレッドとファイル単位のスレッドは、行番号ではなく `diff_hunk` とコメントの内容で照合する。扱い済みの指摘を分類する:

- `rejected` — PR の作成者またはメンテナーが指摘を退けたか、理由（別 PR、受け入れた制限等）を示して見送り、この PR で修正する約束なく議論が終わった（その後スレッドが resolve されたかどうかを問わない）。
- `resolved` — それ以外で、`{{target_dir}}` のコードにもう問題が見られず、スレッドが resolve されているか、会話が問題を修正済みと記録している。
- `reused` — それ以外で、resolve されていないレビュースレッドと一致する: 指摘はレビューに残し、そのスレッドへの返信として投稿する。
- `raised` — それ以外で、レビュースレッド外のコメントで指摘されている。

関連するだけの指摘、確信をもって対応付けられない指摘、およびスレッドが resolve されているか修正済みと記録されているのに `{{target_dir}}` のコードに問題が残り、会話がそのままにする理由を述べていない指摘は、分類せずに残す。

修正確認: `own` が true で `confirmed` が false のスレッドのうち、`{{document_path}}` のどの指摘とも一致しないものについて、スレッドが指す `{{target_dir}}` のコード（outdated なら `diff_hunk` で特定）を Read し、最初のコメントが報告した問題が解消したかを判断する。解消していればそのスレッドを挙げ、問題が残る場合や判断できない場合は挙げない。

`{{output_dir}}/triage.jsonl` の形式: `{items: [{id, verdict: "Won't Fix", prior (raised | resolved | rejected), url (対応するコメントの url), reason, memo_value}], will_fix_count: 0, wontfix_count}`（`rejected`・`resolved`・`raised` の指摘のみ。`wontfix_count` は items の件数）

`memo_value`: `🚫 Won't Fix — {reason}`。`reason` は分類と対応するコメントの url を 1 行で述べる（例: `PR の会話で指摘済み: {url}`）。

`{{output_dir}}/threads.jsonl` の形式: `{reuse: [{id, thread_id, url}], confirm: [{thread_id, url, reason}]}`（`thread_id` はスレッドの `id`、`url` は最初のコメントの url。confirm の `reason` は問題を解消した変更を 1 行で述べる）

`reason` はすべて `{{document_path}}` の Finding の説明と同じ言語で記述する。

戻り値: `{path, excluded_count, raised, resolved, rejected, reused, confirmed, template_id}`（`path` は triage.jsonl のパス。reason は含めない）。`template_id` はこのテンプレートの frontmatter から Read した値をそのまま含める。
