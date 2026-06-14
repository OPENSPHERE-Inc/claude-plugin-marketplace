---
name: comment-review
description: cdev /coding ステップ 3 で coder が自身のコードセル内から comment-sensei を起用し、変更したコメントをレビュー・修正させるためのプロンプト
template_id: 8004286a-f4b2-4a6a-a3cb-9adc9ea370f2
---

coder が追加・変更したコメントを `{{plugin_root}}/rules/comment.md` の規律に照らしてレビューし、違反を修正する。

入力:

- 変更スコープ: `{{changed_scope}}`（coder が編集したファイル / ディレクトリ）。`git diff -- {{changed_scope}}` を実行して、追加・変更されたコメント行を抽出する（記号は言語別: `//` / `#` / `/* */` / `<!-- -->` 等）。
- `{{design_paths}}` の設計セクションを Read し、コードが実装する意図を把握する。コメント調整時に趣旨を歪めないための参照。

手順:

1. `{{plugin_root}}/rules/comment.md` を Read する。
2. 追加・変更されたコメントが 1 件もない場合は `fix_count: 0` で終了する。
3. 規律に違反するコメント（複数段落の正当化、自明な what 言い換え、チャット文脈・移植経緯依存の記述、変更履歴的記述、冗長な FIXME / TODO）は、Edit で簡潔化・削除・短い FIXME 化のいずれかにより修正する。コードのロジックは変更せず、コードが要求する実質は保持する。

起用元の coder への報告（SendMessage 経由）: `{reviewed_paths, fix_count}`。`reviewed_paths`: 追加・変更コメントが検出されレビューしたファイル一覧（空配列もあり）。`fix_count`: 修正したコメント件数。
