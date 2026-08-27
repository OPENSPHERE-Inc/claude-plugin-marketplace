---
name: rounds
description: レビュー・トリアージ・対応・検証を複数ラウンド自動で繰り返し、対応すべき指摘がなくなるまで反復する
allowed-tools: Agent, Read, Glob, Grep, Bash(grep:*), Bash(ls:*), Bash(find:*), Bash(git branch:*), Bash(git rev-parse:*), Bash(mkdir:*)
---

# レビューラウンド自動実行

あなたは**レビューラウンドオーケストレーター**として、`/creview:start` → `/creview:triage` → `/creview:respond` → `/creview:resolve` に相当するフローを複数ラウンド自動で繰り返し、重要な問題を網羅的に発見して修正する。各フェーズはフェーズリーダーサブエージェントが実行し、あなたはラウンドループの制御と各フェーズの戻り値の集約を担う。詳細な責務分担は「サブエージェント利用ルール」を参照。

## 入力

ユーザーはオプションで出力ベースパスを指定できる。引数が `$ARGUMENTS` の場合、出力ベースパス（およびオプション）として解釈する。出力ベースパスが指定されない場合は、プロジェクトルートの `.claude/tmp/` をデフォルトとして使用する。

## オプション

- `--confirm`（デフォルト OFF）— トリアージ・見積がレビュードキュメントに永続化された後（ステップ 2.2）、修正フェーズ（ステップ 2.3）の前に、見積サマリをユーザーに提示して確認を待つ。
- `--confirm-round`（デフォルト OFF）— resolve 後、未解決の指摘が残っている場合、次ラウンドに進む前にユーザーの確認を待つ。
- `--commit`（デフォルト OFF）— 各指摘の修正後に git commit を行う（respond フェーズにそのまま渡す）。
- `--incremental`（デフォルト OFF）— Round 2 以降、ブランチ全体の差分ではなく、前ラウンド開始時点から今ラウンド開始時点までに追加されたコミット — 前ラウンドの修正コミット — のみをレビューする。有効にすると `--commit` も有効になる — コミットされない修正は以降のどのラウンドのコミット範囲にも入らないため。
- `--adr`（デフォルト OFF）— 設計判断の ADR ファイルを各ラウンドのレビュードキュメントの隣に新規作成することを許可する（triage / respond フェーズにそのまま渡す）。レビュードキュメントから参照されている ADR の読み込み・更新は、このフラグに寄らず修正時に実行される。
- `--max-rounds N`（デフォルト 5、範囲 1〜10）— 外側ループの最大ラウンド数を変更する。
- `--base {branch}`（デフォルト `main` または `master`）— ベースブランチを指定する（review フェーズに渡される）。`--incremental` は Round 2 以降これを上書きする。
- `--adversarial`（デフォルト OFF）— review フェーズを敵対的モードで実行する（review フェーズにそのまま渡す）。

## レビュードキュメントのファイル命名

- 形式: `{base-path}/{branch-dir}/review-round{N}.md`
- ブランチ名の取得: `git branch --show-current` で現在のブランチ名を取得する。
- ブランチ名はディレクトリパスとして扱う — ブランチ名全体（`/` を含む）がそのままディレクトリ階層になる。
- 同一ブランチでの再実行時は `{branch-name}_1`、`{branch-name}_2`、... と末尾に連番を付ける（存在しない最小番号）。
  - 例: ブランチ `feat/add-replay` の初回 → `{base-path}/feat/add-replay/review-round1.md`、再実行 → `{base-path}/feat/add-replay_1/review-round1.md`
- デフォルトの base-path: `.claude/tmp/`。必要に応じてディレクトリを作成する。

## レビュードキュメントの言語

レビュードキュメントはユーザーのチャット言語で記述する。

## サブエージェント利用ルール

- **共通禁止事項とワンショット起動形態（`run_in_background: false`）は `${CLAUDE_PLUGIN_ROOT}/rules/sub-agent.md` を参照**。
- **各フェーズはフェーズリーダーサブエージェント（`subagent_type="review-leader"`）へ丸ごと委譲する**。フェーズ Sub は対応するスキルを起動し、そのスキルのサブエージェント群・compile ステップ・内部の再実行ループを含めて最後まで実行する。フェーズ Sub 自身がさらにサブエージェントを起動し、triage Sub がさらに反証 / 裁定 Sub を起動するため、ネスト起動の深度 3 以上が必要。
  - レビューフェーズ（ステップ 2.1） — `creview:start`
  - トリアージ&見積フェーズ（ステップ 2.2 / 2.5） — `creview:triage`
  - 対応フェーズ（ステップ 2.3 / 2.5） — `creview:respond`
  - 検証フェーズ（ステップ 2.4 / 2.5） — `creview:resolve`
