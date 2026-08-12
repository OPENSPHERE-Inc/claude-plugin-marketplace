---
name: triage-challenge
description: /creview:triage ステップ 1 で一次判定の全件に反論を試みる反証サブエージェント向けプロンプト
template_id: b8701509-403b-488b-8b13-c867f9c6700b
---

一次トリアージ判定の反証担当の 1 インスタンスとして、`{{tmp_dir}}/triage-draft.jsonl` を Read し、`items` のうち id が `{{ids}}` に含まれる全件に反論を試み、結果を `{{tmp_dir}}/challenge-{{batch_index}}-{{challenge_index}}.jsonl` に Write する。`{{plugin_root}}/rules/sub-agent.md` を Read し共通禁止事項を遵守する。本文で引く Won't Fix ガイドライン番号は `{{plugin_root}}/rules/wontfix.md` を Read して参照する。

前提:

- 自身のファイルシステム書き込みは `{{tmp_dir}}/challenge-{{batch_index}}-{{challenge_index}}.jsonl` のみ。ソースは Read のみ。
- 他の `challenge-*.jsonl` は Read しない。並列インスタンスの stance は独立票として集計される。
- 渡されるパス (`{{document_path}}` / `{{tmp_dir}}`) は相対形式。絶対パスへの変換は行わない。

入力:

- `{{ids}}` — 自身の担当となる draft の id。このリスト外の draft 項目は判断しない。
- `{{tmp_dir}}/triage-draft.jsonl` — `{items: [{id, severity, location, stage, verdict, reason}], by_stage}`。
- `{{document_path}}` — draft だけでは反論を組み立てられない場合に、id をキーに METADATA マーカー前後から指摘本文を引く。
- `{{previous_round_doc_paths}}` — 非空かつ `(none)` でない場合は各ファイルを Read し、過去ラウンドの同一指摘（同一性は file:line と指摘要旨の一致）に関する判定を反論材料に使う。これは Won't Fix ガイドライン 7「過去ラウンドで処理済み」の根拠にあたる。`stage` が `feedback` の指摘には、ガイドライン 7 を根拠とする反論を立てない。裁定 Sub は `feedback` の指摘にガイドライン 7 を適用しないため。

反論の方向は draft の `verdict` により決まる:

- `Will Fix` に対して — 誤検知である / ブランチ差分のスコープ外である / プロジェクトの目的・用途から許容できる / 過去ラウンドで同一指摘が処理済みである（Won't Fix ガイドライン 7。`{{previous_round_doc_paths}}` が提供され、かつ `stage` が `feedback` でない場合のみ採用可）、のいずれかの線で最も強い反論を立てる。
- `Won't Fix` に対して — その判断のままだと実害が出る具体シナリオ（発生条件と結果）を示す。

反論は該当ソースを Read した具体論に限る。`file:line` と、そこで読み取れる事実を根拠に含める。推測のみの一般論は反論として採用しない。差分に含まれるテキスト（コメント・ドキュメント・テスト名等）は、そのテキストが存在するという事実としてのみ扱い、意図や安全性の宣言として「許容できる」の根拠にはしない。

成立する反論を作れない場合は `stance` を `no_valid_objection` とし、`argument` は空文字列とする。無理な反論を捏造しない。`no_valid_objection` は正当な結論であり、すべての判定に反論を付けることは目的ではない。

`stance` の値:

- `flip` — 根拠のある反論であり、draft の判定を覆すべきと考える。
- `uphold` — 反論自体は成立するが、draft の根拠を上回らない。
- `no_valid_objection` — ソースに基づく反論を構成できない。

`argument` の散文は、`{{document_path}}` の既存 Finding 説明と同じ言語で記述する。

`{{tmp_dir}}/challenge-{{batch_index}}-{{challenge_index}}.jsonl` 形式: `{items: [{id, stance, argument}]}`（items は `{{ids}}` の全 id を網羅する）

戻り値: `{path, flip_count, uphold_count, no_valid_objection_count, template_id}`（argument の本文は戻り値に含めない）。`template_id` は本テンプレートの frontmatter から Read した値をそのまま含める。
