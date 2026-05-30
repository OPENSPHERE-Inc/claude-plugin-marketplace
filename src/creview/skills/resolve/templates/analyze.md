---
name: analyze
description: /creview:resolve ステップ 1 でレビュードキュメントから各指摘の id / 検証担当を抽出する解析サブエージェント向けプロンプト
template_id: 5d9e2c8a-1f74-4b63-a9d8-3c5f7e1b9a42
---

レビュードキュメント `{{document_path}}` を Read し、各指摘の id / 検証担当 (assignee) を抽出する（ファイル出力なし）。`{{plugin_root}}/rules/sub-agent.md` を Read し共通禁止事項を遵守する。

抽出対象: Critical / Major / Minor（Info はスキップ）。METADATA マーカーの状態に関わらず全 finding を `by_assignee` に含める（verify Sub が Resolved / Feedback / Unresolved いずれの判定も担当するため、未トリアージや見積未完了の指摘も dispatch 対象）。

検証担当 (assignee) の決定:

- Triage 行に "(assignee: {specialist})" があれば、その specialist を使う。
- assignee 不在の場合（マーカーが空 / Triage が 🚫 Won't Fix で assignee 行なし 等）、`{{plugin_root}}/rules/agents-detection.md` の手順で agent を解決する。マッチ対象は当該指摘の `Reviewers` と内容、記録先は assignee。

戻り値: `{total, by_assignee: [{assignee, ids: [id, ...]}], template_id}`。`template_id` は本テンプレートの frontmatter から Read した値をそのまま含める。
