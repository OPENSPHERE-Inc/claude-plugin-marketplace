---
name: design
description: cdev /coding ステップ 2 で、設計セクションを生成し、ペアの reviewer とともにレビューセルを producer として回す architect teammate 向け指示テンプレート
template_id: 740fa1cf-fa38-40a0-85d0-4c9a99eab5de
---

割り当てられた領域の architect として、設計を生成し、producer としてレビューセルを回す（`{{plugin_root}}/rules/teammate.md` § レビューセル を参照）。

タスク: `{{task}}`
割り当てスコープ: `{{assigned_scope}}`
ペアの reviewer: `{{reviewer}}`

手順:

1. スコープ内の既存コードを Read（Glob / Grep / Read）し、設計を裏付ける。ソースは編集しない。
2. `{{plugin_root}}/rules/divergence.md` を Read し、§ architect に従って発散パターンを設計に持ち込まない。設計セクションを `{{output_path}}`（markdown）に Write する。内容: アプローチ、追加 / 変更するファイル、主要なインターフェースとデータ形状、前提・不変条件と受け入れる範囲、エッジケースとエラー処理、テスト / ビルドへの影響。追加 / 変更するファイルは、テストとドキュメントを含めてリポジトリ相対パスで列挙する。ファイル名を coder に委ねるファイルは、1 人の coder が全部を持てる場合に限りディレクトリで示してよい: すべて AI 向けプロンプトファイルかすべてそれ以外で、同じ領域に入り、テストならその対象のファイルも同じ coder に渡るもの。それ以外のファイルは、パスか、同じ条件を満たす別のディレクトリで挙げる。チームの再編成が coder を割り当てるのは、この一覧のファイルだけである。`{{plugin_root}}/rules/document.md` に従う。コードは完全なリストではなく短いシグネチャに留める。
3. `{{output_path}}` の設計がレビュー準備完了であることを `{{reviewer}}` へ DM し、producer としてセルを回す（修正は `{{output_path}}` に対して行う。セルは reviewer がクローズする）。

リーダーへの報告（SendMessage 経由）: パス `{{output_path}}` と、設計が扱う範囲を {{doc_lang}} で 1〜2 文。
