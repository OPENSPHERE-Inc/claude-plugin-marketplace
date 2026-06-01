---
name: fix
description: /creview:respond ステップ 2 で担当指摘を修正する修正サブエージェント向けプロンプト
template_id: 2f8a1c5d-7b94-4e63-a1c8-5d3f9b2e7a14
---

担当指摘 `{{ids}}` を順次修正する。`{{plugin_root}}/rules/sub-agent.md` を Read し共通禁止事項を遵守する。

入力（id == "{finding-id}" で引く）:

- レビュードキュメント `{{document_path}}` — METADATA マーカー前後から description / location を取得し、メタデータブロックから当該指摘の確定判定を取得する: `Triage:`（Will Fix + 理由）および `Estimate:`（▶️ Maintain または 🚧 Alternative。Cost / Future / Signals を伴い、Alternative の場合は FIXME 付与の方向性も含む）。フィールドが繰り返す場合は最後の値を使う。
- `{{tmp_dir}}/targets.json` — `items[]` が各 id の `assignee`、`estimate`（Maintain | Alternative）、`fix_plan`（`/creview:triage` の見積で確定した修正プラン。各エントリ `{file:line — 変更内容}` の文字列配列。空配列のこともある）を与える。

各 id について:

1. targets.json の当該 id の `fix_plan` を修正の起点とする。関連ソースを Read して現在のコンテキストを把握する。fix_plan の行番号は見積時点のものでソース変更によりずれている可能性があるため、意図として扱い現在のソースに照合して適用する。`fix_plan` が空（旧フォーマット doc 等で `Plan:` セグメントが無い）の場合は description / `Estimate:` から修正方針を導出する。
2. 修正実装（CLAUDE.md のコーディング規約準拠）:
   - Estimate ▶️ Maintain: fix_plan の各編集を適用する通常の修正。
   - Estimate 🚧 Alternative: FIXME: コメント追加のみ（ロジック変更なし）。fix_plan に記載のコメント文言（無ければ `Estimate:` の FIXME 付与方向性）に沿う。
3. セルフレビュー: 変更箇所再読、新たな問題（リグレッション・スレッド安全性・リソースリーク等）の混入を確認、見つけたら報告前に修正。
4. 修正にコメントの追加・変更が含まれる場合、`{{plugin_root}}/rules/comment.md` を Read し、追加・変更したコメントが同規律に違反していないかセルフチェックする。違反があれば報告前に修正する。
5. `{{tmp_dir}}/statuses/{finding-id}.json` に Write。

並列化制約（複数 id を担当する場合）:

- 同一ファイルに影響する複数 ids は順次処理（書き込み競合防止）。
- 異なるファイルに影響する ids は並列処理可。

`{{tmp_dir}}/statuses/{finding-id}.json` 形式: `{id, specialist, verdict（targets.json の estimate。Maintain | Alternative）, description（修正内容の簡潔な説明）, memo_value}`

`description` および `memo_value` の散文は、`{{document_path}}` の既存 Finding 説明と同じ言語で記述する（`🟢 Fixed` ラベルと絵文字は固定）。

memo_value 形式:

- Maintain: `🟢 Fixed — {修正内容}`
- Alternative: `🟢 Fixed — FIXME コメントを {ファイル:行} に付与`（description にも同趣旨を含める）

戻り値: `{items: [{id, path}, ...], template_id}`（items は担当 ids 全件分）。`template_id` は本テンプレートの frontmatter から Read した値をそのまま含める。
