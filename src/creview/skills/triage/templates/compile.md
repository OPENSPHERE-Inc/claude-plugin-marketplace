---
name: compile
description: /creview:triage ステップ 3 でトリアージ / 見積判定を集約し events.jsonl 経由で markdown に反映する編纂サブエージェント向けプロンプト
template_id: 3b7f1c5d-8a29-4e63-b1c8-9d3a7f5e2b41
---

トリアージ編纂担当として、トリアージ / 見積判定を集約し events.jsonl 経由で markdown に反映する。`status` と `verification` は対象外（`/creview:respond` と `/creview:resolve` が設定する）。`{{plugin_root}}/rules/sub-agent.md` を Read し共通禁止事項を遵守する。

入力:

- triage: `{{tmp_dir}}/triage.json`
- estimate: `{{tmp_dir}}/estimates/`（Will Fix 指摘 1 件 1 JSON。will_fix_count == 0 のとき存在しない）
- 対象 markdown: `{{document_path}}`

出力:

- events.jsonl: `{{tmp_dir}}/events.jsonl`
- 反映後の `{{document_path}}`

実施内容:

1. `{{tmp_dir}}/triage.json` と `{{tmp_dir}}/estimates/*.json` を Read し、各 item の `memo_value` を該当フィールド（`triage` は triage.json の items、`estimate` は各 estimates JSON）の event として収集する。
2. `{{tmp_dir}}/events.jsonl` に 1 行 1 イベントの JSONL を書き出す。形式: `{"id":"...","field":"triage|estimate","value":"..."}`
3. `python {{plugin_root}}/scripts/render-review.py {{document_path}} {{tmp_dir}}/events.jsonl {{document_path}}` を実行する。

戻り値: `{fixed_count（本ステップは常に 0）, code_changed（false）, summary_line（<=200 chars。例: "5 triaged: 3 Will Fix (2 Maintain + 1 Alternative), 2 Won't Fix"）, template_id}`。`template_id` は本テンプレートの frontmatter から Read した値をそのまま含める。
