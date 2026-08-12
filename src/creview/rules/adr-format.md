<!-- ADR スケルトン: {...} プレースホルダを置換し、見出しはすべて残す。
ファイル名: {レビュードキュメント basename}-adr-{finding-id}.md。レビュードキュメントと同じディレクトリに置く
（{レビュードキュメント basename} はレビュードキュメントのファイル名から .md を除いたもの。
例: review-round1.md + M-1 → review-round1-adr-M-1.md）。
散文の言語: レビュードキュメントの既存 Finding 説明と同じ言語。見出し、Source / Status キー、
Status 値は固定。
Status ライフサイクル: Proposed（見積時に作成。修正フェーズ前にユーザーが編集してよい）
→ Accepted（修正がこの判断を実装した）→ Superseded by {adr-filename} / Reverted
（後段の判断がこの判断を置換・巻き戻した）。
Status 遷移または内容更新のたびに History エントリを追記する。既存の History エントリは削除しない。 -->

# ADR: {finding-id} — {判断タイトル}

- **Source:** {レビュードキュメントのファイル名} / {finding-id}
- **Status:** {Proposed | Accepted | Superseded by {adr-filename} | Reverted}

## Context

{指摘が提起する問題と解決策を拘束する制約 — 1〜3 文}

## Decision

{選択したアプローチと決め手となった理由 — 1〜3 文}

## Alternatives

- {却下したアプローチ} — {却下理由}

## Consequences

{受け入れたトレードオフ、先送りした作業（FIXME）、将来の変更への影響}

## History

- {YYYY-MM-DD} {レビュードキュメントのファイル名} / {finding-id} — Created (Proposed)
- {YYYY-MM-DD} {レビュードキュメントのファイル名} / {finding-id} — {更新概要}
