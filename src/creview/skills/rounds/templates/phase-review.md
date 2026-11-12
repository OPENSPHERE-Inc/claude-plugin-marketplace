---
name: phase-review
description: /creview:rounds ステップ 2.1 で /creview:start をリーダーとして実行するフェーズリーダーサブエージェント用プロンプト
template_id: 3e7b1c9d-6a24-4f85-b1d7-8c2e5a9f3b64
---

`/creview:rounds` の 1 ラウンド分として、`creview:start` スキルをそのレビューリーダーとして実行する。`{{plugin_root}}/rules/sub-agent.md` を Read し、共通禁止事項を遵守する。

入力:

- ラウンド番号: `{{round_num}}`
- ベースブランチ: `{{base}}`
- レビュー範囲: `{{review_range}}`（ブランチ全体の差分が対象の場合は `(該当なし)`）
- 今ラウンドのレビュードキュメントのパス: `{{document_path}}`
- ドキュメントの言語: `{{language}}`
- 敵対的モード: `{{adversarial}}`

実施内容:

1. `creview:start` スキルを起動し、そのレビューリーダーとしてステップ 1〜4（作業用ディレクトリの削除を含む）を実行する。引数は `Round {{round_num}}` と `--output {{document_path}}` に加え、`{{review_range}}` が `(該当なし)` でなければ `--range {{review_range}}`、そうでなければ `--base {{base}}` を渡し、`{{adversarial}}` が ON の場合は `--adversarial` を付す。レビュー対象を自分で指定しない。
2. 自分が発行するすべてのサブエージェント起動プロンプトの「ラウンド固有のオーバーライド」セクションに以下を追加する:
   - 過去ラウンドのレビュードキュメントをレビュアーに渡さない。過去ラウンドとの重複排除も行わない。
   - レビュアーへのプロンプトに絶対に含めない: 過去ラウンドの指摘件数、件数の推移、「収束しつつある」等の傾向情報、過去ラウンドの指摘 ID（`C-1`、`M-1` 等）、Fixed / Won't Fix の統計情報。
   - 集約サブエージェント: レビュードキュメントは `{{language}}` で記述する。

レビュアープロンプトテンプレートの一部を省略すること、指摘数を調整する目的で指示を付け足すこと、レビュアーが提出したもの以外の指摘を追加することは禁止。

戻り値: `{doc_path, findings_total, severity_counts: {critical, major, minor, info}, error, template_id}`。`error` は、スキルがステップ 1〜4 を最後まで実行した場合は警告付きでも null。スキルが中断・終了した場合、またはスクリプトの非ゼロ終了や、サブエージェントの `template_id` 不一致の 2 回連続など、先に進めない失敗でステップが止まった場合は、スキルが表示したエラーとし、スキルが表示しなかった場合は、止まったステップとそこで失敗した内容（コマンドの終了コードとエラー出力、または不一致の `template_id`）を記したメッセージを自分で書く。エラー時は `doc_path` を null、`findings_total` と各 severity の件数を 0 として報告する。`template_id` は本テンプレートの frontmatter から Read した値をそのまま含める。
