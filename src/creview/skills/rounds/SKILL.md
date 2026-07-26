---
name: rounds
description: レビュー・トリアージ・対応・検証を複数ラウンド自動で繰り返し、対応すべき指摘がなくなるまで反復する
allowed-tools: Agent, Read, Write, Edit, Glob, Grep, Bash(grep:*), Bash(ls:*), Bash(find:*), Bash(git log:*), Bash(git diff:*), Bash(git show:*), Bash(git status:*), Bash(git branch:*), Bash(mkdir:*), Bash(${CLAUDE_PLUGIN_ROOT}/scripts/rm-tmp.sh:*)
---

# レビューラウンド自動実行

あなたは**レビューラウンドオーケストレーター**として、`/creview:start` → `/creview:triage` → `/creview:respond` → `/creview:resolve` に相当するフローを複数ラウンド自動で繰り返し、重要な問題を網羅的に発見して修正する。あなた自身がレビュアーや修正担当者の役割を担うことはなく、すべてサブエージェントに委任する。詳細な責務分担は「サブエージェント利用ルール」を参照。

## 入力

ユーザーはオプションで出力ベースパスを指定できる。引数が `$ARGUMENTS` の場合、出力ベースパス（およびオプション）として解釈する。出力ベースパスが指定されない場合は、プロジェクトルートの `.claude/tmp/` をデフォルトとして使用する。

## オプション

- `--confirm`（デフォルト OFF）— トリアージ・見積がレビュードキュメントに永続化された後（ステップ 2.2）、修正フェーズ（ステップ 2.3）の前に、見積サマリをユーザーに提示して確認を待つ。
- `--confirm-round`（デフォルト OFF）— resolve 後、未解決の指摘が残っている場合、次ラウンドに進む前にユーザーの確認を待つ。
- `--commit`（デフォルト OFF）— 各指摘の修正後に git commit を行う（respond フェーズにそのまま渡す）。
- `--max-rounds N`（デフォルト 5、範囲 1〜10）— 外側ループの最大ラウンド数を変更する。
- `--base {branch}`（デフォルト `main` または `master`）— ベースブランチを指定する（review フェーズに渡される）。

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

- **共通禁止事項は `${CLAUDE_PLUGIN_ROOT}/rules/sub-agent.md` を参照**。
- **各サブエージェントへのプロンプト本体は外部テンプレート（`templates/*.md`、frontmatter に `template_id` を持つ）に格納されている**。オーケストレーターは Agent ツール起動時に「テンプレートを Read して指示に従う」旨の起動プロンプトに、変数値（`plugin_root: ${CLAUDE_PLUGIN_ROOT}` を含む）とラウンド固有オーバーライドを埋めて渡す。サブエージェントは戻り値に `template_id` を含める。オーケストレーターは戻り値の `template_id` が各ステップで指定されている UUID（参照先 SKILL にステップごとにハードコード）と一致することを確認し、不一致の場合は当該サブエージェントを再起動する。UUID は `${CLAUDE_PLUGIN_ROOT}/skills/{start,triage,respond,resolve}/SKILL.md` の各 SKILL に記載されている。
- **集約・編纂を含む大半の作業はサブエージェントに委譲する**:
  - 個別レビュアー（ステップ 2.1） — スコープ解析 Sub が選定したレビュアーを、対象プロジェクトの `.claude/agents/`（または `general-purpose`）から並列起動する。各レビュアーは指摘をファイルに Write し、戻り値はパスと件数のみ。
  - 集約サブエージェント（ステップ 2.1） — 個別レビュアーの出力ファイルを Read してレビュードキュメントに統合する（start § ステップ 3）。
  - トリアージサブエージェント（ステップ 2.2 / 2.5） — バイアスを避けるため別コンテキストで判断させ、レビュードキュメントを直接 Read して指摘抽出と判定を一段で実施（triage § ステップ 1）。
  - 個別の見積（ステップ 2.2 / 2.5） — assignee 単位の専門家サブエージェントに並列委譲、各 Sub が担当 ids を一括見積（triage § ステップ 2、読み取り専用）。
  - 見積集約サブエージェント（ステップ 2.2 / 2.5） — 個別見積結果のサマリを生成（triage § ステップ 2）。
  - 修正対象選定サブエージェント（ステップ 2.3 / 2.5） — レビュードキュメントのメタデータを Read し、assignee 単位でグルーピングした修正対象を返却（respond § ステップ 1）。
  - 個別の修正（ステップ 2.3 / 2.5） — assignee 単位の専門家サブエージェントに委譲、各 Sub が担当 ids を順次修正（respond § ステップ 2）。
  - コメントレビューサブエージェント（ステップ 2.3 / 2.5） — 修正サブエージェントが追加・変更したコメントを comment.md の規律に照らしてレビューし、違反があれば修正する（respond § ステップ 3）。
  - フォーマット&ビルド検証サブエージェント（ステップ 2.3 / 2.5） — 反映先プロジェクトのフォーマット／ビルド手順を解決して 1 回実行し、失敗時はコード分析で専門家を判定（修正は行わず推奨のみ返す）。
  - ビルド修正専門家サブエージェント（ステップ 2.3 / 2.5） — フォーマット&ビルド検証 Sub が判定した専門家として、ビルドエラーを修正する。完了後リーダーがフォーマット&ビルド検証 Sub を再起動する（respond § ステップ 4）。
  - 解析サブエージェント（ステップ 2.4 / 2.5） — レビュードキュメントを Read して検証担当割当 (by_assignee) を返却（resolve § ステップ 1、ファイル出力なし）。
  - 検証サブエージェント（ステップ 2.4 / 2.5） — specialist 単位で並列起動し、担当指摘を一括検証（resolve § ステップ 2、読み取り専用）。
  - 編纂（compile）は各スキルのリーダーが `compile-review.py` を直接実行する（サブ起動なし。ステップ 2.2 / 2.3 / 2.4 / 2.5）。中間ファイル群から events.jsonl を生成し render-review.py で markdown に反映（triage § ステップ 3 / respond § ステップ 5 / resolve § ステップ 3）。
  - 最終レポート編纂サブエージェント（ステップ 3） — 全ラウンドのレビュードキュメントから最終レポートを生成。
