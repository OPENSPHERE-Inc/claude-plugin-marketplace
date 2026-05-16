---
name: estimate-summary
description: /creview:triage ステップ 2 で見積結果サマリを生成する見積集約サブエージェント向けプロンプト
template_id: 5c1e9b7a-3d48-4a96-b8e2-7f3c5a1d4b29
---

見積結果サマリ生成担当として、`{{tmp_dir}}/triage.json` と `{{tmp_dir}}/estimates/*.json` および `{{document_path}}` を Read し、統合サマリを `{{tmp_dir}}/estimate-summary.md` に Write する。`{{plugin_root}}/rules/sub-agent.md` を Read し共通禁止事項を遵守する。

## 入力の取り扱い

- triage.json の各 item（Will Fix / Won't Fix 両方）が出力対象。estimates は Will Fix のみ存在するので、triage.json を主軸にして estimates/{id}.json を id で結合する。
- レビュードキュメント `{{document_path}}` から各 finding の severity / location / description を取得する（METADATA マーカー前後の見出し・本文から抽出）。description は 1〜2 文の要約に圧縮する。

## `{{tmp_dir}}/estimate-summary.md` の構成

1. 先頭にレビュードキュメントへのリンク行: `詳細: [{basename}]({{document_path}})`（`{basename}` は `{{document_path}}` の末尾ファイル名）
2. 統合テーブル（列）: 指摘 ID / Severity / Location / 概要 / 専門家 / トリアージ / Cost / Future / シグナル / 見積判定（▶️ Maintain | 🔻 Downgrade | 🚧 Alternative）/ 備考
   - Severity: Critical / Major / Minor / Info
   - Location: file:line（長い場合は basename:line に短縮可）
   - 概要: description の要約 1〜2 文
   - 専門家: triage.json の assignee（Won't Fix は `—`）
   - トリアージ: 🔧 Will Fix / 🚫 Won't Fix
   - Won't Fix 行は estimate 4 列（Cost / Future / シグナル / 見積判定）を `—` で埋め、備考に triage.json の reason を要約して記載
   - 備考: 別 PR 推奨や FIXME 付与等の補足、または Won't Fix の理由要約

## 戻り値

`{summary_path, summary_line（<=200 chars。例: "C-1 Maintain / M-2 Downgrade(別PR) / M-3 Alternative"）, maintain_count, downgrade_count, alternative_count, template_id}`。`template_id` は本テンプレートの frontmatter から Read した値をそのまま含める。
