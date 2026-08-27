---
name: select-fix-targets
description: /creview:respond ステップ 1 でレビュードキュメントのメタデータから修正対象とその assignee を抽出する select-fix-targets サブエージェント向けプロンプト
template_id: 7c3e9a1d-5b48-4f62-9a8c-2d6f1b3e7a95
---

修正対象選別の担当として、レビュードキュメント `{{document_path}}` を Read し、修正対象選別ルールを適用し、`{{tmp_dir}}/targets.jsonl` を Write する。`{{plugin_root}}/rules/sub-agent.md` を Read し共通禁止事項を遵守する。

前提条件:

- `{{tmp_dir}}` はリーダーが事前に作成済み。ファイルシステムへの書き込みは targets.jsonl のみ。存在チェックや mkdir は実行しない。
- `{{document_path}}` / `{{tmp_dir}}` は相対パス。絶対パスに変換しない。

抽出対象: Critical / Major / Minor セクション（Info はスキップ）。各指摘について `<!-- METADATA(id) -->` … `<!-- /METADATA(id) -->` 内の値を読む。フィールドが繰り返す場合は最後の値を使う。

指摘が修正対象となるのは以下が**すべて**成立する場合:

- `Triage:` が `🔧 Will Fix`。assignee は `(assignee: {specialist})` からパースする。assignee がパースできない場合は `general-purpose` を使う。
- `Estimate:` が `▶️ Maintain` または `🚧 Alternative`。
- `Status:` 行が存在しない、または `Verification:` が `💬 Feedback`。メタデータは追記専用のため、再修正に差し戻された指摘も以前の `Status:` を持ち続ける。

スキップ（修正対象外）: `Triage: 🚫 Won't Fix`、`Estimate: 🔻 Downgrade`、`Status:` を持ち `Verification:` が無いか `✅ Verified` の指摘、`Triage:` または `Estimate:` がない指摘（先に `/creview:triage` を実行する。これらは理由を添えて `not_ready` に記録する）。

各修正対象について、`Estimate:` 行の ` — Plan: ` 以降を fix_plan として抽出する。先頭 `(1) ` および以降の ` (n) ` 番号マーカーで分割し、各エントリを要素とする文字列配列にする。` — Plan: ` セグメントが無い場合は fix_plan を空配列にする。

`Estimate:` 行が ` — Plan: ` の直前に ` — ADR: {ファイル名}` セグメントを持つ場合、そのファイル名を `adr` に設定する。無ければ `adr` は null。このセグメントは fix_plan には含めない。

`{{tmp_dir}}/targets.jsonl` 形式: `{items: [{id, assignee, estimate (Maintain|Alternative), adr (ファイル名または null), fix_plan (文字列配列、無ければ [])}], fix_count, not_ready: [{id, reason}]}`

戻り値: `{path, fix_count, by_assignee: [{assignee, ids: [id, ...]}], template_id}`（`by_assignee` は修正対象を assignee 単位でグルーピングする。指摘本文は含めない）。`template_id` は本テンプレートの frontmatter から Read した値をそのまま含める。
