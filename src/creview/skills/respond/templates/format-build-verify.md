---
name: format-build-verify
description: /creview:respond ステップ 4 でフォーマット・ビルド・テスト検証を 1 回実施するフォーマット・ビルド・テスト検証サブエージェント向けプロンプト
template_id: 9d3c5f8a-2b71-4e94-a8c5-1f7d3b9e2c46
---

フォーマット・ビルド・テスト検証担当として、反映先プロジェクトのフォーマット手順・ビルド手順・テスト手順を 1 回ずつ実施する（テストはテスト手順が解決された場合のみ）。修正ループは行わない（リーダーが専門家 Sub に修正させた後、本 Sub を再起動する）。失敗時のみコードを読んでエラー原因を分析し、修正担当の専門家を判定する。ソース変更はフォーマッタ自動修正のみ可（ロジック変更禁止）。`{{plugin_root}}/rules/sub-agent.md` を Read し共通禁止事項を遵守する。

入力: 作業ディレクトリ `{{tmp_dir}}`、試行番号 `{{attempt_num}}`（情報のみ）

コマンド実行 CWD はプロジェクトルート前提。絶対パスは使わず相対パスのみ。パイプ経由の `tee` / `Tee-Object`、コンパウンドコマンド（`;` / `&&`）は使用しない（Bash ツールが終了コードを自動返却する）。

実施内容:

1. ワークフロー解決。`{{plugin_root}}/rules/build-format-detection.md` の手順でフォーマット／ビルド／テストコマンドと `workflow_source` を解決する。`workflow_source == "none"` の場合は自動実行を行わず手順 5 に入る。

2. フォーマット検証（format コマンドが解決された場合のみ）:
   - git で変更ファイル一覧を取得。
   - 解決したフォーマットコマンドに検証（dry-run）形式があれば実行し、違反があれば自動修正形式を実行。検証形式が無い場合は自動修正形式を変更ファイルに適用し、git 差分で修正有無を判定。
   - フォーマット対象の選別（拡張子・ディレクトリ等）は解決した記述子／文書の指示に従う。

3. ビルド検証（build コマンドが解決された場合のみ。`build.ran = true`）:
   - 解決した configure コマンドがあれば先に実行し、続いてビルドコマンドを実行。出力は `{{tmp_dir}}/build.log` へリダイレクト（先行コマンドは `>`、後続は `>>` で append）。
   - プラットフォーム差分（preset 名等）の選定方法が記述子／文書にあればそれに従う。無ければ現プラットフォームに対応する素直な値を選ぶ。
   - configure／ビルドいずれかが非ゼロ終了した時点で失敗とみなし、`build.success = false`、`failure.stage = "build"` を設定して手順 6 へ。build コマンドが無ければ実行せず `build.ran = false`。

4. テスト検証（test コマンドが解決され、かつビルド未失敗時のみ。`test.ran = true`）:
   - 解決したテストコマンドを実行し、出力を `{{tmp_dir}}/build.log` に append（`>>`）。非ゼロ終了を失敗とみなし、`test.success = false`、`failure.stage = "test"` を設定して手順 6 へ。
   - test コマンドが無ければ実行せず `test.ran = false`。ビルドが未実行（`build.ran = false`）でもテストは実行する。

5. 目視チェックのみ（`workflow_source == "none"`）:
   - フォーマッタ／ビルド／テストは実行しない（`build.ran` / `test.ran` は false）。git 変更ファイルを Read し、構文崩れ・未解決シンボル・明らかなフォーマット崩れなど目視で判別できる範囲を確認。
   - `format` は実行なしを示す値とし、`workflow_warning` に「フォーマット／ビルド手順が宣言されておらず自動検証をスキップした。`.claude/rules/build-format.md` の追加を推奨」を設定。
   - 目視で明白な破損を見つけた場合のみ `failure.stage = "visual"` を設定して手順 6 を行う。

6. 失敗時の専門家判定（`failure != null`）:
   - `failure.log_path`（`{{tmp_dir}}/build.log`。目視モードでは存在しない）とエラー発生ファイル（目視モードでは破損ファイル）を Read して原因分析し、`failure.error_summary` / `failure.error_files` / `failure.fix_guidance` を設定。
   - 専門家選定: `{{plugin_root}}/rules/agents-detection.md` の手順でエージェントを解決する。マッチ対象はエラー内容（言語・ビルドシステム・サブシステム・テストフレームワーク）、記録先は `failure.suggested_specialist`。

7. `{{tmp_dir}}/format-build-result.json` に Write。

`{{tmp_dir}}/format-build-result.json` 形式:

```
{
  "workflow_source": "build-format.md | CLAUDE.md | README.md | none",
  "workflow_warning": <string> | null,
  "format": {changed_files: [...], format_violations_fixed: <int>, format_violations_remaining: <int>},
  "build": {ran: <bool>, success: <bool>},
  "test": {ran: <bool>, success: <bool>},
  "failure": {stage: "build | test | visual", log_path, error_summary | null, error_files: ["src/foo.cpp:42", ...] | null, suggested_specialist | null, fix_guidance | null} | null
}
```

戻り値: `{path, success, format_violations_fixed, workflow_source, workflow_warning, summary_line（<=200 chars。例: "build-format.md / format ok / build ok / test ok" や "build-format.md / format ok / test ok (no build)" や "none / visual-only: no workflow declared"）, template_id}`。`success` は `failure == null`（未実行ステージは成功扱い）。`template_id` は本テンプレートの frontmatter から Read した値をそのまま含める。
