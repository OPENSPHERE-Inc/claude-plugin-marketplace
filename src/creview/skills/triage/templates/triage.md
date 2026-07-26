---
name: triage
description: /creview:triage ステップ 1 で各指摘のステージ判定と敵対的トリアージ（提案 → 反証 → 裁定）を実施するトリアージサブエージェント向けプロンプト
template_id: 1e9c4f7a-5b82-4d63-a1c8-3f7d2e9b4a15
---

レビュードキュメントのトリアージ担当として、`{{document_path}}` を Read し、各指摘のステージ判定と敵対的トリアージ（提案 → 反証 → 裁定）を実施し、最終結果を `{{tmp_dir}}/triage.json` に Write する。`{{plugin_root}}/rules/sub-agent.md` を Read し共通禁止事項を遵守する。

前提:

- `{{tmp_dir}}` はリーダーが事前に `mkdir -p` で作成済み。Sub から存在確認 (`Test-Path` / `ls` 等) や mkdir は不要。自身のファイルシステム書き込みは `triage-draft.json` と `triage.json` の 2 つ。ネスト起動する反証 Sub / 裁定 Sub は、それぞれのテンプレートが指定する `challenge.json` / `adjudication.json` を書く。
- 渡されるパス (`{{document_path}}` / `{{tmp_dir}}`) は相対形式。絶対パスへの変換は行わない。

`{{previous_round_doc_paths}}` が提供されていれば（Round 1 で実施する標準フローでは空）、各ファイルを Read して過去ラウンドの判定情報（id / location / description / METADATA の triage / estimate / status / verification）を抽出し、トリアージで参照する。空または `(none)` の場合は参照不要。

抽出対象: Critical / Major / Minor セクション（Info はスキップ）。各指摘から id（C-1, M-1, mi-1 等）/ severity / location / description（マーカーまでの本文）/ current_meta（triage / estimate / status / verification の現在値、同フィールド複数出現時は最後の値）を取得する。

stage 分類（current_meta に基づく）:

- マーカー内が空 → pending_triage
- triage: 🔧 Will Fix、estimate なし → pending_estimate
- estimate: ▶️ Maintain または 🚧 Alternative、status なし → pending_fix
- verification 最終値が 💬 Feedback → feedback（再修正対象）
- triage: 🚫 Won't Fix → wontfix_skip
- estimate: 🔻 Downgrade → downgrade_skip
- status: 🟢 Fixed、verification なしまたは最終値が ✅ Verified → fixed_skip

判定対象は stage が pending_triage または feedback の指摘のみ。それ以外の stage はカウントのみ行いトリアージ判定はしない。

判定種別:

- Will Fix — 妥当、対応すべき
- Won't Fix — 該当しない / 誤検知 / リスク許容（理由必須）
- Needs Investigation — ソース調査後に Will Fix / Won't Fix に決着

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

手順:

1. 判定対象ごとに一次判定を行い `{{tmp_dir}}/triage-draft.json` に Write する。この段では assignee を解決しない。
2. draft の `items` が空の場合は手順 3・4 をスキップし、`items: []` / `will_fix_count: 0` / `wontfix_count: 0` / draft の `by_stage` を持つ `{{tmp_dir}}/triage.json` を Write し、`flipped_count: 0` で返す。
3. 反証 Sub を `Agent(subagent_type="general-purpose", prompt=...)` で起動する。モデル指定はしない。受け取った変数値を埋めた起動プロンプト:

```
最初の行動として `{{plugin_root}}/skills/triage/templates/triage-challenge.md` を必ず Read する。Read 完了前に他の判断・行動・ツール呼び出しを行わない。Read 後はその指示に従う。

変数（テンプレート中の {{...}} placeholder を置換）:
- plugin_root: {{plugin_root}}
- document_path: {{document_path}}
- tmp_dir: {{tmp_dir}}
- previous_round_doc_paths: {{previous_round_doc_paths}}

ラウンド固有のオーバーライド（テンプレートの指示に従った後に適用）:
- (none)

戻り値に template_id（テンプレートの frontmatter から Read）を含める。
```

