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

`/creview:start` には `--adversarial` オプション（デフォルト OFF）があり、
Critical / Major の指摘に具体的な失敗シナリオを求める敵対的モードで
レビュアーを実行します（`/creview:rounds` も同じフラグを受け取り、
`/creview:start` へそのまま渡します）。`/creview:triage` の敵対的トリアージは
常時有効で、指摘を最大 8 件ずつのバッチに分割し、トリアージサブエージェントの
一次判定にバッチごとの 3 体の反証サブエージェントがそれぞれ独立に可能な範囲で
反対の論を立て、裁定サブエージェントが最終判定を決めます。一次判定が覆るのは、
担当バッチの 3 体のうち 2 体以上が反転を支持し、かつ裁定サブエージェントが
その根拠となる事実を確認できた場合に限られます。

`/creview:triage` と `/creview:respond` には `--adr` オプション
（デフォルト OFF）があり、設計判断を記録する ADR ファイルをレビュードキュメントの
隣に新規作成することを許可します（`{レビュードキュメント basename}-adr-{finding-id}.md`、
スケルトンは `rules/adr-format.md`）。見積時に、複数の実行可能なアプローチから
1 つを選んで修正方針を確定した指摘について見積サブエージェントが ADR を作成し、
ユーザーは `/creview:triage` と `/creview:respond` の間で ADR ファイルを編集
できます。レビュードキュメントの `Estimate:` メタデータから参照されている
ADR は、フラグに寄らず修正時に読み戻され（ユーザーが編集した Decision は
見積時のプランより優先）、Status / History が更新されます — `/creview:respond`
のフラグは、実装時に初めて生じた設計判断の ADR 新規作成のみを許可します。
後段のラウンドが同じ箇所を再修正した場合は、新規作成せず既存の ADR を更新または
Superseded にします。`/creview:rounds` も同じフラグを受け取り、両フェーズへ
そのまま渡します。

ネスト起動（`CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH`。デフォルトは 3）の
必要深度はエントリポイントごとに異なります。

- `/creview:rounds` — 3 以上。各フェーズをフェーズリーダーサブエージェントで
  実行し、そのサブエージェントが当該フェーズのサブエージェントを起動し、
  トリアージサブエージェントがさらに反証サブエージェントと裁定
  サブエージェントを起動します。
- `/creview:triage` 単体 — 2 以上。トリアージサブエージェントが反証
  サブエージェントと裁定サブエージェントを起動します。

長時間の実行はサブエージェントの枠を多く消費し、反証サブエージェントだけでも
指摘 8 件あたり 3 体になるため、`--max-rounds` を大きくする場合は
`CLAUDE_CODE_MAX_SUBAGENTS_PER_SESSION`（デフォルト 200、セッション累積）の
引き上げを検討してください。

## レビュアー / 修正担当エージェント

このプラグインは専門エージェントを同梱しません。triage / scope-analysis /
analysis / format-build-verify の各サブエージェントが**移植先プロジェクト**
（`.claude/agents/`）→**ユーザー**（`~/.claude/agents/`）→**プラグイン同梱**の順に、
サブディレクトリを含めて再帰的（`**/*.md`）にエージェントを列挙し、各エージェントの
frontmatter の `name` / `description` を読み、指摘ごとに最適なものを選定します。
一致が無い場合は `general-purpose` に
フォールバックします。同梱エージェントは `review-helper`（機械的な集約 / 検証）、
`comment-sensei`（コメント規律レビュー）、`review-leader`（`/creview:rounds` の
フェーズリーダー）の 3 つです。

## 同梱サポートファイル

- `rules/` — `comment.md`、`document.md`、`review.md`、`wontfix.md`、`sub-agent.md`、
  `adr-format.md`（スキルが参照するルールのみ）。
- `scripts/` — `fetch-diff.sh`、`render-review.py`、`del-tmp.sh`、
  `lib/scratch-guard.py`（`fetch-diff.sh` / `del-tmp.sh` が共有する
  `.claude/tmp/` 封じ込めチェック）。これらのスクリプトは `PATH` 上の
  `python3`（3.9 以降）を必要とします。スキルは
  `${CLAUDE_PLUGIN_ROOT}/scripts/...` 経由で呼び出し、サブエージェント
  テンプレートは起動変数 `{{plugin_root}}` で解決済みパスを受け取ります。
- `skills/{triage,respond,resolve}/scripts/compile-review.py` — スキルごとの
  compile ステップ（リーダーが実行）。中間 JSON を `events.jsonl` に集約し
  `render-review.py` を呼び出します。
- `sequencer/programs/review_rounds.py` — `/creview:rounds` の決定論的な
  シーケンサプログラム版。

## シーケンサ版（review_rounds.py）

`sequencer/programs/review_rounds.py` は、`/creview:rounds` スキルの代わりに
[agent-sequencer](https://github.com/OPENSPHERE-Inc/agent-sequencer) MCP
サーバ経由で同じ複数ラウンドフローを駆動します。`agent-sequencer` プラグイン /
MCP サーバに依存します（このマーケットプレースに外部プラグインとして登録）。
プログラムは agent-sequencer のプログラムディレクトリに配置してください。
この構成ではオーケストレーター自身がトリアージのリーダーとなるため、
必要な深度は `/creview:rounds` の 3 ではなく 2 以上です。
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
