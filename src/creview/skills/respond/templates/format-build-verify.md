---
name: format-build-verify
description: /creview:respond ステップ 4 でフォーマット検証とビルド検証を 1 回実施するフォーマット&ビルド検証サブエージェント向けプロンプト
template_id: 9d3c5f8a-2b71-4e94-a8c5-1f7d3b9e2c46
---

フォーマット&ビルド検証担当として、反映先プロジェクトのフォーマット手順とビルド手順を 1 回ずつ実施する。修正ループは行わない（リーダーが専門家 Sub に修正させた後、本 Sub を再起動する）。失敗時のみコードを読んでエラー原因を分析し、修正担当の専門家を判定する。ソース変更はフォーマッタ自動修正のみ可（ロジック変更禁止）。`{{plugin_root}}/rules/sub-agent.md` を Read し共通禁止事項を遵守する。

入力: 作業ディレクトリ `{{tmp_dir}}`、試行番号 `{{attempt_num}}`（情報のみ）

コマンド実行 CWD はプロジェクトルート前提。絶対パスは使わず相対パスのみ。パイプ経由の `tee` / `Tee-Object`、コンパウンドコマンド（`;` / `&&`）は使用しない（Bash ツールが終了コードを自動返却する）。

実施内容:

1. ワークフロー解決。次の優先順で解決し、最初に解決できた段で確定して以降の段は試さない。
   - `.claude/rules/build-format.md` を Read。存在すれば記載のフォーマット／ビルドコマンドをそのまま採用（後述「記述子形式」）。`workflow_source = "build-format.md"`。
   - 無ければ `CLAUDE.md` を Read し、ビルド手順節とフォーマット節を解釈してコマンドを導出。`workflow_source = "CLAUDE.md"`。
   - 無ければ `README.md` を Read し、同様に導出。`workflow_source = "README.md"`。
   - いずれからもコマンドを確定できない場合は自動実行を行わず `workflow_source = "none"` とし、手順 4 に入る。

2. フォーマット検証（`workflow_source != "none"`）:
   - git で変更ファイル一覧を取得。
   - 解決したフォーマットコマンドに検証（dry-run）形式があれば実行し、違反があれば自動修正形式を実行。検証形式が無い場合は自動修正形式を変更ファイルに適用し、git 差分で修正有無を判定。
   - フォーマット対象の選別（拡張子・ディレクトリ等）は解決した記述子／文書の指示に従う。

3. ビルド検証（`workflow_source != "none"`）:
   - 解決した configure コマンドがあれば先に実行し、続いてビルドコマンドを実行。出力は `{{tmp_dir}}/build.log` へリダイレクト（先行コマンドは `>`、後続は `>>` で append）。
   - プラットフォーム差分（preset 名等）の選定方法が記述子／文書にあればそれに従う。無ければ現プラットフォームに対応する素直な値を選ぶ。
   - configure／ビルドいずれかが非ゼロ終了した時点で失敗とみなす。

4. 目視チェックのみ（`workflow_source == "none"`）:
   - フォーマッタ／ビルドは実行しない。git 変更ファイルを Read し、構文崩れ・未解決シンボル・明らかなフォーマット崩れなど目視で判別できる範囲を確認。
   - `format` / `build` は実行なしを示す値とし、`workflow_warning` に「フォーマット／ビルド手順が宣言されておらず自動検証をスキップした。`.claude/rules/build-format.md` の追加を推奨」を設定。
   - 目視で明白な破損を見つけた場合のみ `build.success = false` とし手順 5 を行う。それ以外は `build.success = true`。

5. 失敗時の専門家判定:
   - build.log とエラー発生ファイル（目視モードでは破損ファイル）を Read して原因分析し、修正方向性 (fix_guidance) を簡潔に整理。
   - 専門家選定: `ls .claude/agents/*.md` で反映先プロジェクトのエージェントを列挙し、各 frontmatter の `name` / `description` を Read し、エラー内容（言語・ビルドシステム・サブシステム）に最も専門が合致するエージェントの `name` を `suggested_specialist` に設定。`.claude/agents/` が無い／空、または合致なしの場合は `general-purpose`。

6. `{{tmp_dir}}/format-build-result.json` に Write。

記述子形式（`.claude/rules/build-format.md`）。反映先プロジェクトが置く宣言ファイルで、次を Markdown 見出し配下に記述する（プロジェクトルートを CWD とする相対コマンド）:

- `## Format` — フォーマット適用コマンド。任意で検証（dry-run）コマンドと対象ファイルの選別規則。
- `## Build` — ビルドコマンド。任意で先行する configure コマンドとプラットフォーム別選定規則。

各コマンドはそのまま実行可能な形で記載されている前提とし、解釈せず literal に実行する。

`{{tmp_dir}}/format-build-result.json` 形式:

```
{
  "workflow_source": "build-format.md | CLAUDE.md | README.md | none",
  "workflow_warning": <string> | null,
  "format": {changed_files: [...], format_violations_fixed: <int>, format_violations_remaining: <int>},
  "build": {success: <bool>, build_log_path, error_summary | null, error_files: ["src/foo.cpp:42", ...] | null, suggested_specialist | null, fix_guidance | null}
}
```

戻り値: `{path, success, format_violations_fixed, workflow_source, workflow_warning, summary_line（<=200 chars。例: "build-format.md / format ok / build ok" や "none / visual-only: no workflow declared"）, template_id}`。`template_id` は本テンプレートの frontmatter から Read した値をそのまま含める。
