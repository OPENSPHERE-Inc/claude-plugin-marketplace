---
name: reviewer
description: /creview:start ステップ 2 で個別レビュアー（専門家サブエージェント）が差分をレビューする際の指示テンプレート
template_id: 4d8c2e5b-1f73-4a96-b2e8-9c1d3a7f4b62
---

`{{diff_path}}` を Read してコードレビューを実施する。`{{plugin_root}}/rules/sub-agent.md` を Read し共通禁止事項を遵守する。

対象: `{{targets}}`（ベース: `{{base}}`）

ルール:

- 使用ツールは Read / Glob / Grep / Bash(grep/ls/find) に限定。git diff/log/show の再実行は不要（差分は `{{diff_path}}` に集約済み）。周辺コードを確認する際も Read を使う。
- 重要度ラベル: Critical（致命的・修正必須）/ Major（中リスク・修正すべき）/ Minor（注意事項）/ Info（参考）。
- カテゴリラベル: 指摘の性質を表す分類を 1 件以上付与する。プリセット: `バグ` / `保守性` / `可読性` / `テスト` / `パフォーマンス` / `セキュリティ` / `スタイル` / `ドキュメント` / `設計`。プリセットに当てはまらない場合は新規ラベルを作成可（短い名詞句、`/` と `]` を含めない）。複数該当時は `/` 連結で 1 つの `[ ]` にまとめる。カテゴリラベル本体は `{{doc_lang}}` で記述可（プリセット名は訳語に置換可）。
- `{{plugin_root}}/rules/review.md` を Read して従う。

出力:

- `{{output_path}}` に `[重要度] [カテゴリ] file_path:line — 問題の説明とその重要性。` 形式の番号付きリストのみ Write（前置き・後書き禁止）。
  - カテゴリ例: `[バグ]` / `[保守性/可読性]` / `[テスト]`。
- 問題の説明は `{{doc_lang}}` で記述する。`file_path:line` と重要度ラベル（Critical / Major / Minor / Info）はそのまま。
- 戻り値: `{"path": "{{output_path}}", "critical": <int>, "major": <int>, "minor": <int>, "info": <int>, "template_id": "<本テンプレートの template_id>"}`
