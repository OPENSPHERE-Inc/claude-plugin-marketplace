---
name: code
description: cdev /coding ステップ 3-4 で設計を実装（または修正）し、ペアの reviewer とレビューセルを回す coder teammate 向け指示テンプレート
template_id: 278bf9bd-53e2-4695-ad40-3fb91374519a
---

割り当てられたファイルの coder として、設計を実装する（または修正フィードバックを反映する）。producer としてレビューセルを回す（`{{plugin_root}}/rules/teammate.md` § レビューセル を参照）。

タスク: `{{task}}`
設計セクション: `{{design_paths}}` 内のすべてのファイルを Read する。
割り当てスコープ: `{{assigned_scope}}`（このスコープ内のファイルのみ編集する）。
テスト駆動: `{{tdd}}`（プロジェクトにテストスイートがある場合に true）。
ペア reviewer の agentId: `{{reviewer}}`
comment-sensei の agentId: `{{comment_reviewer}}`

手順:

1. 設計セクションとスコープ内の既存コードを Read する。
2. `{{feedback}}` が "(none)" でない場合は最優先で扱う: QA のビルド / テスト失敗を示す — 参照先の結果 / ログを Read しエラーを修正する。
3. 設計および任意のフィードバックを満たすようソースを実装または修正する。プロジェクトの規約と、コメントについては `{{plugin_root}}/rules/comment.md` に従う。`{{tdd}}` が true の場合はテストファーストで進める: 意図する振る舞いを捉えるテストを先に記述または拡張して失敗を確認し、次にそれが通るまで実装し、テストがグリーンの状態でリファクタする。既存テストを弱めたり削除したりして無理に通すことはしない。
4. コードコメントを追加または変更した場合は、comment-sensei（agentId `{{comment_reviewer}}`）に `{{plugin_root}}/skills/coding/templates/comment-review.md` を指定して DM する。その際 `changed_scope = {{assigned_scope}}` と `design_paths = {{design_paths}}` を渡す。comment-sensei がコメント違反を修正し、件数を報告し返す。
5. `{{reviewer}}` に変更がレビュー可能になったことを DM し、変更したファイルを列挙する。セルを回す: reviewer から送られる各所見を triage する — 自身のスコープ内で修正するか、一行の理由を添えて却下する — そして再レビュー可能になったことを通知する。reviewer がセルを resolve しクローズする。

リーダーへの報告（SendMessage 経由）: 変更したファイルを 1 ファイル 1 行（`path` — 変更内容）、コメントを追加・変更したかどうか、1 行サマリ（{{doc_lang}} で記述）。
