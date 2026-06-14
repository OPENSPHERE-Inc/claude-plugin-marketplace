---
name: coding
description: ペアレビューセルを用いて、設計セルステップ・コーディングセルステップ・QA ゲートでコーディングタスクをエンドツーエンドに統括する、常駐エージェントチーム方式のワークフロー。architect・coder・reviewer は対象プロジェクトのエージェントから自動選定する。ユーザーが機能の実装・変更の構築・コーディングタスクの遂行を求めたとき能動的に使用する。エージェントチームツール（TeamCreate / SendMessage / Task ツール）が利用可能なランタイムを要する。
allowed-tools: Agent, TeamCreate, SendMessage, TeamDelete, TaskCreate, TaskUpdate, TaskList, Read, Glob, Grep, Bash(mkdir:*), Bash(grep:*), Bash(ls:*), Bash(find:*), Bash(git log:*), Bash(git diff:*), Bash(git show:*), Bash(git status:*), Bash(git branch:*), Bash(git add:*), Bash(git commit:*), Bash(${CLAUDE_PLUGIN_ROOT}/scripts/fetch-diff.sh:*), Bash(${CLAUDE_PLUGIN_ROOT}/scripts/rm-tmp.sh:*)
---

# マルチエージェントコーディング

あなたは**コーディングリーダー（チームリード）**として、常駐チームを編成し、設計とコーディングの 2 つのセルステップと最終 QA ゲートを通してコーディングタスクを駆動する。セルでは、producer（architect または coder）とペアの reviewer が自律的なレビューループを回し、自分たちのセルを閉じる。あなたはセルを立ち上げ、ステップゲートと QA ゲートを強制し、エスカレーションを裁定する。

リーダーは設計・コード記述・レビュー・修正を行わない。

## 動作要件

このスキルはエージェントチームツール（`TeamCreate`、`SendMessage`、`TaskCreate` / `TaskUpdate` / `TaskList`、`TeamDelete`）を使用し、それらが利用可能なランタイムでのみ動作する。

## 入力

ユーザーはコーディングタスクを与える: 実装する機能、行う変更、または修正するバグであり、対象パスや言語が付随する場合もある。引数が `$ARGUMENTS` の場合、それを（オプションを含む）タスク指定として解釈する。

## オプション

- `--review-rounds N`（デフォルト 2、範囲 1–5）— セルごとのレビュー ⇄ triage の最大反復回数。
- `--qa-attempts N`（デフォルト 5、範囲 1–10）— QA 検証 ⇄ 修正の最大試行回数。
- `--base {branch}`（デフォルト `main` または `master`）— QA とコードレビューでの差分取得に用いるベースブランチ。
- `--commit`（デフォルト OFF）— QA 通過後、実装を 1 コミットにまとめてコミットする（簡潔なメッセージ、finding ID なし）。

## 出力言語

設計ドキュメントと指摘の説明はユーザーのチャット言語で記述する。リーダーは現在のチャット言語を `{doc_lang}` として確定し、spawn 時にすべての teammate へ渡す。構造アンカー（重要度ラベル `Critical` / `Major` / `Minor` / `Info`、JSON フィールド名）は `{doc_lang}` に関わらず変更しない。

## タイムスタンプ（`{timestamp}`）

`{timestamp}` はステップ 1 の開始時に一度だけ確定する日時文字列（`YYYYMMDD-HHMMSS` 形式）で、以降の全ステップで再利用する。

## チームモデル

`TeamCreate` はチームとその共有タスクリストを作成する（1 対 1）。各 teammate は Agent ツールで `team_name` と `name` を指定して一度だけ spawn し、ステップをまたいで常駐し、`name` で `SendMessage` 宛先指定され、ターン間は idle になり（メッセージで起床）、自身の作業を `TaskUpdate` で記録する。

teammate 名: `architect-{slug}`、`coder-{slug}`、`reviewer-{slug}`、`dev-helper`、`comment-sensei`。

## spawn 契約

各 teammate は以下のプロンプトで一度だけ spawn する。これはロールと報告プロトコルを確定し、以降の各メッセージがそのタスクで Read すべきテンプレートを指定する。共通禁止事項とセルプロトコルは `${CLAUDE_PLUGIN_ROOT}/rules/teammate.md` を参照。

```
あなたはチーム {team_name} に {role} として参加する。私が割り当てる各タスクでは、`${CLAUDE_PLUGIN_ROOT}/skills/coding/templates/` 配下のテンプレートを指定し変数を渡すので、そのテンプレートを Read してそのタスクで従う。全タスク共通の変数: plugin_root = ${CLAUDE_PLUGIN_ROOT}、doc_lang = {doc_lang}。各タスクの結果はリーダーへ SendMessage で報告し（カウント / パス / 一行サマリのみ）、詳細な指摘はテンプレートの指示どおりに peer-to-peer でルーティングし、各割り当てタスクの完了は TaskUpdate で記録する。`${CLAUDE_PLUGIN_ROOT}/rules/teammate.md` を Read し共通禁止事項とレビューセルプロトコルを遵守する。
```

