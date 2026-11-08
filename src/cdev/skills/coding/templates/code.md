---
name: code
description: cdev /coding ステップ 3-4 で設計を実装（または修正）し、ペアの reviewer とレビューセルを回す coder teammate 向け指示テンプレート
template_id: 278bf9bd-53e2-4695-ad40-3fb91374519a
---

割り当てられたファイルの coder として、設計を実装する（または修正フィードバックを反映する）。producer としてレビューセルを回す（`{{plugin_root}}/rules/teammate.md` § レビューセル を参照）。

タスク: `{{task}}`
設計セクション: `{{design_paths}}` 内のすべてのファイルを Read する。
割り当てスコープ: `{{assigned_scope}}`（このスコープ内のファイル、手順 5 のプロンプトレビューがそれらから外部化して追加したテンプレートファイル、およびこのスコープ内の AI 向けプロンプトファイルが呼ぶ新しい外部スクリプトのみ編集する）。
テスト駆動: `{{tdd}}`（プロジェクトにテストスイートがある場合に true）。
ペア reviewer: `{{reviewer}}`
コメント reviewer: `{{comment_reviewer}}`
プロンプト reviewer: `{{prompt_reviewer}}`

手順:

1. 設計セクションとスコープ内の既存コードを Read する。
2. `{{feedback}}` が "(none)" でない場合は最優先で扱う: QA の失敗 — ビルド / テストのエラー、またはプロンプト解釈テストの unclear 項目 — を示す。参照先のファイルを Read し、そこに報告された問題を修正する。
3. 設計および任意のフィードバックを満たすようソースを実装または修正する。プロジェクトの規約、コメントについては `{{plugin_root}}/rules/comment.md`、AI 向けプロンプトファイルについては `{{plugin_root}}/rules/prompt.md` に従う。`{{feedback}}` に応じて AI 向けプロンプトファイルを修正するとき、またはセル内でそれへのレビュー指摘を triage するときは、`{{plugin_root}}/rules/divergence.md` を Read し、§ coder に従う。`{{tdd}}` が true の場合は、AI 向けプロンプトファイル以外をテストファーストで進める: 意図する振る舞いを捉えるテストを先に記述または拡張して失敗を確認し、次にそれが通るまで実装し、テストがグリーンの状態でリファクタする。既存テストを弱めたり削除したりして無理に通すことはしない。
4. コードコメントを追加または変更した場合は、`{{comment_reviewer}}` に `{{plugin_root}}/skills/coding/templates/comment-review.md` を指定して DM する。その際 `changed_scope = {{assigned_scope}}、および書いた新しい外部スクリプト` と `design_paths = {{design_paths}}` を渡す。comment-sensei がコメント違反を修正し、件数を報告し返す。
5. AI 向けプロンプトファイル（`{{plugin_root}}/rules/prompt.md` の定義による）を作成または編集し、かつ `{{prompt_reviewer}}` が "(none)" でない場合は、手順 4 のコメントレビューを依頼したならその報告が返った後に、`{{prompt_reviewer}}` に `{{plugin_root}}/skills/coding/templates/prompt-review.md` を指定して DM する。その際 `changed_files = {作成・変更したプロンプトファイル。この実行で作成したファイルにはその旨を、それ以外のファイルには分かる場合に変更した箇所を添える}`、`design_paths = {{design_paths}}`、`feedback = {{feedback}}` を渡す。prompt-sensei がそれらをセルフチェック・修正・圧縮し、報告し返す。
6. `{{reviewer}}` に変更がレビュー可能になったことを DM し、変更したファイル（AI 向けプロンプトファイルには手順 5 の `changed_files` と同じ注記を添える）、プロンプトレビューが追加したテンプレートファイル、プロンプトレビューが残した違反を列挙する。producer としてセルを回す。セルは reviewer がクローズする。

リーダーへの報告（SendMessage 経由、{{doc_lang}} で記述）: 変更したファイルを、プロンプトレビューが追加したテンプレートファイルも含めて 1 ファイル 1 行（`path` — 変更内容）、コメントを追加・変更したかどうか、プロンプトレビューを依頼した場合はその件数（検出 / 修正 / 残存した違反、圧縮したファイル）、1 行サマリ。
