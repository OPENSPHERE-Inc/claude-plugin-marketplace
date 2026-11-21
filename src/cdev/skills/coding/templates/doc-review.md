---
name: doc-review
description: cdev /coding ステップ 3-4（ループ内品質ゲート）で writer のドキュメント変更を、コードとの整合を含めてレビューし、ペアの writer とレビューセルを resolve する reviewer teammate 向け指示テンプレート
template_id: 9771b927-1003-44a9-be83-dd33ddfa5d99
---

`{{producer}}` が生成したドキュメントをレビューし、reviewer としてセルを resolve する（`{{plugin_root}}/rules/teammate.md` § レビューセル を参照）。最大 `{{review_rounds}}` ラウンドまで。

タスク: `{{task}}`
設計セクション（意図する変更）: `{{design_paths}}` の全ファイルを Read する。
この実行の変更: `{{diff_path}}`
Producer: `{{producer}}` | セルタスク: `{{cell_task}}`

producer が準備完了を通知したら、準備完了メッセージに列挙されたファイルを Read し、そこに記録された乖離を受け取って、次を判定する:

- 変更したファイルがコードについて述べること — 挙動、インターフェース、オプション、既定値、パス、要件、例 — が、`{{target_dir}}` にあるコードの現状（`{{diff_path}}` にあるこの実行の変更を含む）と整合しているか。コードそのものを読んで判定する。
- この実行のコード変更が、変更したファイルの未変更部分を誤りにしていないか。
- 設計が producer のスコープに求めるドキュメント変更がそろっているか。
- 変更したファイル同士が矛盾しないか。
- それらが `{{plugin_root}}/rules/document.md` に従っているか。

`{{plugin_root}}/rules/teammate.md` § レビューセル の判断の優先順位にあるドキュメントセルの規則に従い、設計やタスクと食い違うコードに従った記述は、producer がその乖離を記録していれば指摘にしない。記録していなければ、修正方針を乖離の記録とする Major の指摘にし、ドキュメントを変える修正方針にはしない。この実行が変えておらず、誤りにもしていない記述は範囲外とし、挙げても Info とする。ツール使用は Read / Glob / Grep / Bash(grep/ls/find) と、ターニングポイントを読むための読み取り専用の `git log` / `git show` / `git diff` に限定する。一切編集しない。

重大度ラベル: Critical（読み手が頼る記述がコードと矛盾する）/ Major（設計が求めるドキュメント変更の欠落、設計やタスクと食い違うコードに従った記述で乖離が記録されていないもの、読み手を誤った使い方に導く記述、レンダリングを壊す記法）/ Minor（読み手を誤らせない文言・体裁）/ Info（参考）。対応が必要 = Critical / Major。

セル `{{cell_task}}` についてセルプロトコルを回す: 対応が必要な所見を `file:line` と問題内容・推奨修正方向として `{{producer}}` に DM し（`line` はファイルを Read して得た実際の行番号。文面は {{doc_lang}} で、重大度ラベルはそのまま）、重大度別の件数を 1 行（`Critical N / Major N / Minor N / Info N`）でリーダーへ報告する。
