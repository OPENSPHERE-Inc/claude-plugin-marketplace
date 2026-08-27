---
name: phase-resolve
description: /creview:rounds ステップ 2.4 およびステップ 2.5 のフィードバックループで /creview:resolve をリーダーとして実行するフェーズリーダーサブエージェント用プロンプト
template_id: 2f9c6a1e-7b53-4d84-8e2b-5a1f9d3c7b26
---

`/creview:rounds` の 1 ラウンド分として、`creview:resolve` スキルをそのレビュー検証リーダーとして実行する。`{{plugin_root}}/rules/sub-agent.md` を Read し、共通禁止事項を遵守する。

入力:

- レビュードキュメント: `{{document_path}}`
- ベースブランチ: `{{base}}`
- ラウンド固有のオーバーライド: `{{overrides}}`

実施内容:

1. `creview:resolve` スキルを引数 `{{document_path}} --base {{base}}` で起動し、そのレビュー検証リーダーとしてステップ 1〜4（compile ステップと作業用ディレクトリの削除を含む）を実行する。
2. `{{overrides}}` の各項目を、項目が名指しするサブエージェント（名指しが無い場合は全サブエージェント）の起動プロンプトの「ラウンド固有のオーバーライド」セクションに追加する。

戻り値: `{summary_line, resolved_count, feedback_count, unresolved_count, template_id}`。`template_id` は本テンプレートの frontmatter から Read した値をそのまま含める。
