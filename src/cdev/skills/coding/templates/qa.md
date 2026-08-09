---
name: qa
description: cdev /coding ステップ 4 で反映先プロジェクトのフォーマット・ビルド・テストを 1 回実施し、失敗時に修正担当の専門家を判定する QA タスク（dev-helper）向けプロンプト
template_id: 6a711cba-0da8-4177-a41f-ddb4cf2a6e1f
---

反映先プロジェクトのフォーマット・ビルド・テストを 1 回ずつ実施し（テストはテスト手順が解決された場合のみ）、失敗時に修正担当の専門家を判定する。修正ループは行わない（coder が修正した後にリーダーが本担当を再起動する）。ソース変更はフォーマッタ自動修正のみ可（ロジック変更禁止）。

入力: 作業ディレクトリ `{{tmp_dir}}`、作業ツリー差分 `{{diff_path}}`（`fetch-diff.sh` 出力）、試行番号 `{{attempt_num}}`（情報のみ）。

コマンド実行 CWD はプロジェクトルート。相対パスのみ使用する。パイプ経由の `tee` / `Tee-Object` は使わず、コンパウンドコマンド（`;` / `&&`）も使用しない（Bash ツールが終了コードを自動返却する）。

手順:

1. `{{plugin_root}}/rules/build-format-detection.md` の手順でフォーマット／ビルド／テストコマンドと `workflow_source` を解決する。`workflow_source == "none"` の場合は何も実行せず手順 5 に進む。
2. `{{diff_path}}` を Read し変更内容を分類する。あるステージの結果に影響し得ない変更のみ（コメント／ドキュメント／非ソースのみ）の場合、当該ステージをスキップ対象とする（`ran = false`、完了報告にスキップを記載）。判断に迷う場合は実行する。
3. フォーマット（format コマンドが解決された場合のみ）: 検証（dry-run）形式があれば実行し違反時は自動修正形式を適用、無ければ変更ファイルに自動修正形式を適用する。対象選別は解決した記述子に従う。
4. ビルド、続いてテスト:
   - ビルド（build コマンドが解決され、ステージがスキップ対象でない場合。`build_ran = true`）: configure コマンドがあれば先に実行し、続いてビルドを実行、出力を `{{tmp_dir}}/build.log` へリダイレクトする。configure かビルドが非ゼロ終了した時点で `failure.stage = "build"` を設定し手順 6 へ。
   - テスト（test コマンドが解決され、ビルド未失敗、ステージがスキップ対象でない場合。`test_ran = true`）: テストを実行し、出力を `{{tmp_dir}}/build.log` に append する。非ゼロ終了時は `failure.stage = "test"` を設定し手順 6 へ。
5. 目視チェックのみ（`workflow_source == "none"`）: 何も実行しない（`build_ran` / `test_ran` は false）。変更ファイルを Read し、目視で明白な破損（構文崩れ、未解決シンボル）を確認する。`workflow_warning` に「フォーマット／ビルド／テスト手順が宣言されておらず自動検証をスキップした。`.claude/rules/build-format.md` の追加を推奨」を設定する。明白な破損がある場合のみ `failure.stage = "visual"` を設定する。
6. 失敗時（`failure != null`）: ログ（`{{tmp_dir}}/build.log`。目視モードでは存在しない）とエラー発生ファイルを Read し、原因を分析して `error_summary` / `error_files` / `fix_guidance` を設定する。`{{plugin_root}}/rules/agents-detection.md` の手順で修正担当の専門家を解決し（マッチ対象はエラー内容——言語／ビルドシステム／サブシステム／テストフレームワーク）、`suggested_specialist` に記録する。
7. `{{tmp_dir}}/qa-result.jsonl` を Write する。

`{{tmp_dir}}/qa-result.jsonl` 形式:

```
{"workflow_source": "build-format.md | CLAUDE.md | README.md | none", "workflow_warning": <string|null>, "format": {"format_violations_fixed": <int>}, "build": {"ran": <bool>, "success": <bool>}, "test": {"ran": <bool>, "success": <bool>}, "failure": {"stage": "build|test|visual", "error_summary": <string|null>, "error_files": ["src/foo:42", ...]|null, "suggested_specialist": <string|null>, "fix_guidance": <string|null>, "log_path": "{{tmp_dir}}/build.log"}|null}
```

リーダー（`SendMessage` の `to: "main"`）へ完了を 1 行 <=200 chars で報告する（例: "build-format.md / format ok / build ok / test ok"）。
