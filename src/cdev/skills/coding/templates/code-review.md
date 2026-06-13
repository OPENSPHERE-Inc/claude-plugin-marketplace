---
name: code-review
description: cdev /coding ステップ 6（ループ内品質ゲート）で、生成されたコードをレビューするレビュアー teammate 向けの指示テンプレート
template_id: 4abf814d-2e3e-4bec-8ff8-45c9a176b01f
---

`{{diff_path}}` を Read し、ループ内品質ゲートとしてタスクで生成されたコードをレビューする。

タスク: `{{task}}`
設計セクション（意図する挙動）: `{{design_paths}}` の全ファイルを Read する。
スコープマップ（coder → スコープ）: `{{scope_map}}`

ルール:

- ツール使用は Read / Glob / Grep / Bash(grep/ls/find) に限定する。変更ファイルを Read して周辺コードを確認する。git の再実行は不要（差分は `{{diff_path}}` にある）。
- 設計・タスクに対する正しさ、バグ、欠落したエッジケース／エラーハンドリング、セキュリティ、性能、保守性の観点でコードを判定する。`{{plugin_root}}/rules/review.md` を Read し従う。
- 重大度ラベル: Critical（致命的、要修正）/ Major（修正すべき）/ Minor（注意）/ Info（参考）。

ルーティングと報告:

- 対応が必要な所見（Critical / Major）ごとに、所有する `coder-{slug}` に SendMessage する（所有者は所見が関係するファイルから `{{scope_map}}` で解決する）。`file:line`、問題内容、推奨修正方向を {{doc_lang}} で伝える。`line` は対象ファイルを Read して得た実際の行番号であり、差分上の位置ではない。`file:line` と重大度ラベルはそのまま保持する。
- リーダーに報告（SendMessage 経由）: `{critical, major, minor, info}`（各重大度の所見件数。本文なし）。TaskUpdate でタスクを done にする。
