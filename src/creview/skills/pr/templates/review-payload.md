---
name: review-payload
description: /creview:pr ステップ 6 でトリアージ済みのレビュードキュメントから投稿するレビューコメントと修正確認を作成するサブエージェントのプロンプト
template_id: 1c163d5b-2249-4ff2-bb85-5dcce19fe281
---

トリアージ済みのレビュードキュメント `{{document_path}}` とスレッド一覧 `{{threads_path}}` から投稿するプルリクエストレビューを作成し、`{{output_path}}` に Write する。`{{plugin_root}}/rules/sub-agent.md` を Read し共通禁止事項を遵守する。使用ツールは Read、`{{output_path}}` への Write、`check-jsonl.py` の実行に限る Bash に限定。

`{{threads_path}}` は `{reuse: [{id, thread_id, url}], confirm: [{thread_id, url, reason}]}`。`(none)` の場合は両方とも空として扱う。

選定: Critical / Major / Minor セクションの指摘のうち、最後の `Triage` の値が `🔧 Will Fix` で始まるものすべて。

投稿言語: `{{pr_path}}` の `title` と `body` の言語。`body` が空か言語が判然としない場合は `{{doc_lang}}`。

選定した指摘ごとに 1 件のコメント:

- `id` と `severity` — 指摘のセクション（`Critical` / `Major` / `Minor`）。
- `location` — 見出しのロケーション。`PR description` は投稿言語に訳す。
- `path` / `line` — `file_path:line` のロケーションから、リポジトリルートからの相対パスと整数の行（範囲なら先頭行）。ロケーションに行がなければ `line` は null、`PR description` では両方 null。
- `thread_id` / `thread_url` — 当該指摘の `reuse` エントリの `thread_id` と `url`。コメントはそのスレッドへの返信として投稿される。エントリがなければ両方 null。
- `body` — 投稿言語の Markdown: 1 行目は `**{id} {severity}** [{categories}]`（例: `**M-1 Major** [Security]`。`{id}` はレビュードキュメントの finding-id のまま、カテゴリは投稿言語）、続いて PR の作成者向けに書き直した指摘 — 問題、その影響、修正の方向性。レビュアー名とトリアージのメタデータは含めない。本文は当該指摘だけを根拠とし、ローカルの絶対パス（リポジトリ相対パスを使う）、プルリクエストに含まれないファイルの内容、認証情報や秘密値らしき文字列を含めない。

`confirm` のエントリごとに 1 件の修正確認: その `thread_id` と `url`、および `reason` に基づき、スレッドが報告した問題が PR の head で修正されたことを確認した旨を投稿言語で述べる 1〜2 文の `body`。

あわせて投稿言語で、`body` — 投稿する指摘を重要度別の件数で、修正確認をその件数で要約する 1〜2 文 — と、`outside_diff_heading` — 差分にアンカーできない指摘の見出し — を作成する。

`{{output_path}}` の形式（1 つの JSON オブジェクト）:

```json
{"post_lang": "English", "body": "...", "outside_diff_heading": "...", "comments": [{"id": "M-1", "severity": "Major", "location": "src/a.py:42", "path": "src/a.py", "line": 42, "thread_id": null, "thread_url": null, "body": "..."}], "confirmations": [{"thread_id": "PRRT_...", "url": "...", "body": "..."}]}
```

選定や一覧がなければ `comments` と `confirmations` は空配列。`python3 {{plugin_root}}/scripts/check-jsonl.py {{output_path}}` でファイルを検証する。

戻り値: `{path, comment_count, confirmation_count, by_severity: {critical, major, minor}, post_lang, template_id}`。`template_id` はこのテンプレートの frontmatter から Read した値をそのまま含める。
