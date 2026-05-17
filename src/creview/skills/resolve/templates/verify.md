---
name: verify
description: /creview:resolve ステップ 2 で担当指摘を一括検証する検証サブエージェント向けプロンプト
template_id: 8a1f5c9b-2e73-4d64-9c1e-8b3d7f2a5e94
---

担当指摘 `{{ids}}` の検証を一括実施する。`{{plugin_root}}/rules/sub-agent.md` を Read し共通禁止事項を遵守する。

入力:

- レビュードキュメント `{{document_path}}`（Read して各 id の severity / location / description / 末尾フィールドを取得する）。
- 差分ファイル `{{diff_path}}`（Read して今回の変更範囲を把握する。`Status: 🟢 Fixed` の検証では、記載された修正がこの差分に実在するかを照合の基準とする。差分外を根拠に Resolved と判定しない）。

各 id について以下のロジックで Resolved / Feedback / Unresolved を判定し、結果を `{{tmp_dir}}/verifications/{id}.json` に Write する。末尾フィールドは METADATA マーカー間の triage / estimate / status / verification の最終値。

共通追加チェック（コード検証分岐の判定直前に必ず実施。`Status: 🟢 Fixed` / `Triage: 🚫 Won't Fix` / `Estimate: 🔻 Downgrade` の各分岐で適用）:

- コメントの追加・変更があれば `{{plugin_root}}/rules/comment.md` を Read し違反を確認する。違反があれば Feedback とする。
- 人間向けドキュメント（README、API リファレンス等。`.claude/` 配下の AI 向けプロンプトは対象外）の追加・修正があれば `{{plugin_root}}/rules/document.md` を Read し違反を確認する。違反があれば Feedback とする。

`Status: 🟢 Fixed` あり:

1. 参照ファイル＋行を Read し、記載された修正が実在することを確認する:
   - Estimate ▶️ Maintain: 指摘に対する通常修正（ロジック変更含む）が完全に反映されているか。
   - Estimate 🚧 Alternative: `FIXME:` / `TODO:` コメントが該当箇所にあり、Estimate の FIXME 方向性と概ね一致し、将来修正に必要十分か（ロジック変更は期待しない）。
2. 新たな問題（リグレッション / バグ / スタイル違反 / スレッド安全性 / リソースリーク等）の混入を確認する。
3. 共通追加チェックを実施する。
4. 判定: Resolved（正確・完全・新規問題なし）/ Feedback（欠落・不完全・新規問題あり。残課題を記述）。

`Triage: 🚫 Won't Fix` あり:

1. 参照ファイルを Read し、「修正しない」根拠が現在のコードに照らして依然妥当か評価する。
2. 共通追加チェックを実施する。
3. 判定: Resolved（根拠が妥当）/ Feedback（根拠に欠陥がある、または状況が変化した。理由を記述）。

`Estimate: 🔻 Downgrade` あり:

1. 参照ファイルを Read し、格下げ根拠（拡散シグナル / Cost / Future / 理由）が現在のコードに照らして妥当か評価する。
2. 別 PR 推奨の有無と妥当性を確認する（Critical / Major で別 PR 推奨もない場合は特に注意）。
3. 共通追加チェックを実施する。
4. 判定: Resolved（根拠が妥当）/ Feedback（根拠に欠陥がある、または状況が変化した。理由を記述）。

Unresolved として報告するケース:

- `Estimate: 🚧 Alternative` あり、`Status` なし — FIXME 付与未完了。
- `Estimate: ▶️ Maintain` あり、`Status` なし — 修正未完了。
- `Triage: 🔧 Will Fix` のみ — 見積未完了。
- マーカー間にメタデータなし — トリアージ未実施。

`{{tmp_dir}}/verifications/{id}.json` 形式: `{id, severity, trailing_field, outcome (Resolved | Feedback | Unresolved), reason (1〜3 文), memo_value, feedback_detail}`

trailing_field: マーカー内の末尾フィールド（例: `Status: 🟢 Fixed` / `Triage: 🚫 Won't Fix` / `(empty)`）。

`reason` / `memo_value` の説明文 / `feedback_detail` の散文は、`{{document_path}}` の既存 Finding 説明と同じ言語で記述する（`✅ Verified` / `💬 Feedback` ラベルと絵文字は固定）。

memo_value:

- Resolved: `✅ Verified — {検証結果}`
- Feedback: `💬 Feedback — {不足点と完全解決のために必要なこと}`
- Unresolved: `""`

feedback_detail（outcome == Feedback のみ含める）: `{description, current_state, issue, suggestion}`

戻り値: `{items: [{id, outcome}, ...], template_id}`（reason / memo_value / feedback_detail 等の本文は戻り値に含めない。これらは `verifications/{id}.json` ファイル側にのみ書き出す）。`template_id` は本テンプレートの frontmatter から Read した値をそのまま含める。
