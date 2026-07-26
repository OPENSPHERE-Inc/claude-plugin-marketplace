---
name: phase-review
description: /creview:rounds ステップ 2.1 で /creview:start をリーダーとして実行するフェーズリーダーサブエージェント用プロンプト
template_id: 3e7b1c9d-6a24-4f85-b1d7-8c2e5a9f3b64
---

`/creview:rounds` の 1 ラウンド分として、`creview:start` スキルをそのレビューリーダーとして実行する。`{{plugin_root}}/rules/sub-agent.md` を Read し、共通禁止事項を遵守する。

入力:

- ベースブランチ: `{{base}}`
- 今ラウンドのレビュードキュメントのパス: `{{document_path}}`
- ドキュメントの言語: `{{language}}`
- 敵対的モード: `{{adversarial}}`

実施内容:

1. `creview:start` スキルを引数 `--base {{base}} --output {{document_path}}` で起動する（`{{adversarial}}` が ON の場合は `--adversarial` を付す）。そのレビューリーダーとしてステップ 1〜4（作業用ディレクトリの削除を含む）を実行する。レビュー対象は指定せず、スキルのデフォルト（現在のブランチ固有のコミット）に委ねる。
2. 自分が発行するすべてのサブエージェント起動プロンプトの「ラウンド固有のオーバーライド」セクションに以下を追加する:
   - 過去ラウンドのレビュードキュメントをレビュアーに渡さない。過去ラウンドとの重複排除も行わない。
   - レビュアーへのプロンプトに絶対に含めない: 過去ラウンドの指摘件数、件数の推移、「収束しつつある」等の傾向情報、過去ラウンドの指摘 ID（`C-1`、`M-1` 等）、Fixed / Won't Fix の統計情報。
   - 集約サブエージェント: レビュードキュメントは `{{language}}` で記述する。

レビュアープロンプトテンプレートの一部を省略すること、指摘数を調整する目的で指示を付け足すこと、レビュアーが提出したもの以外の指摘を追加することは禁止。

戻り値: `{doc_path, findings_total, severity_counts: {critical, major, minor, info}, template_id}`。`template_id` は本テンプレートの frontmatter から Read した値をそのまま含める。