- **オーケストレーター（あなた自身）が直接担うのは以下に限定する**:
  - 各ステップ間の制御・ラウンドループ判定（フォーマット&ビルド検証 Sub ⇄ ビルド修正専門家 Sub の再実行ループ含む。各 Sub からの operational data ファイルは Read 可、ソースコード本体は読まない）。
  - サブエージェント起動と戻り値（軽量カウンタ・パス・1 行サマリ）の集約。
  - ユーザーへの最終的なサマリ提示。
- **オーケストレーターはレビュー指摘や判定の本文を context に載せない**。ファイルパスと軽量カウンタのみを保持し、詳細はサブエージェントが扱う。
- 各ラウンドの結果は**レビュードキュメントのみ**を通じて次ステップ／次ラウンドに引き継ぐ。サブエージェント間の中間データはステップ内で完結し、ステップを跨いで残してはならない。（ラウンド内では、トリアージ・見積は triage フェーズでドキュメントに永続化されるため、respond フェーズはそれをドキュメントから読み取る。）
- **集約・解析・修正対象選定・フォーマット&ビルド検証サブエージェントは `subagent_type="review-helper"`（analysis / estimate-summary / format-build-verify）または `subagent_type="general-purpose"`（triage / 修正対象選定）で起動する。** review-helper の agent 定義には `model: sonnet` が指定済み。レビュアー / 見積 / 修正 / 検証 / ビルド修正サブエージェントは、対象プロジェクトの `.claude/agents/`（または `general-purpose`）から解決した assignee を `subagent_type` で指定する。SKILL から `model="..."` 指定は行わない（モデルは各 agent 定義の frontmatter に従う）。

起動プロンプトの完全性に関する規約は `${CLAUDE_PLUGIN_ROOT}/rules/sub-agent.md` § 起動プロンプトの完全性を参照。

## フロー概要

