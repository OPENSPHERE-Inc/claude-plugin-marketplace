---
name: team-analysis
description: cdev /coding ステップ 1 の team-analysis タスク（dev-helper）向けプロンプト。コーディングタスクのスコープを定め、対象プロジェクトの agents から reviewer を選定し（architect / coder は general-purpose）、各 producer を reviewer とペアにする
template_id: d8760930-8d32-42c1-b033-d61f0cbd19c7
---

コーディングタスクのスコープを定め、専門家チームを編成し、各 producer を reviewer とペアにする。

タスク: `{{task}}`
出力先: `{{output_path}}`

エージェントプール: `{{plugin_root}}/rules/agents-detection.md` § 列挙 に従って構築する。同ルールは 1 体を解決する手順だが、ここでは複数体を（以下の手順で）選定し、各選定の `name` を同ルール § 結果 の指定どおりに記録する。

手順:

1. タスクを理解する: 対象言語、関わるサブシステム / ディレクトリ、ビルド / テスト範囲を判定する。プロジェクトにテストスイート（解決可能なテストコマンド、テストフレームワーク、またはテストディレクトリ）があるかを判定し `has_test_suite` を設定する。既存コードベースに対し Glob / Grep / Read を用いてこれを裏付ける。スコープ判定に足る範囲のみ読み、実装は一切しない。
2. プールからチームを選定し、各エージェントの `description` の専門性をタスクに合致させる:
   - architects — 設計を担う。architect は常に `general-purpose` とする（`name` = `general-purpose`）。単一サブシステムのタスクなら 1 体で足りる。明確に分離可能な複数サブシステムにまたがる場合のみ複数を用いる。各々に `slug`（kebab-case）と `scope` を付与し、`reason` にその scope が関わるドメインを記す。
   - coders — 実装を担う。coder は常に `general-purpose` とする（`name` = `general-purpose`）。一部の専門家エージェントはツールコールをテキストとして出力して停止し実装を継続できないため。実装ボリュームに応じて 1 体以上に分け、各々に `slug`（kebab-case）と互いに素なファイル / ディレクトリの `scope` を付与し、2 人の coder が同一ファイルを編集しないようにする。各 coder の `reason` に、その scope が従うべきドメイン / 規約（例: backend なら Laravel）を記す。
   - reviewers — 設計とコードをレビューする。各 producer のドメインを個別にカバーできるよう選定する（backend / frontend / E2E / security 等が混在するなら各領域に対応できる reviewer を確保する）。各々に `slug` を付与する。
3. あるドメイン / 役割に合致する専門家がプールにいない場合、その担当には `general-purpose` を用いる。
4. 各 architect と各 coder を、その producer のドメインに一致する 1 名の reviewer とペアにする: その `reviewer` を reviewer の `slug` に設定する。1 名の reviewer を複数の producer に共有してよいのは同一ドメインの producer に限る。ドメインが一致する reviewer がいない producer には `general-purpose` の reviewer を充てる（専門外の reviewer に兼任させない）。
5. `task_summary` を、architects / coders が元のチャットなしで動けるタスクの自己完結的な再記述（{{doc_lang}} で）として記述する。
6. 結果を `{{output_path}}` へ Write する。`scope` / `reason` / `rationale` / `task_summary` は {{doc_lang}} で記述し、`name` / `slug` / 識別子はそのまま。

`{{output_path}}` の形式:

```
{"task_summary": <string>, "target_languages": [<string>, ...], "has_test_suite": <bool>, "architects": [{"name": <string>, "slug": <string>, "scope": <string>, "reviewer": <string>, "reason": <string>}], "coders": [{"name": <string>, "slug": <string>, "scope": <string>, "reviewer": <string>, "reason": <string>}], "reviewers": [{"name": <string>, "slug": <string>, "reason": <string>}], "rationale": <string>}
```

リーダー（`SendMessage` の `to: "main"`）へ完了を 1 行で報告する。`{{output_path}}` とチーム規模（architect / coder / reviewer の人数）を記す。
