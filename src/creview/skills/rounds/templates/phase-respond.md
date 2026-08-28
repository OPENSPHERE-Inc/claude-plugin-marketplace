---
name: phase-respond
description: /creview:rounds ステップ 2.3 およびステップ 2.5 のフィードバックループで /creview:respond をリーダーとして実行するフェーズリーダーサブエージェント用プロンプト
template_id: 8b5e3d7a-4c16-4a92-a7f3-2d9c6b1e8f47
---

`/creview:rounds` の 1 ラウンド分として、`creview:respond` スキルをそのレビュー対応リーダーとして実行する。`{{plugin_root}}/rules/sub-agent.md` を Read し、共通禁止事項を遵守する。

入力:

- レビュードキュメント: `{{document_path}}`（トリアージ / 見積は永続化済み）
- `--commit`: `{{commit_flag}}`
- `--adr`: `{{adr_flag}}`
- ラウンド固有のオーバーライド: `{{overrides}}`

実施内容:

1. `creview:respond` スキルを引数 `{{document_path}}` で起動する（`{{commit_flag}}` が ON の場合は `--commit` を、`{{adr_flag}}` が ON の場合は `--adr` を付す）。そのレビュー対応リーダーとしてステップ 1〜6（フォーマット・ビルド・テスト検証 ⇄ ビルド修正の再実行ループ、コミットステップ、および compile ステップを含む）を実行する。
2. `{{overrides}}` の各項目を、項目が名指しするサブエージェント（名指しが無い場合は全サブエージェント）の起動プロンプトの「ラウンド固有のオーバーライド」セクションに追加する。

戻り値: `{fix_count, fixed_count, code_changed, workflow_warning, summary_line, template_id}`。`workflow_warning` は最後のフォーマット・ビルド・テスト検証の値で、手順が解決できた場合は null。`template_id` は本テンプレートの frontmatter から Read した値をそのまま含める。
