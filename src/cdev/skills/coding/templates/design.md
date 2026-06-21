---
name: design
description: cdev /coding ステップ 2 で、設計セクションを生成し、ペアの reviewer とともにレビューセルを producer として回す architect teammate 向け指示テンプレート
template_id: 740fa1cf-fa38-40a0-85d0-4c9a99eab5de
---

割り当てられた領域の architect として、設計を生成し、producer としてレビューセルを回す（`{{plugin_root}}/rules/teammate.md` § レビューセル を参照）。

タスク: `{{task}}`
割り当てスコープ: `{{assigned_scope}}`
ペアの reviewer の agentId: `{{reviewer}}`

手順:

1. スコープ内の既存コードを Read（Glob / Grep / Read）し、設計を裏付ける。ソースは編集しない。
2. 設計セクションを `{{output_path}}`（markdown）に Write する。内容: アプローチ、追加 / 変更するファイル / モジュール、主要なインターフェースとデータ形状、エッジケースとエラー処理、テスト / ビルドへの影響。`{{plugin_root}}/rules/document.md` に従う。コードは完全なリストではなく短いシグネチャに留める。
3. `{{output_path}}` の設計がレビュー準備完了であることを `{{reviewer}}` へ DM する。セルを回す: reviewer が送る各指摘を triage し — `{{output_path}}` で修正するか、1 行の理由で却下する — 再レビューの準備完了を伝える。reviewer が resolve しセルをクローズする。

リーダーへの報告（SendMessage 経由）: `{path: "{{output_path}}", summary}`（`summary` は {{doc_lang}} で 1〜2 文）。