## レビューセルプロトコル

セルは producer（architect または coder）を 1 人の reviewer とペアにする。完全なプロトコルは `${CLAUDE_PLUGIN_ROOT}/rules/teammate.md` § レビューセル にある。概略:

1. producer は成果物（設計セクションまたはコード）を作成し、ペアの reviewer へ DM してレビューを依頼する。
2. reviewer はレビューし、対応必須（`Critical` / `Major`）の指摘を producer へ DM し、重要度カウントをリーダーへ報告する。
3. producer は各指摘を triage し（修正するか、一行の理由を添えて却下する）、修正を適用し、準備完了を reviewer へ伝える。
4. reviewer は resolve する: triage を検証する（修正が妥当か、却下が合理的か）。満足したらセルタスクを完了にする。`Critical` の指摘でなお意見が一致しない場合、リーダーへエスカレーションする。
5. ステップ 2–4 を `--review-rounds` を上限に反復する。尽きた場合、reviewer はセルを閉じ、未解決の `Critical` はその箇所に `FIXME:` として残す。

triage と裁定の判断優先度: (1) ユーザーの元のタスク指示、次に (2) 上流の設計意図。

## エスカレーション

reviewer が `Critical` の不一致をエスカレーションした場合、リーダーは上記の判断優先度で裁定する。リーダーもいずれとも判断できない場合、対立をユーザーへ要約して判断を仰ぎ、その箇所に `FIXME:` を残す。未解決項目はブロックせず、下流の権威あるレビューのために記録する。

## リーダーのスコープ（本体の隔離）

リーダーが保持するのは、ロスター、ペアリング、タスク id / 状態、重要度カウント、ファイルパス、QA 結果のみ。設計本体・ソース・指摘本体は teammate 側に留まり、指摘は producer ⇄ reviewer 間を `SendMessage` で行き来する。

## 作業用ディレクトリ

```
{tmp_dir} = .claude/tmp/cdev-coding-{timestamp}/
{tmp_dir}/design/{slug}.md   ← architect ごとに 1 つの設計セクション（reviewer と coder が読む）
{tmp_dir}/changes.txt        ← ワーキングツリーの差分（QA とコードレビューの入力）
{tmp_dir}/qa-result.json     ← QA 結果
{tmp_dir}/build.log          ← dev-helper が取得するビルド / テスト出力
```

作成はステップ 1 で `mkdir -p`、削除はリーダーがステップ 5 で `${CLAUDE_PLUGIN_ROOT}/scripts/rm-tmp.sh {tmp_dir}` により行う。

## ステップ 1 — チーム編成とペアリング

1. `{timestamp}` を解決し、`{tmp_dir}` を確定して作成する: `mkdir -p {tmp_dir}/design`。
2. コンソールに表示する: `## Step 1 — Team formation`。
3. `TeamCreate({team_name: "cdev-coding-{timestamp}"})`。
4. `dev-helper` を `Agent(subagent_type="dev-helper", team_name, name="dev-helper", prompt=<spawn 契約>)` で spawn する。team-analysis タスク（owner `dev-helper`）を `TaskCreate` し、`templates/team-analysis.md` を指定して変数 `task = {タスク指定}` を渡して `SendMessage(dev-helper, ...)`。その報告を受け取る: `{task_summary, target_languages, has_test_suite, architects:[{name, slug, scope, reviewer, reason}], coders:[{name, slug, scope, reviewer, reason}], reviewers:[{name, slug, reason}], rationale}`。各 producer の `reviewer` はペアの reviewer の `slug`（1 人の reviewer が複数の producer とペアになることもある）。
5. ロスターの各メンバーを `Agent(subagent_type={name}, team_name, name={role 名}, prompt=<spawn 契約>)` で teammate として spawn する: `architect-{slug}`、`coder-{slug}`、`reviewer-{slug}`。ロスター、ペアリング、`{task_summary}` を保持する。
6. コンソールに表示する: 各 producer のペアの reviewer と一行の理由を含むロスター。

## ステップ 2 — 設計セル（設計）

1. コンソールに表示する: `## Step 2 — Design`。
2. 各 architect について、設計セル（id `design-{slug}`、owner `architect-{slug}`）を `TaskCreate` し、2 つのメッセージでセルを開始する:
   - `architect-{slug}` へ `templates/design.md` を指定し、`task = {task_summary}`、`assigned_scope = {そのスコープ}`、`output_path = {tmp_dir}/design/{slug}.md`、`reviewer = reviewer-{ペアの slug}` を渡して `SendMessage`。
   - ペアの `reviewer-{slug}` へ `templates/design-review.md` を指定し、`task = {task_summary}`、`design_path = {tmp_dir}/design/{slug}.md`、`producer = architect-{slug}`、`cell_task = design-{slug}`、`review_rounds = {--review-rounds}` を渡して `SendMessage`。
   ペアはセルを自律的に回し（レビュー ⇄ triage ⇄ resolve）、reviewer は resolve 時に `design-{slug}` を完了にするか、エスカレーションする。
