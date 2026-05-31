---
name: comment-review
description: /creview:respond ステップ 3 で修正サブエージェント（ステップ 2）が追加・変更したコメントをコメント規律に照らしてレビューし、違反があれば修正する comment-sensei 向けプロンプト
template_id: 4a8e2d6f-9b15-4c73-8a2d-7f1e5c9b3d68
---

修正サブエージェント（ステップ 2）が変更した各ファイルのコメントを `{{plugin_root}}/rules/comment.md` の規律に照らしてレビューし、違反があれば修正する。`{{plugin_root}}/rules/sub-agent.md` を Read し共通禁止事項を遵守する。

## 入力

- `{{tmp_dir}}/statuses/*.json` を Read し、`items[].path` から修正済みファイルパス一覧を得る。
- `{{document_path}}`（レビュードキュメント）を Read し、各修正が対応した指摘の趣旨（Finding 本文・location・triage / estimate メタデータ）を把握する。コメント調整時に趣旨を棄損しないための参照。

## 実施内容

1. `{{plugin_root}}/rules/comment.md` を Read。
2. 各修正済みファイルについて、`git diff HEAD -- {path}` と `git diff HEAD~ -- {path}` の両方から追加・変更されたコメント行を抽出する。コメント記号は言語別（`//` / `#` / `/* */` / `<!-- -->` 等）。
3. 全ファイルで追加・変更コメントが 1 件もない場合: 何もせず手順 5 に進む（`fix_count: 0`）。
4. 抽出した追加・変更コメントが `comment.md` の規律に違反している場合（複数段落の正当化、自明な what 言い換え、チャット文脈・移植経緯依存の記述、変更履歴的記述、冗長な FIXME / TODO 等）、Edit で当該コメントを簡潔化・削除・FIXME 化のいずれかにより修正する。コードのロジックは変更しない。
   - 調整は形式上の違反のみを対象とする。当該コメントが対応する指摘（`{{document_path}}` の Finding を file:line と内容で対応付け）が要求する実質——特に Alternative 見積で方向性指定された FIXME の要点——は保持し、趣旨を棄損しない。規律順守と趣旨保持が両立しない場合は削除せず、簡潔化または FIXME 化で要点を残す。
5. 戻り値を返す。

## 戻り値

`{reviewed_paths, fix_count, template_id}`

- `reviewed_paths`: 追加・変更コメントが検出されレビューしたファイルパス一覧（空配列もあり）
- `fix_count`: 修正したコメントの件数（0 ならコメント修正なし）

`template_id` は本テンプレートの frontmatter から Read した値をそのまま含める。
