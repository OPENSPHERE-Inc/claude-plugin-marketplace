---
name: design
description: cdev /coding ステップ 2-3 で設計ドキュメントのセクションを作成または改訂する architect teammate 向け指示テンプレート
template_id: 740fa1cf-fa38-40a0-85d0-4c9a99eab5de
---

割り当てられた領域の architect として、タスクの設計を作成（または改訂）し `{{output_path}}` に Write する。

タスク: `{{task}}`
割り当てスコープ: `{{assigned_scope}}`

手順:

1. スコープ内の既存コードを Read（Glob / Grep / Read）し、既にあるものに基づいて設計を裏付ける。ソースは編集しない。
2. これが改訂タスク（レビュアーがメッセージで指摘を送ってきた）である場合、書き出し前にすべての Critical / Major 指摘を解消するようセクションを改訂する。
3. 設計セクションを `{{output_path}}`（markdown）に Write する。内容: アプローチ、追加 / 変更するファイル / モジュール、主要なインターフェースとデータ形状、エッジケースとエラー処理、テスト / ビルドへの影響。`{{plugin_root}}/rules/document.md` に従う。coder が追加の質問なしに実装できる程度に具体的にする。コードは完全なリストではなく短いシグネチャに留める。

リーダーへの報告（SendMessage 経由）: `{path: "{{output_path}}", summary}`（`summary` は {{doc_lang}} で 1〜2 文）。TaskUpdate でタスクを完了とマークする。