戻り値の `template_id` が `b8701509-403b-488b-8b13-c867f9c6700b` と一致することを確認する。不一致の場合は同一 `subagent_type` の新規インスタンスを起動して再試行する。2 回連続で不一致となった場合は以降の手順に進まず、`triage.json` を Write せずに `{path: null, error: "challenge template_id mismatch twice", template_id}` を返す。Agent の起動自体が失敗した場合（ネスト起動の深度上限到達等）は、手順 4 をスキップし、draft の `verdict` / `reason` をそのまま最終判定として手順 5 の要領で `{{tmp_dir}}/triage.json` を Write し、`flipped_count: 0` と反証・裁定を省略した旨を返す。

4. 裁定 Sub を `Agent(subagent_type="general-purpose", prompt=...)` で起動する。手順 3 の戻り値を受け取り `{{tmp_dir}}/challenge.json` の生成を確認してから起動する。手順 3 と同一メッセージで並列起動しない。モデル指定はしない。受け取った変数値を埋めた起動プロンプト:

```
最初の行動として `{{plugin_root}}/skills/triage/templates/triage-adjudicate.md` を必ず Read する。Read 完了前に他の判断・行動・ツール呼び出しを行わない。Read 後はその指示に従う。

変数（テンプレート中の {{...}} placeholder を置換）:
- plugin_root: {{plugin_root}}
- document_path: {{document_path}}
- tmp_dir: {{tmp_dir}}
- previous_round_doc_paths: {{previous_round_doc_paths}}

ラウンド固有のオーバーライド（テンプレートの指示に従った後に適用）:
- (none)

戻り値に template_id（テンプレートの frontmatter から Read）を含める。
```

戻り値の `template_id` が `1921777f-3486-44ff-bc18-2b859ce75122` と一致することを確認する。不一致の場合は同一 `subagent_type` の新規インスタンスを起動して再試行する。2 回連続で不一致となった場合は手順 5 に進まず、`triage.json` を Write せずに `{path: null, error: "adjudicate template_id mismatch twice", template_id}` を返す。Agent の起動自体が失敗した場合は、draft の `verdict` / `reason` をそのまま最終判定として手順 5 の要領で `{{tmp_dir}}/triage.json` を Write し、`flipped_count: 0` と裁定を省略した旨を返す。

5. `{{tmp_dir}}/adjudication.json` の `verdict` と `reason` をそのまま採用し（reason は加工しない）、確定した Will Fix 集合に対してのみ `{{plugin_root}}/rules/agents-detection.md` の手順で assignee を解決し（マッチ対象は指摘内容（言語・サブシステム・コメント規律・ビルド等）、記録先は assignee）、`{{tmp_dir}}/triage.json` を Write する。`adjudication.json` に欠けている id、および `verdict` が `Will Fix` / `Won't Fix` 以外の id は、draft の `verdict` と `reason` を採用し反転なしとして数える。`{{tmp_dir}}/adjudication.json` の Read に失敗した場合（ファイルが存在しない等）は、全 id について draft の `verdict` と `reason` を最終判定として採用し、Will Fix 集合の assignee は通常どおり解決して `{{tmp_dir}}/triage.json` を Write し、`flipped_count: 0` とする。

`{{tmp_dir}}/triage-draft.json` 形式: `{items: [{id, severity, location, stage, verdict（Will Fix | Won't Fix）, reason}], by_stage: {<stage>: <int>}}`（Needs Investigation は Write 前にいずれかの verdict へ決着させる）

`{{tmp_dir}}/triage.json` 形式: `{items: [{id, verdict, assignee（Won't Fix は null）, reason, memo_value}], will_fix_count, wontfix_count, by_stage: {<stage>: <int>}}`

集計の基準: `will_fix_count` / `wontfix_count` / `by_assignee` / `memo_value` は最終判定に従う。`by_stage` は draft のものを引き継ぐ。`flipped_count` は `adjudication.json` の `flipped == true` の件数。

`reason` および `memo_value` の散文は、`{{document_path}}` の既存 Finding 説明と同じ言語で記述する（`🔧 Will Fix` / `🚫 Won't Fix` のラベルと絵文字、`(assignee: ...)` は固定）。

memo_value 形式:

- Will Fix: `🔧 Will Fix (assignee: {assignee}) — {reason}`
- Won't Fix: `🚫 Won't Fix — {reason}`

戻り値: `{path, will_fix_count, wontfix_count, flipped_count, by_stage, by_assignee: [{assignee, ids: [id, ...]}], template_id}`（by_assignee は Will Fix のみを assignee 単位にグルーピングしたもの。reason / memo_value 等の本文は戻り値に含めない）。`template_id` は本テンプレートの frontmatter から Read した値をそのまま含める。