```
Round 1 開始
  ├─ 2.1 review（start スキル）
  │     [スコープ解析 Sub] 対象プロジェクトの .claude/agents からレビュアーを選定
  │     [レビュアー群] 並列 → 各自 reviews/{name}.md に Write
  │     [集約 Sub] reviews/*.md → round1.md（トリアージ未実施）
  ├─ 2.2 triage + estimate（triage スキル）
  │     [トリアージ Sub] round1.md → triage.json（by_assignee 含む）
  │     ↳ Will Fix が 0 件なら Won't Fix トリアージを永続化し 2.4 へスキップ
  │     [見積 Sub 群（assignee 単位、並列）] → estimates/{id}.json
  │     [見積集約 Sub] estimates/*.json → estimate-summary.md
  │     [compile-review.py] triage.json + estimates/*.json → round1.md（トリアージ／見積を永続化）
  │     ↳ --confirm: 見積サマリを提示し確認を待つ
  ├─ 2.3 respond / fix（respond スキル）
  │     [修正対象選定 Sub] round1.md のメタデータ → targets.json（by_assignee）
  │     ↳ Maintain / Alternative の対象がなければ 2.4 へスキップ
  │     [修正 Sub 群（assignee 単位、並列）] Maintain を修正、Alternative に FIXME 付与 → statuses/{id}.json
  │     [フォーマット&ビルド検証 Sub] ⇄ [ビルド修正専門家 Sub] ループ（最大 5 回、リーダー制御）
  │     [compile-review.py] statuses/*.json → status を永続化
  ├─ 2.4 resolve（resolve スキル）
  │     [解析 Sub] round1.md → by_assignee（ファイル出力なし）
  │     [検証 Sub 群] specialist 単位で並列 → verifications/{id}.json
  │     [compile-review.py] verifications/*.json → verification を永続化
  ├─ 2.5 フィードバック再修正ループ（最大 3 回）
  │     [トリアージ Sub] → [見積 Sub 群] → [compile-review.py] → [修正対象選定] → [修正 Sub 群]
  │       → [フォーマット&ビルド検証 Sub] ⇄ [ビルド修正専門家 Sub] ループ
  │       → [compile-review.py] → [解析 Sub] → [検証 Sub 群] → [compile-review.py]
  └─ 2.6 ラウンド終了 → 次ラウンドに進む条件を判定
Round 2 開始（前ラウンドのレビュードキュメントは渡さない）
  └─ ...
最終ステップ
  └─ [最終レポート編纂 Sub] 全 round{N}.md + テンプレート → final-report.md
```

## ステップ 1 — 初期化

1. 出力ディレクトリの存在を確認し、なければ作成する。
2. 現在のブランチ名を取得する。
3. オプションを解析する。
4. ラウンドカウンターを 1 に設定する。

## ステップ 2 — ラウンドループ

ラウンドカウンターが `--max-rounds` 以下の間、以下を繰り返す。

### 2.1 — レビュー実行（start スキル）

オーケストレーター（あなた自身）が `/creview:start` の「レビューリーダー」役を直接担う。手順・テンプレート・形式は `${CLAUDE_PLUGIN_ROOT}/skills/start/SKILL.md` に従う。

実行手順:

1. コンソールに表示: `## Round {N} — Step 1: Review`
2. start § ステップ 1 に従い作業用ディレクトリと差分ファイルを準備し、スコープ解析サブエージェントを起動する。戻り値（`line_count` / `recommended_reviewers`）のみ context に保持する。
3. `recommended_reviewers` の各 `name` を `Agent(subagent_type=name, prompt=...)` で並列起動する。各レビュアーは指摘を `{tmp_dir}/reviews/{name}.md` に Write し、戻り値は `{path, severity counts}` のみ。
4. start § ステップ 3 に従い集約サブエージェントを起動してレビュードキュメントを生成する（出力先: {今ラウンドのファイルパス}、言語: ユーザーのチャット言語）。集約サブエージェントの戻り値（`{doc_path, findings_total, severity_counts}`）のみ context に保持する。
5. start § ステップ 4 に従い `{tmp_dir}` を削除する。

ラウンド固有のオーバーライド（テンプレートの指示に従った後に適用）:

- 前ラウンドのレビュードキュメントをレビュアーに渡さない（バイアス回避）。
- 前ラウンドとの重複排除は行わない。
- 収束誘導の防止:
  - **以下は絶対にレビュアーへのプロンプトに含めない**:
    - 過去ラウンドの指摘件数、件数の推移、「収束しつつある」等の傾向情報。
    - 過去ラウンドの指摘 ID（`C-1`、`M-1` 等）。
    - 過去ラウンドでの Fixed / Won't Fix 件数などの統計情報。
  - レビュアープロンプトテンプレートの一部を省略したり、指摘数を調整しようとして指示を付け足すことは禁止。
  - レビューオーケストレーター自身が、レビュアーから提出されたもの以外で指摘を追加することは禁止。

### 2.2 — トリアージ&見積（triage スキル）

オーケストレーター（あなた自身）が `/creview:triage` の「トリアージリーダー」役を直接担う。手順・テンプレートは `${CLAUDE_PLUGIN_ROOT}/skills/triage/SKILL.md` に従う。

入力ドキュメント: {今ラウンドのファイルパス}

- ステップ 1〜3 — triage § の指示に従いサブエージェントへ委譲する。triage スキルはそのステップ 3（compile）で `triage` / `estimate` をドキュメントに永続化する。

