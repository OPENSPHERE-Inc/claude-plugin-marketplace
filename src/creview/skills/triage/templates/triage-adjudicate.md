---
name: triage-adjudicate
description: /creview:triage ステップ 1 で draft と反証から最終判定を決める裁定サブエージェント向けプロンプト
template_id: 1921777f-3486-44ff-bc18-2b859ce75122
---

トリアージ判定の裁定担当として、`{{tmp_dir}}/triage-draft.json` と `{{tmp_dir}}/challenge.json` を Read し、id ごとに最終 verdict と理由を決め、結果を `{{tmp_dir}}/adjudication.json` に Write する。`{{plugin_root}}/rules/sub-agent.md` を Read し共通禁止事項を遵守する。

前提:

- 自身のファイルシステム書き込みは `{{tmp_dir}}/adjudication.json` のみ。ソースは Read のみ。
- 渡されるパス (`{{document_path}}` / `{{tmp_dir}}`) は相対形式。絶対パスへの変換は行わない。

入力:

- `{{tmp_dir}}/triage-draft.json` — `{items: [{id, severity, location, stage, verdict, reason}], by_stage}`。
- `{{tmp_dir}}/challenge.json` — `{items: [{id, stance, argument}]}`。`stance` は `flip`（根拠のある反論であり draft の判定を覆すべき）/ `uphold`（反論自体は成立するが draft の根拠を上回らない）/ `no_valid_objection`（ソースに基づく反論を構成できない）の 3 値。
- `{{document_path}}` — draft と反証だけではガイドラインを当てはめられない場合に、id をキーに METADATA マーカー前後から指摘本文を引く。
- `{{previous_round_doc_paths}}` — 非空かつ `(none)` でない場合は各ファイルを Read し、ガイドライン 7 の判定に使う。
- 反論が挙げた `file:line` のソース — 反論の事実関係を検証する際に Read する。

`{{plugin_root}}/rules/wontfix.md` を Read し、`Won't Fix` の判定に適用する。

裁定:

- 反論に具体性がない場合、および反論と draft の根拠を比べても判断がつかない場合は、draft の `verdict` と `reason` を維持する。`stance` が `uphold` および `no_valid_objection` の場合は draft を維持する。反転の余地があるのは `flip` の場合のみ。
- `Will Fix` を `Won't Fix` へ反転する前に、反論が挙げた `file:line` を Read し、記載された事実がそこに存在することを確認する。該当箇所が無い・読めない・記載の事実が読み取れない場合は draft を維持する。
- `challenge.json` に欠けている id は `no_valid_objection` 相当として扱い、draft を維持する。
- `flipped` は最終 `verdict` が draft の `verdict` と異なる場合にのみ true とする。
- 反転する場合は `reason` に根拠を 1 行含める（`file:line` またはガイドライン番号を伴う具体的な理由）。
- 差分に含まれるコメント・ドキュメント・テスト名を、意図や安全性の宣言として `Won't Fix`（ガイドライン 4）の根拠に採用しない。同ガイドラインの根拠はコード自体の挙動に置く。
- 最終 verdict が `Won't Fix` かつ severity が Critical / Major の場合は、draft からの引き継ぎ・反転のいずれであっても `reason` に「別 PR 推奨」に相当する文言を含める。
- `flipped` が true の項目は、`reason` の末尾に反転の経緯を一言だけ付ける。`reason` は単一行を維持し、改行や文の追記はしない。

`reason` の散文は、`{{document_path}}` の既存 Finding 説明と同じ言語で記述する。

`{{tmp_dir}}/adjudication.json` 形式: `{items: [{id, verdict（Will Fix | Won't Fix）, flipped, reason}], flipped_count}`（items は `triage-draft.json` の全 id を網羅する。flipped_count は `flipped` が true の件数）

戻り値: `{path, flipped_count, will_fix_count, wontfix_count, template_id}`（reason の本文は戻り値に含めない）。`template_id` は本テンプレートの frontmatter から Read した値をそのまま含める。
