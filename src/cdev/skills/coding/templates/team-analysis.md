---
name: team-analysis
description: cdev /coding ステップ 1 の team-analysis タスク（dev-helper）向けプロンプト。コーディングタスクのスコープを定め、対象プロジェクトの agents から reviewer を選定し（architect / coder / writer は general-purpose）、各 producer を reviewer とペアにする
template_id: d8760930-8d32-42c1-b033-d61f0cbd19c7
---

コーディングタスクのスコープを定め、専門家チームを編成し、各 producer を reviewer とペアにする。

タスク: `{{task}}`
申し送り: `{{handoff_path}}`
出力先: `{{output_path}}`

エージェントプール: `{{plugin_root}}/rules/agents-detection.md` § 列挙 に従って構築する。同ルールは 1 体を解決する手順だが、ここでは複数体を（以下の手順で）選定し、各選定の `name` を同ルール § 結果 の指定どおりに記録する。

割り当て規則:

- プールのエージェントは、各エージェントの `description` の専門性を担当の領域に照らして選ぶ。
- coders — 実装を担う。coder は常に `general-purpose` とする（`name` = `general-purpose`）。一部の専門家エージェントはツールコールをテキストとして出力して停止し実装を継続できないため。実装ボリュームに応じて 1 体以上に分け、各々に `slug`（kebab-case）と互いに素なファイル / ディレクトリの `scope` を付与し、2 人の coder が同一ファイルを編集しないようにする。AI 向けプロンプトファイルはそれ自体を 1 つのドメインとし、ほかのソースを含まないスコープの coder に割り当てる。各 coder の `reason` に、その scope が従うべきドメイン / 規約（例: backend なら Laravel）を記す。
- writers — ドキュメントファイル（`{{plugin_root}}/rules/teammate.md` § ドキュメントファイル の定義による）を書く。writer は常に `general-purpose` とする（`name` = `general-purpose`）。ドキュメントファイルはそれ自体を 1 つのドメインとし、writer にだけ割り当てる。writer のスコープはドキュメントファイルだけを持つ。writer は coder と同じくボリュームに応じて分け、各々に `slug`（kebab-case）と、どの coder・writer のスコープとも互いに素な `scope` を付与し、各 writer の `reason` にそのドキュメントのドメインを記す。`has_docs` が false なら `writers` は空とする。
- reviewers — 設計、コード、ドキュメントをレビューする。各 producer のドメインを個別にカバーできるよう選定する（backend / frontend / E2E / security / AI 向けプロンプト / ドキュメント等が混在するなら各領域に対応できる reviewer を確保する）。各々に `slug` を付与する。
- あるドメイン / 役割に合致する専門家がプールにいない場合、その担当には `general-purpose` を用いる。
- 各 architect、各 coder、各 writer を、その producer のドメインに一致する 1 名の reviewer とペアにする: その `reviewer` を reviewer の `slug` に設定する。1 名の reviewer を複数の producer に共有してよいのは同一ドメインの producer に限る。ドメインが一致する reviewer がいない producer には `general-purpose` の reviewer を充てる（専門外の reviewer に兼任させない）。

手順:

1. タスクを理解する: 対象言語、関わるサブシステム / ディレクトリ、ビルド / テスト範囲を判定する。プロジェクトにテストスイート（解決可能なテストコマンド、テストフレームワーク、またはテストディレクトリ）があるかを判定し `has_test_suite` を設定する。タスクが AI 向けプロンプトファイル（`{{plugin_root}}/rules/prompt.md` の定義による）を作成または編集する場合、そうしうる場合、および判断に迷う場合は `has_prompts` を true にする。ドキュメントファイル（`{{plugin_root}}/rules/teammate.md` § ドキュメントファイル の定義による）について同じ基準で `has_docs` を設定する。既存コードベースに対し Glob / Grep / Read を用いてこれを裏付ける。スコープ判定に足る範囲のみ読み、実装は一切しない。`{{handoff_path}}` が `(none)` でない場合はそれを Read し、スコープの判定にも使う: 申し送りが触れるサブシステム、その方針が求める変更、申し送りが挙げるターニングポイントへ設計が復元しうるファイル。
2. プールからチームを選定する:
   - architects — 設計を担う。architect は常に `general-purpose` とする（`name` = `general-purpose`）。単一サブシステムのタスクなら 1 体で足りる。明確に分離可能な複数サブシステムにまたがる場合のみ複数を用いる。各々に `slug`（kebab-case）と `scope` を付与し、`reason` にその scope が関わるドメインを記す。architect の scope には、コードとそれを説明するドキュメントを一緒に持たせてよい。
   - coders、writers、reviewers — 割り当て規則に従って選定し、各 architect、各 coder、各 writer をペアにする。
3. `task_summary` を、architects / coders / writers が元のチャットなしで動けるタスクの自己完結的な再記述（{{doc_lang}} で）として記述する。タスクだけから書き、申し送りの内容は入れない: タスクの要約に入れた内容は、判断の優先順位でタスクの位置、つまり申し送りより上に置かれる。
4. 結果を `{{output_path}}` へ Write する。`scope` / `reason` / `rationale` / `task_summary` は {{doc_lang}} で記述し、`name` / `slug` / 識別子はそのまま。

`{{output_path}}` の形式:

```
{"task_summary": <string>, "target_languages": [<string>, ...], "has_test_suite": <bool>, "has_prompts": <bool>, "has_docs": <bool>, "architects": [{"name": <string>, "slug": <string>, "scope": <string>, "reviewer": <string>, "reason": <string>}], "coders": [{"name": <string>, "slug": <string>, "scope": <string>, "reviewer": <string>, "reason": <string>}], "writers": [{"name": <string>, "slug": <string>, "scope": <string>, "reviewer": <string>, "reason": <string>}], "reviewers": [{"name": <string>, "slug": <string>, "reason": <string>}], "rationale": <string>}
```

リーダー（`SendMessage` の `to: "main"`）へ完了を 1 行で報告する。`{{output_path}}` とチーム規模（architect / coder / writer / reviewer の人数）を記す。
