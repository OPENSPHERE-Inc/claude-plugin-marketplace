---
name: compile
description: /creview:respond ステップ 5 で修正状況を集約し events.jsonl 経由で markdown に反映する編纂サブエージェント向けプロンプト
template_id: 3b7f1c5d-8a29-4e63-b1c8-9d3a7f5e2b41
---

レビュー対応の編纂担当として、修正状況を集約し events.jsonl 経由で markdown に反映する。`triage` / `estimate` フィールドはすでに `/creview:triage` がドキュメントに永続化済みであり、本ステップは `status` のみを反映する。`{{plugin_root}}/rules/sub-agent.md` を Read し共通禁止事項を遵守する。

入力:

- status: `{{tmp_dir}}/statuses/`（修正済み指摘 1 件 1 JSON。修正対象がなかった場合は空でもよい）
- 対象 markdown: `{{document_path}}`

出力:

- events.jsonl: `{{tmp_dir}}/events.jsonl`
- 反映後の `{{document_path}}`

実施内容:

1. `{{tmp_dir}}/statuses/*.json` を Read し、各 item の `memo_value` を `status` event として収集する。
2. `{{tmp_dir}}/events.jsonl` に 1 行 1 イベントの JSONL を書き出す。形式: `{"id":"...","field":"status","value":"..."}`。status が存在しない場合は空ファイルを書き出す。
3. `python {{plugin_root}}/scripts/render-review.py {{document_path}} {{tmp_dir}}/events.jsonl {{document_path}}` を実行する。

戻り値: `{fixed_count（statuses のファイル数 = Maintain 修正 + Alternative FIXME 付与）, code_changed（status が 1 件以上なら true、それ以外は false）, summary_line（<=200 chars。例: "3 fixed (2 Maintain + 1 Alternative)"）, template_id}`。`template_id` は本テンプレートの frontmatter から Read した値をそのまま含める。
