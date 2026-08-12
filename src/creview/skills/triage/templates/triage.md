---
name: triage
description: /creview:triage ステップ 1 で各指摘のステージ判定と敵対的トリアージ（提案 → 並列反証 → 多数決を条件とする裁定）を実施するトリアージサブエージェント向けプロンプト
template_id: 1e9c4f7a-5b82-4d63-a1c8-3f7d2e9b4a15
---

レビュードキュメントのトリアージ担当として、`{{document_path}}` を Read し、各指摘のステージ判定と敵対的トリアージ（提案 → 並列反証 → 多数決を条件とする裁定）を実施し、最終結果を `{{tmp_dir}}/triage.jsonl` に Write する。`{{plugin_root}}/rules/sub-agent.md` を Read し共通禁止事項を遵守する。

前提:

- `{{tmp_dir}}` はリーダーが事前に `mkdir -p` で作成済み。Sub から存在確認 (`Test-Path` / `ls` 等) や mkdir は不要。自身のファイルシステム書き込みは `triage-draft.jsonl` と `triage.jsonl` の 2 つ。ネスト起動する反証 Sub / 裁定 Sub は、それぞれのテンプレートが指定する `challenge-{b}-{n}.jsonl` / `adjudication.jsonl` を書く。
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

`{{plugin_root}}/rules/wontfix.md` を Read し、`Won't Fix` の判定に適用する。

手順:

1. 判定対象ごとに一次判定を行い `{{tmp_dir}}/triage-draft.jsonl` に Write する。この段では assignee を解決しない。
2. draft の `items` が空の場合は手順 3・4 をスキップし、`items: []` / `will_fix_count: 0` / `wontfix_count: 0` / draft の `by_stage` を持つ `{{tmp_dir}}/triage.jsonl` を Write し、`flipped_count: 0` と `adjudication_skipped: true` を返す。
3. draft の `items` を draft の順序のまま最大 8 件ずつのバッチに分割し、バッチに 1 から番号を振る。各バッチにつき反証 Sub 3 体を `Agent(subagent_type="general-purpose", prompt=...)` で起動し、`challenge_index` に 1 / 2 / 3 を与える。全バッチ分を同一メッセージ内に起動する。モデル指定はしない。受け取った変数値を埋めた起動プロンプト（`{b}` は当該インスタンスのバッチ番号、`{n}` は `challenge_index`、`{batch_ids}` はバッチ `{b}` の id をカンマ区切りで列挙したもの）:

```
最初の行動として `{{plugin_root}}/skills/triage/templates/triage-challenge.md` を必ず Read する。Read 完了前に他の判断・行動・ツール呼び出しを行わない。Read 後はその指示に従う。

変数（テンプレート中の {{...}} placeholder を置換）:
- plugin_root: {{plugin_root}}
- document_path: {{document_path}}
- tmp_dir: {{tmp_dir}}
- previous_round_doc_paths: {{previous_round_doc_paths}}
- batch_index: {b}
- challenge_index: {n}
- ids: {batch_ids}

ラウンド固有のオーバーライド（テンプレートの指示に従った後に適用）:
- (none)

戻り値に template_id（テンプレートの frontmatter から Read）を含める。
```

各戻り値の `template_id` が `b8701509-403b-488b-8b13-c867f9c6700b` と一致することを確認する。不一致の（バッチ, challenge_index）の組のみ、同一 `subagent_type` の新規インスタンスを同じ `batch_index` / `ids` / `challenge_index` で起動して再試行する。2 回連続で不一致となった組、および Agent の起動自体が失敗した組（ネスト起動の深度上限到達等）は反証出力を持たないものとし、一致を返した組だけで続行する。

draft の判定を覆すには当該 id の所属バッチからの flip 票が 2 票必要なため、反証出力を 2 つ以上持つバッチが 1 つも無い場合は手順 4 をスキップし、draft の `verdict` / `reason` をそのまま最終判定として手順 5 の要領で `{{tmp_dir}}/triage.jsonl` を Write し、`flipped_count: 0` と `adjudication_skipped: true` を返す。

4. 裁定 Sub を `Agent(subagent_type="general-purpose", prompt=...)` で起動する。手順 3 の全 Sub の戻り値を受け取ってから起動する。手順 3 と同一メッセージで並列起動しない。モデル指定はしない。受け取った変数値を埋めた起動プロンプト:

