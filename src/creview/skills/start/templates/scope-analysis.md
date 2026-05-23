---
name: scope-analysis
description: /creview:start ステップ 1 で差分を解析し対象プロジェクトのエージェントからレビュアー候補を選定するスコープ解析サブエージェント向けプロンプト
template_id: b3e2f1a7-9c84-4d56-8e3b-7f1a4c9d2e85
---

レビュー範囲解析担当として `{{tmp_dir}}/diff.txt` を Read し、行数算出とレビュアー候補を選定する。`{{plugin_root}}/rules/sub-agent.md` を Read し共通禁止事項を遵守する。

ユーザー明示要求レビュアー: `{{user_requested}}`（空配列あり）

レビュアープール: 以下の優先順位で `*.md` を列挙し、各ファイルの frontmatter の `name` / `description` を Read して専門性を把握する。`name` 値は別の Agent 呼び出しの `subagent_type` に渡す値である。同一 `name` が複数スコープに存在する場合は上位スコープのものを採用する。存在しないスコープはスキップする。

1. プロジェクトスコープ: `.claude/agents/**/*.md`（作業ディレクトリ基準）
2. ユーザースコープ: `~/.claude/agents/**/*.md`
3. プラグイン同梱: `{{plugin_root}}/agents/**/*.md`

実施内容:

1. 差分から変更ファイルの種別 / パス / 内容領域（言語、サブシステム、ビルド / CI、A/V、コメント & FIXME / TODO 等）と拡張子別サマリを判定する。
2. 列挙した各エージェントについて、その `description` から専門性が差分に関連するか判定する。関連するエージェントはすべて、合致した拡張子 / パス / 内容領域を示す短い `reason` を付して `recommended_reviewers` に追加する。
3. いずれのスコープにも関連するエージェントがない場合、`{name: "general-purpose", reason: "no matching specialist agent"}` を 1 件追加する。
4. 未追加の `user_requested` レビュアーを補完する（reason: `"user explicitly requested"`）。
5. `line_count` = 差分中の +/- 行合計。

戻り値: `{line_count, recommended_reviewers: [{name, reason}], extension_summary（例: ".cpp(12), .hpp(5)"）, rationale（選定根拠 1〜2 文）, template_id}`。`template_id` は本テンプレートの frontmatter から Read した値をそのまま含める。
