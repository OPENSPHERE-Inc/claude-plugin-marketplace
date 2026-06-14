# opensphere-inc - Claude Code プラグインマーケットプレース

*[English README](README.md)*

OPENSPHERE Inc. が保守する Claude Code プラグインマーケットプレースです。

## プラグイン

| プラグイン | 説明 |
|--------|-------------|
| `creview` | マルチエージェントによる並列コードレビューのワークフロー: start → triage → respond → resolve、および複数ラウンドの自動ドライバ。 |
| `cprompt` | AI 向けプロンプトを作成・編集し、プロンプト規律ルールに照らしてセルフチェックする。 |
| `cdev` | チームネイティブなマルチエージェントコーディングワークフロー: 常駐チームが設計とコーディングをペアレビューセルで実行し、最後に QA ゲートを通す。 |
| `agent-sequencer` | 外部プラグイン（[OPENSPHERE-Inc/agent-sequencer](https://github.com/OPENSPHERE-Inc/agent-sequencer)）。`creview` の `review_rounds.py` シーケンサプログラムの実行に必要。 |
| `x-twitter-scraper` | Xquik の外部プラグイン。X/Twitter データ取得、REST API、MCP、webhooks、SDK、抽出タスクに使う。 |

## インストール

このマーケットプレースを追加し、プラグインをインストールします:

```
/plugin marketplace add OPENSPHERE-Inc/claude-plugin-marketplace
/plugin install creview@opensphere-inc
/plugin install cprompt@opensphere-inc
/plugin install cdev@opensphere-inc
/plugin install x-twitter-scraper@opensphere-inc
```

`creview`・`cprompt`・`cdev` は単体で完結します。任意の `agent-sequencer` エントリは
独自の GitHub リポジトリから解決され、複数ラウンドレビューのシーケンサ駆動版を
使う場合にのみ必要です（[creview/README_ja.md](creview/README_ja.md) を参照）。

## スキルコマンド

| コマンド | 目的 |
|---------|---------|
| `/creview:start` | 並列コードレビューを実行し、レビュードキュメントを生成する。 |
| `/creview:triage` | 指摘をトリアージ・見積し、`triage` / `estimate` をドキュメントへ永続化する。 |
| `/creview:respond` | Will-Fix / Maintain / Alternative の指摘を修正し、`status` を永続化する。 |
| `/creview:resolve` | 修正をソースに照らして検証し、`verification` を永続化する。 |
| `/creview:rounds` | 4 つのフェーズを複数ラウンドにわたって自動反復する。 |
| `/cprompt:edit` | AI 向けプロンプトを作成・編集し、セルフチェックする。 |
| `/cdev:coding` | コーディングタスクをエンドツーエンドで実装する: 設計とコーディングをペアレビューセルで行い、最後に QA ゲート。 |

## レビュアー / 修正担当エージェント

`creview` は専門レビュアーエージェントを**同梱しません**。**移植先プロジェクト**
（`.claude/agents/`）→**ユーザー**（`~/.claude/agents/`）→**プラグイン同梱**の順に、
サブディレクトリを含めて再帰的（`**/*.md`）にエージェントを列挙し、各エージェントの
`description` を読み、指摘ごとに最も関連するエージェントを選定します。適切なエージェント
が存在しない場合は `general-purpose` にフォールバックします。集約用の
`review-helper` エージェントは `creview` プラグインに同梱されています。

## 信頼できる原本とローカライズ

リポジトリ直下の `src/` ディレクトリが全プラグインの**日本語マスタ**を保持し、
各プラグイン自身のツリーをミラーします。`src/<plugin>/...` が `<plugin>/...` に
対応します（例: `src/creview/skills/start/SKILL.md` は
`creview/skills/start/SKILL.md` に対応）。skills、rules、scripts、agents、および
（`creview` の場合）シーケンサプログラムを含みます。

実稼働のプラグインファイル（プラグイン直下の英語ファイル）は、日本語 `src/`
マスタをプラグイン変換を適用しつつ英語へ翻訳したものです。プラグインを更新する
際は、`src/<plugin>/` 配下の日本語マスタを編集し、その後実稼働の英語ファイルへ
再翻訳・変換を再適用します（スキルのリネーム、`${CLAUDE_PLUGIN_ROOT}` /
`{{plugin_root}}` のパス書き換え、`review-respond` → `triage` + `respond` の分割、
エージェントディスパッチの一般化）。