```
最初の行動として `{{plugin_root}}/skills/triage/templates/triage-adjudicate.md` を必ず Read する。Read 完了前に他の判断・行動・ツール呼び出しを行わない。Read 後はその指示に従う。

変数（テンプレート中の {{...}} placeholder を置換）:
- plugin_root: {{plugin_root}}
- document_path: {{document_path}}
- tmp_dir: {{tmp_dir}}
- previous_round_doc_paths: {{previous_round_doc_paths}}
- challenge_paths: {生成された {{tmp_dir}}/challenge-{b}-{n}.jsonl のパスをカンマ区切りで列挙}

ラウンド固有のオーバーライド（テンプレートの指示に従った後に適用）:
- (none)

戻り値に template_id（テンプレートの frontmatter から Read）を含める。
```

戻り値の `template_id` が `1921777f-3486-44ff-bc18-2b859ce75122` と一致することを確認する。不一致の場合は同一 `subagent_type` の新規インスタンスを起動して再試行する。2 回連続で不一致となった場合は手順 5 に進まず、`triage.jsonl` を Write せずに `{path: null, error: "adjudicate template_id mismatch twice", template_id}` を返す。Agent の起動自体が失敗した場合は、draft の `verdict` / `reason` をそのまま最終判定として手順 5 の要領で `{{tmp_dir}}/triage.jsonl` を Write し、`flipped_count: 0` と `adjudication_skipped: true` を返す。

5. `{{tmp_dir}}/adjudication.jsonl` の `verdict` と `reason` をそのまま採用し（reason は加工しない）、確定した Will Fix 集合に対してのみ `{{plugin_root}}/rules/agents-detection.md` の手順で assignee を解決し（マッチ対象は指摘内容（言語・サブシステム・コメント規律・ビルド等）、記録先は assignee）、`{{tmp_dir}}/triage.jsonl` を Write する。`adjudication.jsonl` に欠けている id、および `verdict` が `Will Fix` / `Won't Fix` 以外の id は、draft の `verdict` と `reason` を採用し反転なしとして数える。`{{tmp_dir}}/adjudication.jsonl` の Read に失敗した場合（ファイルが存在しない等）は、全 id について draft の `verdict` と `reason` を最終判定として採用し、Will Fix 集合の assignee は通常どおり解決して `{{tmp_dir}}/triage.jsonl` を Write し、`flipped_count: 0` とする。

`{{tmp_dir}}/triage-draft.jsonl` 形式: `{items: [{id, severity, location, stage, verdict（Will Fix | Won't Fix）, reason}], by_stage: {<stage>: <int>}}`（Needs Investigation は Write 前にいずれかの verdict へ決着させる）

`{{tmp_dir}}/triage.jsonl` 形式: `{items: [{id, verdict, assignee（Won't Fix は null）, reason, memo_value}], will_fix_count, wontfix_count, by_stage: {<stage>: <int>}}`

集計の基準: `will_fix_count` / `wontfix_count` / `by_assignee` / `memo_value` は最終判定に従う。`by_stage` は draft のものを引き継ぐ。`flipped_count` は `adjudication.jsonl` の `flipped == true` の件数。

`reason` および `memo_value` の散文は、`{{document_path}}` の既存 Finding 説明と同じ言語で記述する（`🔧 Will Fix` / `🚫 Won't Fix` のラベルと絵文字、`(assignee: ...)` は固定）。

memo_value 形式:

- Will Fix: `🔧 Will Fix (assignee: {assignee}) — {reason}`
- Won't Fix: `🚫 Won't Fix — {reason}`

戻り値: `{path, will_fix_count, wontfix_count, flipped_count, by_stage, by_assignee: [{assignee, ids: [id, ...]}], template_id}`。裁定を省略した経路では `adjudication_skipped: true` を追加し、手順 4 の 2 回連続不一致の経路では代わりに `error` 形式を返す（by_assignee は Will Fix のみを assignee 単位にグルーピングしたもの。reason / memo_value 等の本文は戻り値に含めない）。`template_id` は本テンプレートの frontmatter から Read した値をそのまま含める。
