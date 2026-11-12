---
name: phase-triage
description: /creview:rounds ステップ 2.2 およびステップ 2.5 のフィードバックループで /creview:triage をリーダーとして実行するフェーズリーダーサブエージェント用プロンプト
template_id: 6d2a8f4c-1e93-4b57-9c8a-3f7b2d6e1a95
---

`/creview:rounds` の 1 ラウンド分として、`creview:triage` スキルをそのトリアージリーダーとして実行する。`{{plugin_root}}/rules/sub-agent.md` を Read し、共通禁止事項を遵守する。

入力:

- レビュードキュメント: `{{document_path}}`
- 過去ラウンドのレビュードキュメントのパス: `{{previous_round_doc_paths}}`（Round 1 では `(なし)`）
- `--adr`: `{{adr_flag}}`
- ラウンド固有のオーバーライド: `{{overrides}}`

実施内容:

1. `creview:triage` スキルを引数 `{{document_path}}` で起動し（`{{adr_flag}}` が ON の場合は `--adr` を付す）、そのトリアージリーダーとしてステップ 1〜3（compile ステップを含む）を実行する。スキルが中断しない限り、作業用ディレクトリは削除せず残す — 戻った後に `summary_path` がそこから Read される。
2. 自分が発行するすべてのサブエージェント起動プロンプトの「ラウンド固有のオーバーライド」セクションに以下を追加する:
   - トリアージサブエージェント: `previous_round_doc_paths` は `{{previous_round_doc_paths}}`。トリアージ報告に Will Fix 件数を明記する（0 件の場合も明示）。
   - 見積サブエージェント: 過去ラウンドのレビュードキュメントは参照しない（バイアス回避）。拡散シグナル e（FIXME 起源の Will Fix）を判定する際、当該指摘がレビュー本文や対象ファイル中の `FIXME:` / `TODO:` を起点としているかを確認する。
   - `{{overrides}}` の各項目: 項目が名指しするサブエージェントの起動プロンプトに付す。名指しが無い項目は全サブエージェントに付す。
3. `will_fix_count` が 0 の場合も compile ステップを実行する（Won't Fix のトリアージ値を永続化するため）。
4. 下記の `error` が定めるエラーでスキルが止まった場合は、残りのステップを実行せず、各カウントを 0、`summary_path` と `summary_line` を null として戻る。`creview:triage` のステップ 1 の戻り値に `error` が含まれる場合もこのエラーに当たり、受領したメッセージを `error` とする。

戻り値: `{will_fix_count, wontfix_count, flipped_count, maintain_count, alternative_count, downgrade_count, summary_path, summary_line, tmp_dir, error, template_id}`。`tmp_dir` はスキルが作成した作業用ディレクトリで、エラー時も報告し、スキルが作成前に止まった場合は null とする。`flipped_count` は裁定段が反転した判定の件数で、トリアージサブエージェントの戻り値をそのまま転記する。`error` は、スキルがステップ 1〜3 を最後まで実行した場合は警告付きでも null。スキルが中断・終了した場合、またはスクリプトの非ゼロ終了や、サブエージェントの `template_id` 不一致の 2 回連続など、先に進めない失敗でステップが止まった場合は、スキルが表示したエラーとし、スキルが表示しなかった場合は、止まったステップとそこで失敗した内容（コマンドの終了コードとエラー出力、または不一致の `template_id`）を記したメッセージを自分で書く。見積ステージをスキップした場合、`maintain_count` / `alternative_count` / `downgrade_count` は 0、`summary_path` は null として報告する。`template_id` は本テンプレートの frontmatter から Read した値をそのまま含める。