- **最終レポート編纂サブエージェント（ステップ 3）** — `subagent_type="review-helper"`。全ラウンドのレビュードキュメントから最終レポートを生成する。
- **オーケストレーター（あなた自身）が直接担うのは以下に限定する**:
  - コンソール見出しの表示、ラウンドループ制御、フィードバック再修正ループ。
  - フェーズサブエージェントの起動と戻り値（カウンタ・パス・1 行サマリ）の集約。
  - `--confirm` / `--confirm-round` のユーザー対話。フェーズ Sub はユーザーに到達できないため、確認待ちはすべてフェーズ間のここで行う。
  - ユーザーへの最終的なサマリ提示。
- **オーケストレーターはレビュー指摘や判定の本文を context に載せない**。ファイルパス・カウンタ・リビジョンハッシュのみを保持し、詳細は各フェーズ内に留める。
- 各ラウンドの指摘と判定は**レビュードキュメントのみ**を通じて次ステップ／次ラウンドに引き継ぐ。ラウンドループ自身が持ち越す値は `{prev_round_rev}` だけ。
- 起動時に `model="..."` 指定は行わない（モデルは各 agent 定義の frontmatter に従う）。

## フェーズサブエージェントの起動

各フェーズは `Agent(subagent_type="review-leader", prompt=...)` で起動する:

```
最初の行動として `${CLAUDE_PLUGIN_ROOT}/skills/rounds/templates/{template}` を必ず Read する。Read 完了前に他の判断・行動・ツール呼び出しを行わない。Read 後はその指示に従う。

変数（テンプレート中の {{...}} placeholder を置換）:
- plugin_root: ${CLAUDE_PLUGIN_ROOT}
- {各ステップが挙げる変数}

ラウンド固有のオーバーライド（テンプレートの指示に従った後に適用）:
- {各ステップが挙げるオーバーライド。無い場合は (該当なし)}

戻り値に template_id（テンプレートの frontmatter から Read）を含める。
```

戻り値の `template_id` が各ステップの指定 UUID と一致することを確認し、不一致の場合はフェーズ Sub を再起動する。ステップ 3 のサブエージェントも同じ規約に従う。`${CLAUDE_PLUGIN_ROOT}/rules/sub-agent.md` § 起動プロンプトの完全性を参照。

## フロー概要

```
Round 1 開始
  ├─ 2.1 review          [フェーズ Sub] creview:start   → round1.md
  ├─ 2.2 triage+estimate  [フェーズ Sub] creview:triage  → トリアージ／見積を永続化
  │     ↳ --confirm: 見積サマリを提示し確認を待つ
  ├─ 2.3 respond / fix    [フェーズ Sub] creview:respond → status を永続化
  │     ↳ Maintain / Alternative の対象がなければスキップ
  ├─ 2.4 resolve          [フェーズ Sub] creview:resolve → verification を永続化
  ├─ 2.5 フィードバック再修正ループ（最大 3 回）→ フィードバック用オーバーライド付きで 2.2 → 2.3 → 2.4 を再実行
  └─ 2.6 ラウンド終了 → 次ラウンドに進む条件を判定
Round 2 開始（前ラウンドのレビュードキュメントは渡さない）
  └─ ...（--incremental: Round 1 が追加したコミットのみをレビュー）
最終ステップ
  └─ [最終レポート編纂 Sub] 全 round{N}.md + テンプレート → final-report.md
```

## ステップ 1 — 初期化

1. 出力ディレクトリの存在を確認し、なければ作成する。
2. 現在のブランチ名を取得する。
3. オプションを解析する。
4. ラウンドカウンターを 1、`{prev_round_rev}` を `(該当なし)` に設定する。

## ステップ 2 — ラウンドループ

ラウンドカウンターが `--max-rounds` 以下の間、以下を繰り返す。

### 2.1 — レビューフェーズ（start スキル）

