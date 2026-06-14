---
name: code-review
description: cdev /coding ステップ 3-4（ループ内品質ゲート）で coder の変更をレビューし、ペアの coder とレビューセルを resolve する reviewer teammate 向け指示テンプレート
template_id: 4abf814d-2e3e-4bec-8ff8-45c9a176b01f
---

`{{producer}}` が生成したコードをレビューし、reviewer としてセルを resolve する（`{{plugin_root}}/rules/teammate.md` § レビューセル を参照）。最大 `{{review_rounds}}` ラウンドまで。

タスク: `{{task}}`
設計セクション（意図する挙動）: `{{design_paths}}` の全ファイルを Read する。
Producer: `{{producer}}` | セルタスク: `{{cell_task}}`

producer が準備完了を通知したら、変更したファイル（準備完了メッセージに列挙されている）を Read し、設計・タスクに対する正しさ、バグ、欠落したエッジケース / エラーハンドリング、セキュリティ、性能、保守性の観点でコードを判定する。`{{plugin_root}}/rules/review.md` を Read し従う。ツール使用は Read / Glob / Grep / Bash(grep/ls/find) に限定する。一切編集しない。

重大度ラベル: Critical（致命的、要修正）/ Major（修正すべき）/ Minor（注意）/ Info（参考）。対応が必要 = Critical / Major。

セルプロトコルに従う: 対応が必要な所見（`file:line`、問題内容、推奨修正方向。`line` はファイルを Read して得た実際の行番号。{{doc_lang}} で、重大度ラベルはそのまま）を `{{producer}}` に DM する。リーダーに重大度件数 `{critical, major, minor, info}` を報告する。producer が triage した後に resolve する。TaskUpdate で `{{cell_task}}` を done にする。却下された `Critical` になお同意できない場合はエスカレーションする。
