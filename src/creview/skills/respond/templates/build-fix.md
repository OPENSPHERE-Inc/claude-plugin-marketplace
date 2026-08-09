---
name: build-fix
description: /creview:respond ステップ 4 でビルド／テストエラーを修正するビルド／テスト修正専門家サブエージェント向けプロンプト
template_id: 6e2a9f5c-1d83-4b74-9c2e-5a8d3f1b7e29
---

ビルド／テストエラーを修正する。`{{plugin_root}}/rules/sub-agent.md` を Read し共通禁止事項を遵守する。

入力（`{{tmp_dir}}/format-build-result.jsonl` の `failure` セクションを Read）:

- stage（`build` / `test` / `visual`）/ error_summary / error_files / fix_guidance / log_path
- ビルド／テストログ全文は `log_path`（通常 `{{tmp_dir}}/build.log`）を Read（必要時のみ）。`stage` が `visual`（目視チェックのみ）の場合ログは存在せず、error_files と fix_guidance を一次情報とする。

手順:

1. error_files に挙げられたソース＋周辺コードを Read してエラー原因を特定。
2. 修正実装（CLAUDE.md のコーディング規約準拠）。
3. セルフレビュー: 変更箇所再読、エラー解消と新規問題の混入がないことを確認。

戻り値: `{description, template_id}`。`template_id` は本テンプレートの frontmatter から Read した値をそのまま含める。
