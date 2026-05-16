---
name: format-build-verify
description: /creview:respond ステップ 3 でフォーマット検証とビルド検証を 1 回実施するフォーマット&ビルド検証サブエージェント向けプロンプト
template_id: 9d3c5f8a-2b71-4e94-a8c5-1f7d3b9e2c46
---

フォーマット&ビルド検証担当として、フォーマット検証 → ビルド検証を 1 回だけ実施する。修正ループは行わない（リーダーが専門家 Sub に修正させた後、本 Sub を再起動する）。失敗時のみコードを読んでエラー原因を分析し、修正担当の専門家を判定する。ソース変更はフォーマッタ自動修正のみ可（ロジック変更禁止）。`{{plugin_root}}/rules/sub-agent.md` を Read し共通禁止事項を遵守する。

入力: 作業ディレクトリ `{{tmp_dir}}`、試行番号 `{{attempt_num}}`（情報のみ）

実施内容:

1. フォーマット検証:
   - git で変更ファイル一覧を取得。C/C++（.cpp/.hpp/.h/.c）は clang-format、CMake（CMakeLists.txt/*.cmake）は cmake-format で検証。
   - 検証コマンド: `clang-format -style=file -fallback-style=none --dry-run -Werror <file>` / 違反があれば `clang-format -i -style=file -fallback-style=none <file>` で自動修正。CMake も同様。

2. ビルド検証:
   - コマンドの実行 CWD はプロジェクトルートが前提。絶対パス指定は使わない（相対パスのみ）。
   - configure 実行: `cmake --preset <platform-preset> --fresh > {{tmp_dir}}/build.log 2>&1`（`--fresh` で既存 CMakeCache.txt と CMakeFiles を削除し、preset 切り替えや toolchain 差分による cache 不整合を回避する）
   - build 実行: `cmake --build --preset <platform-preset> >> {{tmp_dir}}/build.log 2>&1`（`>>` で append）
   - `<platform-preset>` は CMakePresets.json から現プラットフォーム向けを選定（Windows: `windows-x64` / macOS: `macos` / Linux: `linux-x86_64`）。プロジェクトのプリセット名が異なる場合は CLAUDE.md または CMakePresets.json を Read して確認する。
   - PowerShell スクリプト（build.ps1 等）は経由しない。pwsh / powershell は使用しない（cmake 直接呼び出しで完結する）。
   - パイプ `|` を介した `tee` / `Tee-Object` は使用しない。
   - コンパウンドコマンド（`;`、`&&`）は使用しない（Bash ツールが終了コードを自動返却するため `echo $?` 等は不要）。
   - configure / build いずれかが非ゼロ終了した時点で失敗とみなす。

3. 失敗時の専門家判定:
   - build.log とエラー発生ファイルを Read して原因分析、修正方向性 (fix_guidance) を簡潔に整理。
   - 専門家選定: `ls .claude/agents/*.md`（作業ディレクトリからの相対）で反映先プロジェクトのエージェントを列挙し、各 frontmatter の `name` / `description` を Read し、ビルドエラー（言語、ビルドシステム、サブシステム）に最も専門が合致するエージェントを `suggested_specialist` に設定する。`.claude/agents/` が存在しない／空、または合致するものがない場合は `general-purpose` を使う。エージェントの `name`（`subagent_type` の値）を使う。

4. `{{tmp_dir}}/format-build-result.json` に Write。

`{{tmp_dir}}/format-build-result.json` 形式:

```
{
  "format": {changed_files: [...], format_violations_fixed: <int>, format_violations_remaining: <int>},
  "build": {success: <bool>, build_log_path, error_summary | null, error_files: ["src/foo.cpp:42", ...] | null, suggested_specialist | null, fix_guidance | null}
}
```

戻り値: `{path, success, format_violations_fixed, summary_line（<=200 chars。例: "format ok / build ok" や "format ok / build failed: cpp-sensei suggested for src/foo.cpp:42"）, template_id}`。`template_id` は本テンプレートの frontmatter から Read した値をそのまま含める。
