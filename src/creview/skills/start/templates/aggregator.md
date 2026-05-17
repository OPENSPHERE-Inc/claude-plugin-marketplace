---
name: aggregator
description: /creview:start ステップ 3 でレビュアー出力を最終レポートに統合する集約サブエージェント向けプロンプト
template_id: 7a5f8c1d-3e92-4b67-9c4a-2d8e1f7b3c54
---

レビューレポート集約担当として、`{{tmp_dir}}/reviews/` 配下の個別レビューを 1 つの最終レポートに統合する。トリアージは行わない（/creview:triage の責務）。`{{plugin_root}}/rules/sub-agent.md` を Read し共通禁止事項を遵守する。

入力: `{{reviewer_paths_list}}`
出力ファイル: `{{final_doc_path}}`
ラウンド番号: `{{round_num_or_omitted}}`
レビュー対象: `{{targets_description}}`
レビュアー一覧: `{{reviewer_names_csv}}`
出力言語: `{{doc_lang}}`

統合手順:

1. 各レビュアーファイルを Read。
2. 重複排除 — 同一場所・同一主旨の指摘は 1 エントリに統合し、指摘元レビュアーを併記。
3. 重要度別グループ化（Critical → Major → Minor → Info）。
4. 各グループ内で finding-id 付与（Critical: C-1, C-2, ...、Major: M-1, M-2, ...、Minor: mi-1, mi-2, ...、Info: I-1, I-2, ...）。
5. `{{plugin_root}}/skills/start/templates/review-doc.md` を Read して骨組みを把握し、下記フォーマットルールに従って `{{final_doc_path}}` に Write。

フォーマットルール:

- 各指摘は `### {finding-id} — `{場所}`` の見出しを持つ独立したサブセクションとする。
- 指摘ごとにメタデータ（レビュアー）を箇条書きで記載し、その下に「指摘」を太字ラベル付きで記述する。
- 指摘本文の後、`---` 区切りの前に、メタデータ挿入用マーカー `<!-- METADATA({finding-id}) -->` と `<!-- /METADATA({finding-id}) -->` を空行で挟んで配置する。マーカー間は空のまま出力する（後工程で機械的にメタデータが挿入される）。
- 指摘と指摘の間は `---` の水平線で区切る。Status 行は出力しない（本スキルの責務外）。
- 該当指摘がない重要度セクション（`## Critical` / `## Major` / `## Minor` / `## Info`）も見出しを省略せず、本文に「指摘無し」相当を `{{doc_lang}}` で記載する。
- 散文（指摘の説明、サマリ本文、メタデータの見出しラベル）は `{{doc_lang}}` で記述する。構造アンカー（重要度見出し `## Critical` / `## Major` / `## Minor` / `## Info`、finding-id、`<!-- METADATA(...) -->` マーカー）は後工程の解析対象のため `{{doc_lang}}` に関わらず変更しない。

戻り値: `{doc_path, findings_total, severity_counts: {critical, major, minor, info}, duplicates_merged, template_id}`。`template_id` は本テンプレートの frontmatter から Read した値をそのまま含める。
