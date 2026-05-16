# cprompt

*[English README](README.md)*

Claude Code 向けの AI 向けプロンプト（agent / skill / rule / command / 汎用
プロンプト）を作成・編集し、プロンプト規律ルールに照らしてセルフチェック・
修正します。

## スキル

| コマンド | 由来 | 目的 |
|---------|-----------|---------|
| `/cprompt:edit` | `prompt-editor` | AI 向けプロンプトを作成・編集し、同梱の `prompt.md` に照らしてセルフチェック・圧縮・テストする。 |

使い方: 新規作成は `/cprompt:edit <種別 + 対象パス + 要件>`、編集は
`/cprompt:edit <既存パス> <編集要件>`。種別が指定されない場合は、移植先
プロジェクトの `.claude/` 配下の対象パスから推測します
（`.claude/agents/{name}.md` → agent など）。

## 同梱サポートファイル

- `skills/edit/templates/` — 各プロンプト種別のスキャフォールドと
  `prompt.md` テストチェックリスト。
- `rules/` — `prompt.md`（プロンプト規律）と `document.md`（人間向け
  ドキュメント規律）。スキルが `${CLAUDE_PLUGIN_ROOT}/rules/...` 経由で
  参照します。

## 日本語マスタ（リポジトリ直下 `src/cprompt/`）

日本語マスタはリポジトリ直下の `src/cprompt/` にあり、本プラグインのツリーを
1 対 1 でミラーします（`src/cprompt/skills/edit/SKILL.md` ↔
`cprompt/skills/edit/SKILL.md` など）。スキル名もプラグインと同一です。
ここにある実稼働の英語ファイルは、そのマスタを翻訳・変換して生成されます。
更新する際は `src/cprompt/` 配下の日本語マスタを編集し、その後実稼働スキルへ
再翻訳・変換を再適用します（リネーム、`${CLAUDE_PLUGIN_ROOT}` のパス
書き換え）。
