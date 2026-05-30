# creview

*[English README](README.md)*

Claude Code 向けのマルチエージェント並列コードレビューワークフロー。

## スキル

| コマンド | 由来 | 目的 |
|---------|-----------|---------|
| `/creview:start` | `parallel-review` | 並列コードレビューを実行し、メタデータマーカー付きのレビュードキュメントを生成する。 |
| `/creview:triage` | `review-respond`（トリアージ + 見積） | 指摘をトリアージ・見積し、`triage` / `estimate` をドキュメントへ永続化する。 |
| `/creview:respond` | `review-respond`（修正） | Will-Fix / Maintain / Alternative の指摘を修正し、ビルドを検証し、`status` を永続化する。 |
| `/creview:resolve` | `review-resolve` | 修正の解決状況をソースに照らして検証し、`verification` を永続化する。 |
| `/creview:rounds` | `review-rounds` | start → triage → respond → resolve を複数ラウンドにわたって自動反復する。 |

`review-respond` は 2 つのスキルに分割されました。先に `/creview:triage <doc>`
を実行し、ドキュメントに永続化された判定を確認してから `/creview:respond <doc>`
を実行します。どちらのスキルにも確認プロンプトはありません — 分割そのものが
レビューゲートです。`/creview:respond` は `--commit` オプションを保持します。

## レビュアー / 修正担当エージェント

このプラグインは専門エージェントを同梱しません。triage / scope-analysis /
analysis / format-build-verify の各サブエージェントが**移植先プロジェクト**
（`.claude/agents/`）→**ユーザー**（`~/.claude/agents/`）→**プラグイン同梱**の順に、
サブディレクトリを含めて再帰的（`**/*.md`）にエージェントを列挙し、各エージェントの
frontmatter の `name` / `description` を読み、指摘ごとに最適なものを選定します。
一致が無い場合は `general-purpose` に
フォールバックします。機械的な集約 / 編纂 / 検証を担うエージェント
`review-helper` は同梱されています（`agents/review-helper.md`）。

## 同梱サポートファイル

- `rules/` — `comment.md`、`document.md`、`review.md`、`sub-agent.md`
  （スキルが参照するルールのみ）。
- `scripts/` — `fetch-diff.sh`、`render-review.py`、`rm-tmp.sh`。スキルは
  `${CLAUDE_PLUGIN_ROOT}/scripts/...` 経由で呼び出し、サブエージェント
  テンプレートは起動変数 `{{plugin_root}}` で解決済みパスを受け取ります。
- `sequencer/programs/review_rounds.py` — `/creview:rounds` の決定論的な
  シーケンサプログラム版。

## シーケンサ版（review_rounds.py）

`sequencer/programs/review_rounds.py` は、`/creview:rounds` スキルの代わりに
[agent-sequencer](https://github.com/OPENSPHERE-Inc/agent-sequencer) MCP
サーバ経由で同じ複数ラウンドフローを駆動します。`agent-sequencer` プラグイン /
MCP サーバに依存します（このマーケットプレースに外部プラグインとして登録）。
プログラムは agent-sequencer のプログラムディレクトリに配置してください。
Instruction プロンプトは英語で記述されており、呼び出すスキル
（`/creview:start|triage|respond|resolve`）はユーザーのチャット言語で
レビューを駆動します。

## 日本語マスタ（リポジトリ直下 `src/creview/`）

日本語マスタはリポジトリ直下の `src/creview/` にあり、本プラグインのツリーを
1 対 1 でミラーします（`src/creview/skills/start/SKILL.md` ↔
`creview/skills/start/SKILL.md` など）。スキル名もプラグインと同一です。
ここにある実稼働の英語ファイルは、そのマスタを翻訳・変換して生成されます。
更新する際は `src/creview/` 配下の日本語マスタを編集し、その後実稼働ファイルへ
再翻訳・変換を再適用します（リネーム、パス書き換え、`review-respond` →
`triage` + `respond` の分割、エージェントディスパッチの一般化）。
