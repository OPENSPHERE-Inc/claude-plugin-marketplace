---
name: divergence-check
description: /creview:rounds ステップ 2.2 で、指摘への修正が次の指摘を生む連鎖からラウンドループの発散を検出する発散パターン検出サブエージェント向けプロンプト
template_id: 6570a998-e9f3-4421-af84-6911eebd7c07
---

ラウンドループの発散 — 指摘への修正が後のラウンドの指摘を生む連鎖が、縮小せずに続いている状態 — をすべて検出する。`{{plugin_root}}/rules/sub-agent.md` を Read し共通禁止事項を遵守する。

入力:

- 今ラウンドのレビュードキュメント: `{{document_path}}`
- 過去ラウンドのレビュードキュメントのパス: `{{previous_round_doc_paths}}`
- 検出結果の出力先: `{{output_path}}`

判定材料はこれらのレビュードキュメント（指摘本文と、`<!-- METADATA(id) -->` ブロックの Triage / Estimate / Status / Verification）に限る。

定義:

- 修正対象の指摘: Triage が `🔧 Will Fix` で、Estimate が `🔻 Downgrade` でない指摘。
- 連鎖リンク: あるラウンドの修正対象の指摘のうち、それより前のラウンドの指摘への修正（`Status: 🟢 Fixed — ...` に記された変更）を原因とするもの。その修正が導入・変更したコードを問題にしている指摘が該当する。箇所が重なるだけで、修正前からある問題を指す指摘は該当しない。
- 連鎖: 連鎖リンクを過去へ辿った列（指摘 → その修正 → 次の指摘 → その修正 → ...）。

以下に該当する連鎖をすべて発散として検出する。起点の指摘を共有する連鎖は 1 件の発散にまとめる:

- 縮小しない連鎖: 今ラウンドの連鎖リンクの総数が直前ラウンドの連鎖リンクの総数以上である場合の、今ラウンドの連鎖リンクで終わり 3 ラウンド以上にまたがる各連鎖。
- 往復: 今ラウンドの修正対象の指摘が、過去ラウンドの修正を元に戻すこと、またはその修正と相反する変更を求めている連鎖。

発散を 1 件以上検出した場合:

- 検出結果を `{{output_path}}` に Write する。形式: `{divergences: [{id, kind, links}]}`
  - `id`: `D-1` からの連番。
  - `kind`: 往復に該当すれば `"oscillation"`、それ以外は `"chain"`。
  - `links`: 発散を構成する全指摘を古い順に並べた `{round, id, location, finding, fix}` の配列。`finding` は指摘の、`fix` はその指摘への修正の 1 行要約。今ラウンドの指摘の `fix` は null。
- `{{plugin_root}}/rules/agents-detection.md` の手順で、発散の源泉を調査する agent を解決する。マッチ対象は検出した全発散の指摘内容、記録先は `investigator`。

戻り値: `{divergence_count, investigator, template_id}`。`investigator` は発散が 0 件なら null。`template_id` は本テンプレートの frontmatter から Read した値をそのまま含める。
