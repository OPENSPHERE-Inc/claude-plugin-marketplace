---
name: team-analysis
description: cdev /coding ステップ 1 の team-analysis タスク（dev-helper）向けプロンプト。コーディングタスクのスコープを定め、対象プロジェクトの agents から architect / coder / reviewer を選定し、各 producer を reviewer とペアにする
template_id: d8760930-8d32-42c1-b033-d61f0cbd19c7
---

コーディングタスクのスコープを定め、専門家チームを編成し、各 producer を reviewer とペアにする。

タスク: `{{task}}`

エージェントプール: 以下のスコープから優先順位順に `*.md` を列挙し、各ファイルの frontmatter の `name` / `description` を Read して各エージェントの専門性を把握する。`name` 値は、teammate 起動時にリーダーが `subagent_type` に渡す値である。同一 `name` が複数スコープに存在する場合は上位スコープのものを採用する。存在しないスコープはスキップする。

1. プロジェクトスコープ: `.claude/agents/**/*.md`（作業ディレクトリ基準）
2. ユーザースコープ: `~/.claude/agents/**/*.md`
3. プラグイン同梱: `{{plugin_root}}/agents/**/*.md`

手順:

1. タスクを理解する: 対象言語、関わるサブシステム / ディレクトリ、ビルド / テスト範囲を判定する。プロジェクトにテストスイート（解決可能なテストコマンド、テストフレームワーク、またはテストディレクトリ）があるかを判定し `has_test_suite` を設定する。既存コードベースに対し Glob / Grep / Read を用いてこれを裏付ける。スコープ判定に足る範囲のみ読み、実装は一切しない。
2. プールからチームを選定し、各エージェントの `description` の専門性をタスクに合致させる:
   - architects — 設計を担う 1 体以上のエージェント。単一サブシステムのタスクなら architect 1 体で足りる。明確に分離可能な複数サブシステムにまたがる場合のみ複数を用いる。各々に `slug`（kebab-case）と `scope` を付与する。
   - coders — 実装を担う 1 体以上のエージェント。各々に `slug`（kebab-case）と、互いに素なファイル / ディレクトリの `scope` を付与し、2 人の coder が同一ファイルを編集しないようにする。
   - reviewers — 設計とコードの双方をレビューする 1 体以上のエージェント。各々に `slug` を付与する。
3. いずれのスコープにも合致する専門家がいない役割には、その役割に `general-purpose` を 1 件用いる。
4. 各 architect と各 coder を 1 名の reviewer とペアにする: その `reviewer` を reviewer の `slug` に設定する。reviewer が producer より少ない場合は、1 名の reviewer を複数の producer とペアにする。
5. `task_summary` を、architects / coders が元のチャットなしで動けるタスクの自己完結的な再記述（{{doc_lang}} で）として記述する。

リーダー（`SendMessage` の `to: "main"`）へ報告する: `{task_summary, target_languages: [..], has_test_suite: <bool>, architects: [{name, slug, scope, reviewer, reason}], coders: [{name, slug, scope, reviewer, reason}], reviewers: [{name, slug, reason}], rationale}`。`scope` / `reason` / `rationale` / `task_summary` は {{doc_lang}} で記述し、`name` / `slug` / 識別子はそのまま。この報告がタスク完了の通知を兼ねる。
