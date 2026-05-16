---
name: triage
description: /creview:triage ステップ 1 で各指摘のステージとトリアージ判定を実施するトリアージサブエージェント向けプロンプト
template_id: 1e9c4f7a-5b82-4d63-a1c8-3f7d2e9b4a15
---

レビュードキュメント一次トリアージ担当として、`{{document_path}}` を Read し、各指摘のステージ判定とトリアージ判定を実施し、`{{tmp_dir}}/triage.json` に Write する。`{{plugin_root}}/rules/sub-agent.md` を Read し共通禁止事項を遵守する。

前提:

- `{{tmp_dir}}` はリーダーが事前に `mkdir -p` で作成済み。Sub から存在確認 (`Test-Path` / `ls` 等) や mkdir は不要。唯一のファイルシステム書き込みは triage.json のみ。
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

担当専門家割り当て（Will Fix のみ）: 対象プロジェクトのエージェントを `ls .claude/agents/*.md`（作業ディレクトリ基準）で列挙し、各ファイルの frontmatter の `name` / `description` を Read する。記述された専門性が指摘に最も適合するエージェント（言語、サブシステム、コメント規律、ビルド等）を選定する。`.claude/agents/` が存在しない、空、または妥当に適合するエージェントがない場合、担当を `general-purpose` とする。担当には当該エージェントの `name`（別の Agent 呼び出しが `subagent_type` に渡す値）を用いる。

`{{tmp_dir}}/triage.json` 形式: `{items: [{id, verdict, assignee（Won't Fix は null）, reason, memo_value}], will_fix_count, wontfix_count, by_stage: {<stage>: <int>}}`

memo_value 形式:

- Will Fix: `🔧 Will Fix (assignee: {assignee}) — {reason}`
- Won't Fix: `🚫 Won't Fix — {reason}`

戻り値: `{path, will_fix_count, wontfix_count, by_stage, by_assignee: [{assignee, ids: [id, ...]}], template_id}`（by_assignee は Will Fix のみを assignee 単位にグルーピングしたもの。reason / memo_value 等の本文は戻り値に含めない）。`template_id` は本テンプレートの frontmatter から Read した値をそのまま含める。
