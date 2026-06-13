---
name: design-review
description: cdev /coding ステップ 3 で設計ドキュメントをレビューする reviewer teammate 向け指示テンプレート（ループ内品質ゲート）
template_id: 448ee08a-0284-4066-9de9-9f82e9078914
---

ループ内の品質ゲートとして、タスクの設計をレビューする。

タスク: `{{task}}`
設計セクション: `{{design_paths}}` 内のすべてのファイルを Read する。
スコープマップ（architect → scope）: `{{scope_map}}`

ルール:

- 使用ツールは Read / Glob / Grep / Bash(grep/ls/find) に限定。実現可能性を判断する際は設計が参照する既存コードを必要に応じて Read する。一切編集しない。
- 設計を、タスクに対する正しさと完全性、実現可能性、欠落したエッジケース / エラー処理、インターフェースとデータ形状の妥当性、テスト容易性、既存コードへのリスクの観点で判断する。`{{plugin_root}}/rules/review.md` を Read して従う。
- 重要度ラベル: Critical（設計が誤っている、またはタスクを満たさない）/ Major（重大なギャップまたはリスク）/ Minor（改善）/ Info（参考）。

ルーティングと報告:

- 対応すべき各指摘（Critical / Major）について、担当の `architect-{slug}` へ SendMessage する（指摘が関わる設計セクション / 領域から、`{{scope_map}}` を用いて担当を特定する）。セクションまたは領域、問題、推奨する修正方針を {{doc_lang}} で述べる。重要度ラベルはそのまま。
- リーダーへの報告（SendMessage 経由）: `{critical, major, minor, info}`（各重要度の指摘件数。本文は含めない）。TaskUpdate でタスクを完了とマークする。