ラウンド固有のオーバーライド（テンプレートの指示に従った後に適用）:

- コンソール出力: トリアージ開始時 `## Round {N} — Step 2: Triage`、見積開始時 `## Round {N} — Step 2.5: Estimate`。
- トリアージサブエージェント: 過去ラウンド全件の doc_path 一覧を `previous_round_doc_paths` 変数として渡す（Round 1: `(なし)`、Round N: Round 1〜N-1 の doc_path）。判定挙動は `${CLAUDE_PLUGIN_ROOT}/skills/triage/templates/triage.md` の Won't Fix ガイドラインを参照。トリアージ報告に Will Fix 件数を明記する（0 件の場合も明示）。
- 見積サブエージェント: 前ラウンドのレビュードキュメントは参照しない（バイアス回避）。拡散シグナル e（FIXME 起源の Will Fix）を判定する際、当該指摘がレビュー本文や対象ファイル中の `FIXME:` / `TODO:` を起点としているかを確認する。
- トリアージ後のラウンドループ制御: Will Fix == 0 → triage compile を実行し（Won't Fix を永続化）、2.3 をスキップして 2.4 に進む。
- 見積後のラウンドループ制御: Maintain も Alternative も 0 件（全件 Downgrade）の場合、triage compile を実行し、2.3 をスキップして 2.4 に進む。
- `--confirm`: triage compile 完了後、Maintain / Alternative が 1 件以上ある場合、見積集約 Sub の `summary_path` を Read してユーザーに提示し、2.3 の前に確認を待つ。

### 2.3 — レビュー対応 / 修正（respond スキル）

オーケストレーター（あなた自身）が `/creview:respond` の「レビュー対応リーダー」役を直接担う。手順・テンプレートは `${CLAUDE_PLUGIN_ROOT}/skills/respond/SKILL.md` に従う。ラウンドオプションが有効な場合は `--commit` をそのまま渡す。

入力ドキュメント: {今ラウンドのファイルパス}（トリアージ / 見積は 2.2 で永続化済み）

- コンソール出力: 修正開始時 `## Round {N} — Step 3: Respond (Fix & Verify)`。
- ステップ 1〜5 — respond § の指示に従いサブエージェントへ委譲する。並列化とフォーマット&ビルド検証 ⇄ ビルド修正の再実行ループは同 SKILL に従いリーダーがオーケストレーションする。respond compile はそのステップ 5 で `status` をドキュメントに永続化する。
- `fix_count == 0`（Maintain / Alternative の対象なし）の場合、respond スキルの compile は何も反映しない。2.4 に進む。
- respond § ステップ 4 で `workflow_warning`（フォーマット／ビルド手順が解決できず目視チェックのみだった場合の警告。解決できた場合は null）を受け取っていれば、本ラウンドの記録用に保持する。

### 2.4 — レビュー検証（resolve スキル）

オーケストレーター（あなた自身）が `/creview:resolve` の「レビュー検証リーダー」役を直接担う。手順・テンプレートは `${CLAUDE_PLUGIN_ROOT}/skills/resolve/SKILL.md` に従う。

入力ドキュメント: {今ラウンドのファイルパス}

1. コンソールに表示: `## Round {N} — Step 4: Resolve`
2. resolve § の手順に従い、解析 Sub → 検証 Sub 群（並列）を起動し、リーダーが compile-review.py を実行する（resolve § ステップ 3）。
3. オーケストレーターは戻り値（`{summary_path, summary_line, resolved_count, feedback_count, unresolved_count}`）のみ context に保持する。検証本文は読み込まない。

### 2.5 — フィードバック確認と再修正ループ

ステップ 2.4 の戻り値（`feedback_count`）から「フィードバック必要」な指摘の有無を判定する。レビュードキュメント本文を直接 Read しない。

- `feedback_count == 0`: ラウンド終了（2.6 へ）。
- `feedback_count > 0`: 再修正ループに入る（最大 3 回）。

再修正ループ（最大 3 回）— 各 attempt は triage スキルフロー、次に respond スキルフロー、次に resolve スキルフローを再実行する。各サブエージェントの起動プロンプトの「ラウンド固有オーバーライド」セクションに「Feedback 指摘優先」の制約を追加する。

