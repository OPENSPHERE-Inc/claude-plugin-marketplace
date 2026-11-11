---
name: phase-respond
description: /creview:rounds ステップ 2.3 およびステップ 2.5 のフィードバックループで /creview:respond をリーダーとして実行するフェーズリーダーサブエージェント用プロンプト
template_id: 8b5e3d7a-4c16-4a92-a7f3-2d9c6b1e8f47
---

`/creview:rounds` の 1 ラウンド分として、`creview:respond` スキルをそのレビュー対応リーダーとして実行する。`{{plugin_root}}/rules/sub-agent.md` を Read し、共通禁止事項を遵守する。

入力:

- レビュードキュメント: `{{document_path}}`（トリアージ / 見積は永続化済み）
- `--commit`: `{{commit_flag}}`
- `--adr`: `{{adr_flag}}`
- ラウンド固有のオーバーライド: `{{overrides}}`

実施内容:

1. `creview:respond` スキルを引数 `{{document_path}}` で起動する（`{{commit_flag}}` が ON の場合は `--commit` を、`{{adr_flag}}` が ON の場合は `--adr` を付す）。そのレビュー対応リーダーとしてステップ 1〜6（フォーマット・ビルド・テスト検証と解釈テスト ⇄ 修正の再実行ループ、コミットステップ、および compile ステップを含む）を実行する。
2. `{{overrides}}` の各項目を、項目が名指しするサブエージェント（名指しが無い場合は全サブエージェント）の起動プロンプトの「ラウンド固有のオーバーライド」セクションに追加する。
3. 下記の `error` が定めるエラーでスキルが止まったのが、ステップ 4 のループを抜けた後（ループの結果は問わない）で、かつステップ 6 の compile が成功する前である場合は、失敗したのがその compile でない限り、`{tmp_dir}` が削除される前にその compile を実行する: `python3 {{plugin_root}}/skills/respond/scripts/compile-review.py {tmp_dir} {{document_path}}`（`{tmp_dir}` はスキルの作業用ディレクトリ）。その compile、またはステップ 4 のループを抜けた後のステップ 6 自身の compile が失敗した場合は、修正はステップ 4 を通過したがその Status をレビュードキュメントに書けなかったことを `error` に含める。

戻り値: `{fix_count, fixed_count, code_changed, workflow_warning, prompt_warning, summary_line, error, template_id}`。`workflow_warning` は respond がステップ 4 で保持した値で、フォーマット／ビルド手順が解決できなかった場合と、環境起因でビルド／テスト検証が完了しなかった場合は非 null、それ以外は null。`prompt_warning` は respond がステップ 4 の後に保持していた値で、AI 向けプロンプトファイルが解釈テストに不合格のまま残ったか未テストだった場合は非 null、それ以外は null。`error` は、スキルがステップ 1〜6 を最後まで実行した場合は警告付きでも null: `workflow_warning` や `prompt_warning` が非 null の場合も、ステップ 4 のループが最後の試行でビルド／テストが失敗したまま抜けた場合も、エラーではない。スキルが中断・終了した場合、またはスクリプトの非ゼロ終了やサブエージェントの `template_id` 不一致が 2 回続くなど、先に進めない失敗でステップが止まった場合は、スキルが表示したエラーとし、スキルが表示しなかった場合は、止まったステップとそこで失敗した内容（コマンドの終了コードとエラー出力、または不一致の `template_id`）を記したメッセージを自分で書く。エラー時は `fix_count` と `fixed_count` を 0、`code_changed` を false、`workflow_warning`・`prompt_warning`・`summary_line` を null として報告する。`template_id` は本テンプレートの frontmatter から Read した値をそのまま含める。
