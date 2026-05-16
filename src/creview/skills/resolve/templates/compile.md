---
name: compile
description: /creview:resolve ステップ 3 で中間ファイルから検証レポートと events.jsonl を生成し markdown に反映する編纂サブエージェント向けプロンプト
template_id: 1c5e8b2f-7d34-4a96-b8c1-5e9a3f7d2c84
---

レビュー検証の編纂担当として、中間ファイルから検証レポートと events.jsonl を生成し markdown に反映する。`{{plugin_root}}/rules/sub-agent.md` を Read し共通禁止事項を遵守する。

入力:

- `{{tmp_dir}}/verifications/` — 各指摘の検証結果（severity / trailing_field / feedback_detail 含む）
- 対象 markdown: `{{document_path}}`

出力:

- 検証レポート: `{{tmp_dir}}/resolve-summary.md`
- events.jsonl: `{{tmp_dir}}/events.jsonl`
- 反映後の `{{document_path}}`

実施内容:

1. `{{tmp_dir}}/verifications/*.json` を Read し、検証レポートを `{{tmp_dir}}/resolve-summary.md` に Write する。フォーマット:
   - 見出し: 「# レビュー検証レポート」
   - メタ情報: 「レビュードキュメント: {{document_path}}」「検証日: YYYY-MM-DD」（太字）
   - 「## 検証結果」配下に 3 表:
     - 「### 解決済み」: # / 重要度 / 末尾フィールド / 判定（outcome == Resolved）
     - 「### フィードバック必要」: # / 重要度 / 末尾フィールド / 問題（outcome == Feedback）
     - 「### 未解決」: # / 重要度 / 末尾フィールド / メモ（outcome == Unresolved）
   - 「## サマリー」: 検証した指摘件数 / 解決済み / フィードバック必要 / 未解決 を箇条書き
   - 「## フィードバック詳細」: outcome == Feedback の各指摘について「### {finding-id} — フィードバック」「元の指摘（feedback_detail.description）」「末尾フィールド」「実際の状態（feedback_detail.current_state）」「問題（feedback_detail.issue）」「提案（feedback_detail.suggestion）」を記載、エントリ間は --- で区切り

2. `{{tmp_dir}}/events.jsonl` に verification イベントを 1 行 1 イベントの JSONL で書き出す。形式: `{"id":"...","field":"verification","value":"<memo_value>"}`。outcome == Unresolved のエントリは書き込まない。

3. `python {{plugin_root}}/scripts/render-review.py {{document_path}} {{tmp_dir}}/events.jsonl {{document_path}}` を実行する。

戻り値: `{summary_path, summary_line（<=200 chars。例: "3 resolved, 1 feedback (M-1), 2 unresolved"）, resolved_count, feedback_count, unresolved_count, template_id}`。`template_id` は本テンプレートの frontmatter から Read した値をそのまま含める。
