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
- `{{tmp_dir}}/challenge.json` — `{items: [{id, stance, argument}]}`。
- `{{document_path}}` — draft と反証だけではガイドラインを当てはめられない場合に、id をキーに METADATA マーカー前後から指摘本文を引く。
- `{{previous_round_doc_paths}}` — 非空かつ `(none)` でない場合は各ファイルを Read し、ガイドライン 7 の判定に使う。

Won't Fix ガイドライン（いずれか該当時）:

1. ブランチ差分のスコープ外。
2. 既存コードのバグ（ブランチ非由来）。
3. 仮説誤り・技術的誤り。
4. プロジェクト目的・用途・想定利用者から許容と推察できる。
5. 好みベースのリファクタリング（正確性・安全性・性能・保守性の根拠なし）。
6. 再現性不明で e2e 検証が必要。
7. 過去ラウンドで同一箇所・同一内容の指摘が処理済みの場合（`{{previous_round_doc_paths}}` 提供時のみ判定可能）。同一性判定は file:line と指摘要旨の一致で行う。該当パターン:
   - 過去ラウンドで `status: 🟢 Fixed` 済み（通常フローでは起こらないエッジケース。再発見されているため理由欄に「前ラウンドで Fixed 済み」と明記）。
   - 過去ラウンドで `triage: 🚫 Won't Fix`（理由欄に「前ラウンド Won't Fix と同一指摘」と明記し、過去判定の理由も簡潔に転記）。
   - 過去ラウンドで `estimate: 🔻 Downgrade`（理由欄に「前ラウンド Downgrade と同一指摘」と明記し、過去判定の理由も簡潔に転記）。

高重要度例外: Won't Fix でも Critical / Major は理由欄に「別 PR 推奨」を明記（例: "Won't Fix — 既存コードのバグ。別 PR での修正を推奨"）。

ガイドライン 7 は `stage` が `pending_triage` の指摘にのみ適用する。`stage` が `feedback` の指摘は、過去ラウンドで処理されたうえで検証が 💬 Feedback を返した対象であり、処理済みであること自体が前提のため適用しない。

裁定:

- 反論に具体性がない場合、および反論と draft の根拠を比べても判断がつかない場合は、draft の `verdict` と `reason` を維持する。`stance: no_valid_objection` も draft 維持。
- `challenge.json` に欠けている id は `no_valid_objection` 相当として扱い、draft を維持する。
- `flipped` は最終 `verdict` が draft の `verdict` と異なる場合にのみ true とする。
- 反転する場合は `reason` に根拠を 1 行含める（`file:line` またはガイドライン番号を伴う具体的な理由）。
- 最終 verdict が `Won't Fix` かつ severity が Critical / Major の場合は、draft からの引き継ぎ・反転のいずれであっても `reason` に「別 PR 推奨」に相当する文言を含める。
- `flipped` が true の項目は、`reason` の末尾に反転の経緯を一言だけ付ける。`reason` は単一行を維持し、改行や文の追記はしない。

`reason` の散文は、`{{document_path}}` の既存 Finding 説明と同じ言語で記述する。

`{{tmp_dir}}/adjudication.json` 形式: `{items: [{id, verdict（Will Fix | Won't Fix）, flipped, reason}], flipped_count}`（items は `triage-draft.json` の全 id を網羅する。flipped_count は `flipped` が true の件数）

戻り値: `{path, flipped_count, will_fix_count, wontfix_count, template_id}`（reason の本文は戻り値に含めない）。`template_id` は本テンプレートの frontmatter から Read した値をそのまま含める。
