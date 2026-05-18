---
name: final-report-compile
description: /creview:rounds ステップ 3 で全ラウンドのレビュードキュメントから最終レポートを生成する最終レポート編纂サブエージェント向けプロンプト
template_id: 4f8a2d1c-9b35-4e67-a2c1-8b5d3f9e7a16
---

全ラウンドのレビュードキュメントから最終レポートを生成する。`{{plugin_root}}/rules/sub-agent.md` を Read し共通禁止事項を遵守する。

入力:

- 各ラウンドのレビュードキュメント: `{{round_doc_paths}}`（例: `Round 1 → {round1_doc_path}, Round 2 → {round2_doc_path}, ...`）
- 各ラウンドの統計（参考情報）: `{{round_stats}}`（例: `Round 1: findings=N, will_fix=N, maintain=N, alternative=N, downgrade=N, fixed=N, wontfix=N, feedback_attempts=N, unresolved=N, code_changed=<bool>, ...`）。`workflow_warning="..."` が付与されているラウンドは、そのラウンドの respond でフォーマット／ビルド手順が解決できず自動検証をスキップしたことを示す。
- レポートテンプレート: `{{template_path}}`
- 出力先: `{{report_path}}`
- 言語: `{{language}}`

実施内容:

1. テンプレート markdown を Read し構造（`<...>` placeholder、表構造、将来推奨セクションのサブセクション例）を把握する。
2. 各ラウンド md の `<!-- METADATA(id) --> 〜 <!-- /METADATA(id) -->` から Triage / Estimate / Status / Verification 値を抽出し、個別指摘の詳細（重要度 / 場所 / 概要 / 対応 / 別 PR 推奨の有無等）を取得する。
3. テンプレートの統計サマリ・全指摘一覧・将来推奨・レビュードキュメント一覧を埋めて `{{report_path}}` に Write する。
   - `{{round_stats}}` に `workflow_warning` を持つラウンドが 1 つ以上ある場合、テンプレートの「ビルド／フォーマット検証メモ」セクションに該当ラウンドと警告内容を記載する。1 つも無い場合はそのセクションを「全ラウンドで自動検証を実施」と記載する。
   - 「将来の対応推奨項目」セクションへの集約規則:
     - 候補: Triage: 🚫 Won't Fix / Estimate: 🔻 Downgrade / Estimate: 🚧 Alternative のうち、別 PR 推奨が理由欄に明記された指摘。
     - 除外: 候補のうち、後ラウンドで同一箇所・同一内容の指摘が Status: 🟢 Fixed として解決済みのものは本セクションに含めない（既に修正済みのためロードマップに残す必要がない）。同一性判定は `file:line` と指摘要旨の一致で行う。判定が困難な場合は除外せず、推奨理由欄に判定保留の旨を添える。
     - 形式: 各指摘につきテンプレート例に倣って 1 サブセクションを起こす。見出しは `### R{元ラウンド番号}-{元 ID} — `file:line`` 形式（複数ラウンドにまたがる ID 衝突を避けるため必ずラウンド番号を冠する）。サブセクション内に重要度 / 元ラウンド / 元 ID / 元レビュアー / 判定 を箇条書きで掲載し、続けて `**指摘:**` ラベルの後に元レビュードキュメントの当該指摘本文（`### {id} — ...` 直下から `---` 直前までの範囲のうち、`<!-- METADATA(id) --> 〜 <!-- /METADATA(id) -->` ブロックを除く部分）を**省略せず全文転記**する。サブセクションは `---` で区切る。

戻り値: `{report_path, template_id}`。`template_id` は本テンプレートの frontmatter から Read した値をそのまま含める。