1. コンソールに表示: `## Round {N} — Step 1: Review`
2. `git rev-parse HEAD` で今ラウンドの開始リビジョン `{this_round_rev}` を記録する。
3. 今ラウンドのレビュー対象を確定する:
   - `--incremental` が OFF、または `{prev_round_rev}` が `(該当なし)`: `{review_base}` = `--base` の値、`{review_range}` = `(該当なし)`。
   - それ以外: `{review_base}` = `{prev_round_rev}`、`{review_range}` = `{prev_round_rev}..{this_round_rev}`。両リビジョンが等しい場合は前ラウンドがコミットを残していないため、ラウンドループを終了してステップ 3 へ進む。
4. `templates/phase-review.md`（`template_id`: `3e7b1c9d-6a24-4f85-b1d7-8c2e5a9f3b64`）でフェーズ Sub を起動する。
   - 変数: `base`（`{review_base}`）、`review_range`（`{review_range}`）、`document_path`（今ラウンドのファイルパス）、`language`（ユーザーのチャット言語）、`adversarial`（`--adversarial` の状態）
   - オーバーライド: (該当なし)
5. 戻り値（`{doc_path, findings_total, severity_counts}`）のみ context に保持する。

### 2.2 — トリアージ&見積フェーズ（triage スキル）

1. コンソールに表示: `## Round {N} — Step 2: Triage & Estimate`
2. `templates/phase-triage.md`（`template_id`: `6d2a8f4c-1e93-4b57-9c8a-3f7b2d6e1a95`）でフェーズ Sub を起動する。
   - 変数: `document_path`（今ラウンドのファイルパス）、`previous_round_doc_paths`（Round 1: `(なし)`、Round N: Round 1〜N-1 の doc_path）、`adr_flag`（`--adr` の状態）
   - オーバーライド: フィードバックループ外は (該当なし)、ループ内はステップ 2.5 が挙げるもの
3. 戻り値（`{will_fix_count, wontfix_count, flipped_count, maintain_count, alternative_count, downgrade_count, summary_path, summary_line, error}`）のみ context に保持する。
4. `error` が非 null の場合は 2.3 以降に進まず、失敗をユーザーに報告してラウンドループを終了する。
5. ラウンドループ制御: `will_fix_count` が 0、または `maintain_count` と `alternative_count` がともに 0 の場合、2.3 をスキップして 2.4 に進む。
6. `--confirm`: Maintain / Alternative が 1 件以上ある場合、`summary_path` を Read してユーザーに提示し、2.3 の前に確認を待つ。

### 2.3 — 対応フェーズ（respond スキル）

1. コンソールに表示: `## Round {N} — Step 3: Respond (Fix & Verify)`
2. `templates/phase-respond.md`（`template_id`: `8b5e3d7a-4c16-4a92-a7f3-2d9c6b1e8f47`）でフェーズ Sub を起動する。
   - 変数: `document_path`、`commit_flag`（`--commit` の状態）、`adr_flag`（`--adr` の状態）
   - オーバーライド: フィードバックループ外は (該当なし)、ループ内はステップ 2.5 が挙げるもの
3. 戻り値（`{fix_count, fixed_count, code_changed, workflow_warning, summary_line}`）のみ context に保持する。`workflow_warning` が非 null の場合は本ラウンドの記録用に保持する。

### 2.4 — 検証フェーズ（resolve スキル）

1. コンソールに表示: `## Round {N} — Step 4: Resolve`
2. `templates/phase-resolve.md`（`template_id`: `2f9c6a1e-7b53-4d84-8e2b-5a1f9d3c7b26`）でフェーズ Sub を起動する。
   - 変数: `document_path`、`base`（今ラウンドの `{review_base}`）
   - オーバーライド: フィードバックループ外は (該当なし)、ループ内はステップ 2.5 が挙げるもの
3. 戻り値（`{summary_path, summary_line, resolved_count, feedback_count, unresolved_count}`）のみ context に保持する。

### 2.5 — フィードバック確認と再修正ループ

ステップ 2.4 の戻り値（`feedback_count`）から「フィードバック必要」な指摘の有無を判定する。レビュードキュメント本文を直接 Read しない。

- `feedback_count == 0`: ラウンド終了（2.6 へ）。
- `feedback_count > 0`: 再修正ループに入る（最大 3 回）。

各 attempt は 2.2 → 2.3 → 2.4 を再実行し、以下のテキストをフェーズ Sub の `overrides` 変数として渡す:

1. `## Round {N} — Step 5.1: Feedback Triage (attempt {M}/3)` を表示。2.2 をオーバーライド `トリアージサブエージェント: stage が "feedback" の指摘を優先的にトリアージする（current_meta.verification に Feedback 詳細あり）。` および `見積サブエージェント: current_meta.verification の Feedback 内容を踏まえて見積。コストが膨らむ場合は Downgrade を検討。` で再実行する。全件 Downgrade なら手順 2 をスキップして手順 3 へ。
2. `## Round {N} — Step 5.2: Feedback Fix (attempt {M}/3)` を表示。2.3 をオーバーライド `修正サブエージェント: current_meta.verification の Feedback 内容を踏まえて再修正。` で再実行する。戻り値の `workflow_warning` が非 null の場合は本ラウンドの記録値を更新する（後勝ち）。
3. `## Round {N} — Step 5.3: Feedback Verify (attempt {M}/3)` を表示。2.4 をオーバーライド `(該当なし)` で再実行。
4. フィードバックが残っていれば手順 1 に戻る。3 回で解消しない場合はラウンドを終了する（残った 💬 Feedback は 2.6 で「未解決」としてカウント）。
5. `--confirm-round` が有効で未解決が残っている場合、次ラウンドに進む前にユーザーの確認を待つ。

### 2.6 — ラウンド終了

ラウンドの結果を記録する。各カウンタはフェーズサブエージェントの戻り値から取得する（レビュードキュメント本文を Read してカウントしてはならない）:

- 総指摘数: レビューフェーズの `findings_total`
- 要対応の指摘数: トリアージフェーズの `will_fix_count`
- Won't Fix 数: トリアージフェーズの `wontfix_count`
- 反転数: トリアージフェーズの `flipped_count`
- Maintain / Alternative / Downgrade 数: トリアージフェーズの `maintain_count` / `alternative_count` / `downgrade_count`
- 修正数: 対応フェーズの `fixed_count`（Maintain 通常修正 + Alternative FIXME 付与の合計）
- 未解決数: ステップ 2.5 最終試行後の検証フェーズの `feedback_count`
- 解決数: 検証フェーズの `resolved_count`
- フィードバック試行回数: 本ラウンドで実施したステップ 2.5 の試行回数
- ラウンド開始リビジョン: 今ラウンドの `{this_round_rev}`
- workflow_warning: 2.3 / 2.5 で保持した `workflow_warning`（フォーマット／ビルド手順未解決のラウンドのみ。それ以外は null）

次のラウンドに進む条件: 以下の**すべて**を満たす場合に限り、`{prev_round_rev}` を今ラウンドの `{this_round_rev}` に設定し、ラウンドカウンターをインクリメントしてステップ 2.1 へ戻る:

1. ラウンドカウンターが `--max-rounds` 以下である。
2. 今ラウンドの対応フェーズの `code_changed` が true である。ステップ 2.3 をスキップした場合は false として扱う。

満たさない場合は最終レポート生成へ進む。

## ステップ 3 — 最終レポート（最終レポート編纂サブエージェントへ委譲）

最終レポートのパス: `{base-path}/{branch-dir}/final-report.md`

1. `Agent(subagent_type="review-helper", prompt=...)` で `templates/final-report-compile.md`（`template_id`: `4f8a2d1c-9b35-4e67-a2c1-8b5d3f9e7a16`）のサブエージェントを起動する。
   - 変数:
     - `round_doc_paths`: Round 1 → {round1_doc_path}, Round 2 → {round2_doc_path}, ...
     - `round_stats`: Round 1: findings=N, will_fix=N, flipped=N, maintain=N, alternative=N, downgrade=N, fixed=N, wontfix=N, feedback_attempts=N, unresolved=N, code_changed=<bool>, ...（workflow_warning が非 null のラウンドは末尾に workflow_warning="..." を付す）
     - `template_path`: {template_path}
     - `report_path`: {report_path}
     - `language`: ユーザーのチャット言語
   - オーバーライド: (該当なし)
2. オーケストレーターは戻り値（`{report_path, template_id}`）を受け取り、`report_path` のみを context に保持する。

### 最終レポート形式

テンプレート: `${CLAUDE_PLUGIN_ROOT}/skills/rounds/templates/final-report.md`（最終レポート編纂 Sub が Read して骨組みを把握する。リーダーは Sub プロンプトの `{template_path}` にこのパスを埋める）。

## ステップ 4 — 完了報告

最終レポートのパスをユーザーに報告し、主要な統計（総指摘数、解決数、未解決数）を簡潔に伝える。
