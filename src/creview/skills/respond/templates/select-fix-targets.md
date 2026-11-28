---
name: select-fix-targets
description: /creview:respond ステップ 1 でレビュードキュメントのメタデータから修正対象とその assignee・段を抽出する select-fix-targets サブエージェント向けプロンプト
template_id: 7c3e9a1d-5b48-4f62-9a8c-2d6f1b3e7a95
---

修正対象選別の担当として、レビュードキュメント `{{document_path}}` を Read し、修正対象選別ルールを適用し、各修正対象の段を定め、`{{tmp_dir}}/targets.jsonl` を Write する。`{{plugin_root}}/rules/sub-agent.md` を Read し共通禁止事項を遵守する。

前提条件:

- `{{tmp_dir}}` はリーダーが事前に作成済み。ファイルシステムへの書き込みは targets.jsonl のみ。存在チェックや mkdir は実行しない。
- `{{document_path}}` / `{{tmp_dir}}` は渡された形のまま使い、変換しない。

抽出対象: Critical / Major / Minor セクション（Info はスキップ）。各指摘について `<!-- METADATA(id) -->` … `<!-- /METADATA(id) -->` 内の値を読む。フィールドが繰り返す場合は最後の値を使う。

指摘が修正対象となるのは以下が**すべて**成立する場合:

- `Triage:` が `🔧 Will Fix`。assignee は `(assignee: {specialist})` からパースする。assignee がパースできない場合は `general-purpose` を使う。
- `Estimate:` が `▶️ Maintain` または `🚧 Alternative`。
- `Status:` 行が存在しない、または `Verification:` が `💬 Feedback`。メタデータは追記専用のため、再修正に差し戻された指摘も以前の `Status:` を持ち続ける。

スキップ（修正対象外）: `Triage: 🚫 Won't Fix`、`Estimate: 🔻 Downgrade`、`Status:` を持ち `Verification:` が無いか `✅ Verified` の指摘、`Triage:` がなく `Verification:` が `✅ Verified` の指摘（コードと照合済みで修正の必要がない）、それ以外で `Triage:` がない指摘、または `Triage:` が `🔧 Will Fix` で `Estimate:` がない指摘（先に `/creview:triage` を実行する。これらは理由を添えて `not_ready` に記録する）。

各修正対象について、`Estimate:` 行の ` — Plan: ` 以降を fix_plan として抽出する。先頭 `(1) ` および以降の ` (n) ` 番号マーカーで分割し、各エントリを要素とする文字列配列にする。` — Plan: ` セグメントが無い場合は fix_plan を空配列にする。

`Estimate:` 行が ` — Plan: ` の直前に ` — ADR: {ファイル名}` セグメントを持つ場合、そのファイル名を `adr` に設定する。無ければ `adr` は null。このセグメントは fix_plan には含めない。

各修正対象の `stages` は、その修正要件（sub-agent.md § 修正要件）が述べることから定める: ドキュメントファイル（同ファイルの § ドキュメントファイル）の編集を求めるなら `docs`、それ以外のファイルの編集を求めるなら `code` とする。ADR ファイルはどちらにも数えない。判定は修正要件が述べることと挙げるパスだけから行い、ソースを読まず、リポジトリを探さず、プロジェクトの CLAUDE.md も読まない。それで種類が分からないファイルの編集（名前からドキュメントかプロンプトテンプレートか分からない Markdown ファイルなど）は `code` と `docs` の両方に数える。修正要件がどちらも示さない場合は `["code"]` とする。

各修正対象の `text_only` は、同じ修正要件から、`stages` と同じ読む範囲の制約で定める: 修正要件が、求める編集がすべて人向けテキスト（sub-agent.md § 人向けテキスト）に当たると示す場合に限り true、それ以外は false とする。部分の種類は修正要件が述べることから判断し、何がその部分を読むかは、ソースを読む修正に任せる: 修正要件がコメントや docstring の本文、doc ブロックの説明文の編集と述べる部分は、プロジェクトのツールがその部分を読んで作用すると示していない限り人向けコメントであり、例、型、指示などコメントのそれ以外の部分は、何もそれに作用しないと示していない限り人向けかどうか判断できない部分であり、種類を示していない部分も同じである。`🚧 Alternative` の修正は、修正要件がほかの変更を求めない限り、FIXME コメントの挿入だけである。

`{{tmp_dir}}/targets.jsonl` 形式: `{items: [{id, assignee, stages (["code"]、["docs"]、または ["code", "docs"]), text_only (true または false), estimate (Maintain|Alternative), adr (ファイル名または null), fix_plan (文字列配列、無ければ [])}], fix_count, not_ready: [{id, reason}]}`

戻り値: `{path, fix_count, by_assignee: [{assignee, ids: [id, ...]}], code_stage: [{assignee, ids: [id, ...]}], docs_stage: [{assignee, ids: [id, ...]}], not_ready: [{id, reason}], template_id}`（`by_assignee` はすべての修正対象を assignee 単位でグルーピングする。`code_stage` と `docs_stage` は、`stages` がそれぞれ `code`、`docs` を含む修正対象を assignee 単位でグルーピングする。`not_ready` は targets.jsonl と同じ内容で、各 `reason` は短い定型文とする。指摘本文は含めない）。`template_id` は本テンプレートの frontmatter から Read した値をそのまま含める。