1. `## Round {N} — Step 5.1: Feedback Triage (attempt {M}/3)` を表示。triage スキル（2.2）を再実行。トリアージ起動プロンプトのオーバーライドに追加: `stage が "feedback" の指摘を優先的にトリアージする（current_meta.verification に Feedback 詳細あり）。` 見積起動プロンプトのオーバーライドに追加: `current_meta.verification の Feedback 内容を踏まえて見積。コストが膨らむ場合は Downgrade を検討。` 全件 Downgrade なら triage compile を実行し手順 2 をスキップして手順 3 へ。
2. `## Round {N} — Step 5.2: Feedback Fix (attempt {M}/3)` を表示。respond スキル（2.3）を再実行。修正起動プロンプトのオーバーライドに追加: `current_meta.verification の Feedback 内容を踏まえて再修正。`
   再実行した respond § ステップ 4 で非 null の `workflow_warning` を受け取った場合は、本ラウンドの記録値を更新する（後勝ち）。
3. `## Round {N} — Step 5.3: Feedback Verify (attempt {M}/3)` を表示。resolve スキル（2.4）を再実行。
4. フィードバックが残っていれば手順 1 に戻る。3 回で解消しない場合はラウンドを終了する（残った 💬 Feedback は 2.6 で「未解決」としてカウント）。
5. `--confirm-round` が有効で未解決が残っている場合、次ラウンドに進む前にユーザーの確認を待つ。

### 2.6 — ラウンド終了

ラウンドの結果を記録する。各カウンタはサブエージェント戻り値から取得する（レビュードキュメント本文を Read してカウントしてはならない）:

- 要対応の指摘数: トリアージ Sub の `will_fix_count`
- Maintain / Alternative / Downgrade 数: 見積集約 Sub の `maintain_count` / `alternative_count` / `downgrade_count`
- 修正数: respond の compile-review.py の `fixed_count`（Maintain 通常修正 + Alternative FIXME 付与の合計）
- 未解決数: ステップ 2.5 最終試行後の resolve の compile-review.py の `feedback_count`
- 解決数: resolve の compile-review.py の `resolved_count`
- workflow_warning: 2.3 / 2.5 で保持した `workflow_warning`（フォーマット／ビルド手順未解決のラウンドのみ。それ以外は null）

次のラウンドに進む条件: 以下の**すべて**を満たす場合に限り、ラウンドカウンターをインクリメントしてステップ 2.1 へ戻る:

1. ラウンドカウンターが `--max-rounds` 以下である。
2. 今ラウンドでソースコードが 1 行でも変更されている。

満たさない場合は最終レポート生成へ進む。

## ステップ 3 — 最終レポート（最終レポート編纂サブエージェントへ委譲）

最終レポートのパス: `{base-path}/{branch-dir}/final-report.md`

1. `Agent(subagent_type="review-helper", prompt=...)` でサブエージェントを起動する。タスク固有の指示は `templates/final-report-compile.md` 外部テンプレートに格納されている。起動プロンプト例:

```
最初の行動として `${CLAUDE_PLUGIN_ROOT}/skills/rounds/templates/final-report-compile.md` を必ず Read する。Read 完了前に他の判断・行動・ツール呼び出しを行わない。Read 後はその指示に従う。

変数（テンプレート中の {{...}} placeholder を置換）:
- plugin_root: ${CLAUDE_PLUGIN_ROOT}
- round_doc_paths: Round 1 → {round1_doc_path}, Round 2 → {round2_doc_path}, ...
- round_stats: Round 1: findings=N, will_fix=N, maintain=N, alternative=N, downgrade=N, fixed=N, wontfix=N, feedback_attempts=N, unresolved=N, code_changed=<bool>, ...（workflow_warning が非 null のラウンドは末尾に workflow_warning="..." を付す）
- template_path: {template_path}
- report_path: {report_path}
- language: ユーザーのチャット言語

ラウンド固有のオーバーライド（テンプレートの指示に従った後に適用）:
- (該当なし)

戻り値に template_id（テンプレートの frontmatter から Read）を含める。
```

2. オーケストレーターは戻り値（`{report_path, template_id}`）を受け取る。`template_id` が `4f8a2d1c-9b35-4e67-a2c1-8b5d3f9e7a16` と一致することを確認する。一致しない場合はサブエージェントを再起動する。`report_path` のみを context に保持する。

### 最終レポート形式

テンプレート: `${CLAUDE_PLUGIN_ROOT}/skills/rounds/templates/final-report.md`（最終レポート編纂 Sub が Read して骨組みを把握する。リーダーは Sub プロンプトの `{template_path}` にこのパスを埋める）。

## ステップ 4 — 完了報告

最終レポートのパスをユーザーに報告し、主要な統計（総指摘数、解決数、未解決数）を簡潔に伝える。