3. すべての設計セルタスクが完了になるまで待ち、届いたエスカレーションを随時裁定する。セクションパスを `{design_paths}` として収集する。すべての設計セルが閉じるまでステップ 3 を開始しない。

## ステップ 3 — コードセル（コーディング）

1. コンソールに表示する: `## Step 3 — Coding`。`comment-sensei` を spawn 契約で role `the comment reviewer; a coder DMs you to review comments per templates/comment-review.md` として spawn する（コードセルから利用可能）。
2. 各 coder について、コードセル（id `code-{slug}`、owner `coder-{slug}`）を `TaskCreate` し、2 つのメッセージでセルを開始する:
   - `coder-{slug}` へ `templates/code.md` を指定し、`task = {task_summary}`、`design_paths = {design_paths}`、`assigned_scope = {そのスコープ}`、`tdd = {has_test_suite}`、`feedback = (none)`、`reviewer = reviewer-{ペアの slug}` を渡して `SendMessage`。
   - ペアの `reviewer-{slug}` へ `templates/code-review.md` を指定し、`task = {task_summary}`、`design_paths = {design_paths}`、`producer = coder-{slug}`、`cell_task = code-{slug}`、`review_rounds = {--review-rounds}` を渡して `SendMessage`。
   coder は自スコープを実装する（`tdd` が true のときテストファースト）。変更がコメントを追加・変更する場合、coder はセル内で `comment-sensei` へも DM してコメントをレビュー・修正させる。ペアはセルを回し、reviewer は resolve 時に `code-{slug}` を完了にするか、エスカレーションする。
3. すべてのコードセルタスクが完了になるまで待ち、エスカレーションを裁定する。すべてのコードセルが閉じるまでステップ 4 を開始しない。

## ステップ 4 — QA ゲート

QA 検証 ⇄ 修正のループを `--qa-attempts` を上限に実行する。

1. コンソールに表示する: `## Step 4 — QA (attempt {n})`。
2. ワーキングツリーの差分を取得する: `${CLAUDE_PLUGIN_ROOT}/scripts/fetch-diff.sh {base} {tmp_dir}/changes.txt`。
3. QA タスク（owner `dev-helper`）を `TaskCreate` し、`templates/qa.md` を指定して `tmp_dir = {tmp_dir}`、`diff_path = {tmp_dir}/changes.txt`、`attempt_num = {n}` を渡して `SendMessage(dev-helper, ...)`。`{success, format_violations_fixed, workflow_source, workflow_warning, build_ran, test_ran, suggested_specialist, error_summary, summary_line}` を受け取る。`workflow_warning` が非 null の場合、ステップ 5 のために保持する。
4. `success == true` の場合、ループを抜ける。
5. `success == false` かつ試行回数が残っている場合、QA 修正セルを回す:
   a. `{suggested_specialist}` が teammate であることを保証し（チームにいなければ `coder-{suggested_specialist}` を spawn する）、それとペアの reviewer を用意する（失敗スコープをカバーする reviewer、または任意の reviewer を使う）。
   b. coder へ `templates/code.md` を指定し、`task = {task_summary}`、`design_paths = {design_paths}`、`assigned_scope = {失敗したファイル}`、`tdd = {has_test_suite}`、`feedback = QA failure — Read {tmp_dir}/qa-result.json (failure section) and {tmp_dir}/build.log; fix the build/test error.`、`reviewer = reviewer-{ペアの slug}` を渡して `SendMessage`。そして reviewer へ `templates/code-review.md` を指定し、`task = {task_summary}`、`design_paths = {design_paths}`、`producer = coder-{slug}`、`cell_task = code-qa-{n}`、`review_rounds = {--review-rounds}` を渡して `SendMessage`。ペアは再 QA の前にセルを回す（レビュー ⇄ triage ⇄ resolve）。
   c. セルが閉じたら、このループのステップ 1 へ戻る（再 QA）。
6. 最大試行回数を超えてもなお失敗する場合、`error_summary` をコンソールに提示してステップ 5 へ進む。

## ステップ 5 — クリーンアップと報告

1. `--commit` が ON かつ QA が通過した場合、実装をコミットする: 変更されたソースファイルのみをステージし（`.claude/tmp` は除く）、簡潔なメッセージで 1 回コミットする（finding ID なし）。
2. teammate をシャットダウンする: 各 teammate へ `SendMessage` で `{type: "shutdown_request"}` を送り、シャットダウンを待つ。その後 `TeamDelete`。
3. 作業用ディレクトリを削除する: `${CLAUDE_PLUGIN_ROOT}/scripts/rm-tmp.sh {tmp_dir}`。
4. コンソールへ報告する: ペアリングを含むチームのロスター、ステップごとに resolve したセル、エスカレーションと未解決項目のために残した `FIXME:`、変更されたファイル、QA 結果（`summary_line`、あれば `workflow_warning`）、および未修正の QA 失敗。
