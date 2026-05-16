---
name: fix
description: /creview:respond ステップ 2 で担当指摘を修正する修正サブエージェント向けプロンプト
template_id: 2f8a1c5d-7b94-4e63-a1c8-5d3f9b2e7a14
---

担当指摘 `{{ids}}` を順次修正する。`{{plugin_root}}/rules/sub-agent.md` を Read し共通禁止事項を遵守する。

入力（id == "{finding-id}" で引く）:

- レビュードキュメント `{{document_path}}` — METADATA マーカー前後から description / location を取得し、メタデータブロックから当該指摘の確定判定を取得する: `Triage:`（Will Fix + 理由）および `Estimate:`（▶️ Maintain または 🚧 Alternative。Cost / Future / Signals を伴い、Alternative の場合は FIXME 付与の方向性も含む）。フィールドが繰り返す場合は最後の値を使う。
- `{{tmp_dir}}/targets.json` — `items[]` が各 id の `assignee` と `estimate`（Maintain | Alternative）を与える。

各 id について:

1. 関連ソースを Read してコンテキスト把握。
2. 修正実装（CLAUDE.md のコーディング規約準拠）:
   - Estimate ▶️ Maintain: 指摘内容に沿った通常の修正。
   - Estimate 🚧 Alternative: FIXME: コメント追加のみ（ロジック変更なし）。当該指摘の `Estimate:` メタデータに記載された FIXME 付与の方向性に沿った文言を使う。
3. セルフレビュー: 変更箇所再読、新たな問題（リグレッション・スレッド安全性・リソースリーク等）の混入を確認、見つけたら報告前に修正。
4. `{{tmp_dir}}/statuses/{finding-id}.json` に Write。

並列化制約（複数 id を担当する場合）:

- 同一ファイルに影響する複数 ids は順次処理（書き込み競合防止）。
- 異なるファイルに影響する ids は並列処理可。

`{{tmp_dir}}/statuses/{finding-id}.json` 形式: `{id, specialist, description（修正内容の簡潔な説明）, memo_value}`

memo_value 形式:

- Maintain: `🟢 Fixed — {修正内容}`
- Alternative: `🟢 Fixed — FIXME コメントを {ファイル:行} に付与`（description にも同趣旨を含める）

戻り値: `{items: [{id, path}, ...], template_id}`（items は担当 ids 全件分）。`template_id` は本テンプレートの frontmatter から Read した値をそのまま含める。
