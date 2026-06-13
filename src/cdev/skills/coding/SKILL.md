---
name: coding
description: 設計・設計レビュー・コーディング・QA・コードレビューを、対象プロジェクトのエージェントから自動選定したアーキテクト・コーダー・レビュアーの常駐チームで統括する、チームネイティブのコーディングワークフロー。ユーザーが機能の実装・変更の構築・コーディングタスクの遂行を求めたとき能動的に使用する。エージェントチームツール（TeamCreate / SendMessage / Task ツール）が利用可能なランタイムを要する。
allowed-tools: Agent, TeamCreate, SendMessage, TeamDelete, TaskCreate, TaskUpdate, TaskList, Read, Glob, Grep, Bash(mkdir:*), Bash(grep:*), Bash(ls:*), Bash(find:*), Bash(git log:*), Bash(git diff:*), Bash(git show:*), Bash(git status:*), Bash(git branch:*), Bash(git add:*), Bash(git commit:*), Bash(${CLAUDE_PLUGIN_ROOT}/scripts/fetch-diff.sh:*), Bash(${CLAUDE_PLUGIN_ROOT}/scripts/rm-tmp.sh:*)
---

# マルチエージェントコーディング

あなたは**コーディングリーダー（チームリード）**として、専門 teammate の常駐チームを編成し、設計・設計レビュー・コーディング・QA・コードレビューの 5 フェーズにわたって駆動し、フェーズとフィードバックループを順序立てる。

リーダーは設計・コード記述・レビュー・修正を行わない。リーダーはチームを編成し、タスクを作成・割り当て、フェーズを順序立て、進捗を報告する。専門家は、フェーズをまたいで文脈を保持し互いにフィードバックを直接ルーティングする常駐 teammate である。

## 動作要件

このスキルはエージェントチームツール（`TeamCreate`、`SendMessage`、`TaskCreate` / `TaskUpdate` / `TaskList`、`TeamDelete`）を使用し、それらが利用可能なランタイムでのみ動作する。

## 入力

ユーザーはコーディングタスクを与える: 実装する機能、行う変更、または修正するバグであり、対象パスや言語が付随する場合もある。引数が `$ARGUMENTS` の場合、それを（オプションを含む）タスク指定として解釈する。

## オプション

- `--design-rounds N`（デフォルト 2、範囲 1–5）— 設計レビュー ⇄ 設計改訂の最大反復回数。
- `--review-rounds N`（デフォルト 2、範囲 1–5）— コードレビュー ⇄ コード修正の最大反復回数。
- `--qa-attempts N`（デフォルト 5、範囲 1–10）— QA 実行 1 回あたりの QA 検証 ⇄ コーダー修正の最大試行回数。
- `--base {branch}`（デフォルト `main` または `master`）— QA とコードレビューでの差分取得に用いるベースブランチ。
- `--commit`（デフォルト OFF）— QA とコードレビューを通過した後、実装を 1 コミットにまとめてコミットする（簡潔なメッセージ、finding ID なし）。

## 出力言語

設計ドキュメントと指摘の説明はユーザーのチャット言語で記述する。リーダーは現在のチャット言語を `{doc_lang}`（例: `日本語`、`English`）として確定し、spawn 時にすべての teammate へ渡す。構造アンカー（重要度ラベル `Critical` / `Major` / `Minor` / `Info`、JSON フィールド名）は `{doc_lang}` に関わらず変更しない。

## タイムスタンプ（`{timestamp}`）

`{timestamp}` はステップ 1 の開始時に一度だけ確定する日時文字列（`YYYYMMDD-HHMMSS` 形式）で、以降の全ステップで再利用する。

## チームモデル

`TeamCreate` はチームとその共有タスクリストを作成する（チームとタスクリストは 1 対 1）。各 teammate は Agent ツールで `team_name` と `name` を指定して一度だけ spawn し、フェーズをまたいで常駐し、`name` で `SendMessage` 宛先指定され、ターン間は idle になり（メッセージで起床）、自身の作業を `TaskUpdate` で記録する。

teammate 名:
- `architect-{slug}` — アーキテクトごとに 1 つ
- `coder-{slug}` — コーダーごとに 1 つ（`{slug}` はそのスコープ由来）
- `reviewer-{n}` — レビュアーごとに 1 つ
- `dev-helper` — チーム編成と QA（同梱エージェント）
- `comment-sensei` — コメントレビュー（同梱エージェント。コメントが存在する場合にステップ 6 で spawn）

## spawn 契約

各 teammate は以下のプロンプトで一度だけ spawn する。これはロールと報告プロトコルを確定し、以降の各タスクメッセージがそのタスクで Read すべきテンプレートを指定する。共通禁止事項は `${CLAUDE_PLUGIN_ROOT}/rules/teammate.md` を参照。

```
あなたはチーム {team_name} に {role} として参加する。私が割り当てる各タスクでは、`${CLAUDE_PLUGIN_ROOT}/skills/coding/templates/` 配下のテンプレートを指定し変数を渡すので、そのテンプレートを Read してそのタスクで従う。全タスク共通の変数: plugin_root = ${CLAUDE_PLUGIN_ROOT}、doc_lang = {doc_lang}。各タスクの結果はリーダーへ SendMessage で報告し（カウント / パス / 一行サマリのみ）、詳細な指摘はテンプレートの指示どおりにルーティングし、各タスクの完了は TaskUpdate で記録する。`${CLAUDE_PLUGIN_ROOT}/rules/teammate.md` を Read し共通禁止事項を遵守する。
```

タスクメッセージとルーティングの規約は `${CLAUDE_PLUGIN_ROOT}/rules/teammate.md` § チーム規約を参照。

## リーダーのスコープ（本体の隔離）

リーダーが保持するのは、ロスター、タスク id / 状態、重要度カウント、ファイルパス、QA 結果のみ。設計本体・ソース・指摘本体は teammate 側に留まる。レビュアーは詳細な指摘を所有する `architect` / `coder` へ `SendMessage` で直接ルーティングし、リーダーへは重要度カウントのみを報告する。

## 作業用ディレクトリ

```
{tmp_dir} = .claude/tmp/cdev-coding-{timestamp}/
{tmp_dir}/design/{slug}.md   ← アーキテクトごとに 1 つの設計セクション（レビュアーとコーダーが読む）
{tmp_dir}/changes.txt        ← ワーキングツリーの差分（QA とコードレビューの入力）
{tmp_dir}/qa-result.json     ← QA 結果
{tmp_dir}/build.log          ← dev-helper が取得するビルド / テスト出力
```

作成はステップ 1 で `mkdir -p`、削除はリーダーがステップ 7 で `${CLAUDE_PLUGIN_ROOT}/scripts/rm-tmp.sh {tmp_dir}` により行う。

## 対応必須の指摘

レビュアーは重要度カウントをリーダーへ報告する。指摘は重要度が `Critical` または `Major` のとき**対応必須**である。リーダーは `critical + major > 0` かつ反復回数が残っている間のみフィードバックループを継続する。`Minor` / `Info` は参考である。

## ステップ 1 — チーム編成

1. `{timestamp}` を解決し、`{tmp_dir}` を確定して作成する: `mkdir -p {tmp_dir}/design`。
2. コンソールに表示する: `## Phase 0 — Team formation`。
3. `TeamCreate({team_name: "cdev-coding-{timestamp}"})`。
4. `dev-helper` を `Agent(subagent_type="dev-helper", team_name, name="dev-helper", prompt=<spawn 契約、role="チーム編成と QA のヘルパー">)` で spawn する。
5. team-analysis タスク（owner `dev-helper`）を `TaskCreate` し、`templates/team-analysis.md` を指定して変数 `task = {タスク指定}` を渡して `SendMessage(dev-helper, ...)`。その報告を受け取る: `{task_summary, target_languages, has_test_suite, architects:[{name, slug, scope, reason}], coders:[{name, slug, scope, reason}], reviewers:[{name, reason}], rationale}`。
6. ロスターの各メンバーを `Agent(subagent_type={name}, team_name, name={role 名}, prompt=<spawn 契約>)` で teammate として spawn する: `architect-{slug}`、`coder-{slug}`、`reviewer-{n}`。スコープマップ（どの `coder-{slug}` / `architect-{slug}` がどのファイルを所有するか）を保持する。
7. コンソールに表示する: ロスターと一行の理由。ロスターと `{task_summary}` を context に保持する。

## ステップ 2 — 設計

1. コンソールに表示する: `## Phase 1 — Design`。
2. 各アーキテクトについて、設計タスク（owner `architect-{slug}`）を `TaskCreate` し、`templates/design.md` を指定して変数 `task = {task_summary}`、`assigned_scope = {そのスコープ}`、`output_path = {tmp_dir}/design/{slug}.md` を渡して `SendMessage` する。
3. 各アーキテクトは自セクションを書き、タスクを完了にし、`{path, summary}` を報告する。各セクションパスを `{design_paths}` として収集する。

## ステップ 3 — 設計レビュー

`--design-rounds` を上限に反復する。

1. コンソールに表示する: `## Phase 2 — Design Review (iteration {i})`。
2. 各レビュアーについて、レビュータスク（owner `reviewer-{n}`）を `TaskCreate` し、`templates/design-review.md` を指定して変数 `task = {task_summary}`、`design_paths = {design_paths}`、`scope_map = {アーキテクト → スコープ}` を渡して `SendMessage` する。レビュアーは対応必須の指摘を所有する `architect-{slug}` へ `SendMessage` し、`{critical, major, minor, info}` をリーダーへ報告し、タスクを完了にする。
3. レビュアー横断で `critical + major` を合計する。
4. 合計が 0、または今回が許容された最後の反復だった場合、ループを抜ける（設計確定）。
5. それ以外の場合、指摘を受け取った各アーキテクトへ `templates/design.md` を同じ変数で指定して `SendMessage` し、レビュアーが DM した対応必須の指摘を解消すべく自セクションを改訂させる（アーキテクトは設計の文脈を保持している）。アーキテクトが改訂を完了にしたら、このループのステップ 2 へ戻る。

## ステップ 4 — コーディング

1. コンソールに表示する: `## Phase 3 — Coding`。
2. 各コーダーについて、コーディングタスク（owner `coder-{slug}`）を `TaskCreate` し、`templates/code.md` を指定して変数 `task = {task_summary}`、`design_paths = {design_paths}`、`assigned_scope = {そのスコープ}`、`tdd = {has_test_suite}`、`feedback = (none)` を渡して `SendMessage` する。コーダーは互いに重ならないファイルスコープを所有する。
3. 各コーダーは自スコープを実装し、タスクを完了にし、`{files_changed, has_comments, summary}` を報告する。いずれかのコーダーが `has_comments == true` を報告した場合、`{comments_present}` を true に設定する。

## ステップ 5 — QA

QA 検証 ⇄ コーダー修正のループを `--qa-attempts` を上限に実行する。

1. コンソールに表示する: `## Phase 4 — QA (attempt {n})`。
2. ワーキングツリーの差分を取得する: `${CLAUDE_PLUGIN_ROOT}/scripts/fetch-diff.sh {base} {tmp_dir}/changes.txt`。
3. QA タスク（owner `dev-helper`）を `TaskCreate` し、`templates/qa.md` を指定して変数 `tmp_dir = {tmp_dir}`、`diff_path = {tmp_dir}/changes.txt`、`attempt_num = {n}` を渡して `SendMessage(dev-helper, ...)`。`{success, format_violations_fixed, workflow_source, workflow_warning, build_ran, test_ran, suggested_specialist, error_summary, summary_line}` を受け取る。`workflow_warning` が非 null の場合、ステップ 7 のために保持する。
4. `success == true` の場合、ループを抜ける。
5. `success == false` かつ試行回数が残っている場合: `{suggested_specialist}` が teammate であることを保証し（まだチームにいなければ `coder-{suggested_specialist}` を spawn する）、`templates/code.md` を指定して `feedback = QA 失敗 — {tmp_dir}/qa-result.json（failure セクション）と {tmp_dir}/build.log を Read し、ビルド / テストエラーを修正する。`、`assigned_scope = {失敗したファイル}`、`tdd = {has_test_suite}` を渡して `SendMessage` する。修正が完了にされたら、このループのステップ 1 へ戻る。
6. 最大試行回数を超えてもなお失敗する場合、`error_summary` をコンソールに提示してステップ 6 へ進む。

## ステップ 6 — コードレビュー

`--review-rounds` を上限に反復する。

1. コンソールに表示する: `## Phase 5 — Code Review (iteration {i})`。
2. 現在の差分を取得する: `${CLAUDE_PLUGIN_ROOT}/scripts/fetch-diff.sh {base} {tmp_dir}/changes.txt`。
3. 各レビュアーについて、レビュータスクを `TaskCreate` し、`templates/code-review.md` を指定して変数 `task = {task_summary}`、`diff_path = {tmp_dir}/changes.txt`、`design_paths = {design_paths}`、`scope_map = {コーダー → スコープ}` を渡して `SendMessage` する。レビュアーは対応必須の指摘を所有する `coder-{slug}` へ `SendMessage` し、`{critical, major, minor, info}` をリーダーへ報告し、タスクを完了にする。
4. `{comments_present}` が true の場合、`comment-sensei` teammate の存在を保証し（いなければ spawn）、`templates/comment-review.md` を指定して変数 `diff_path = {tmp_dir}/changes.txt`、`design_paths = {design_paths}` を渡して `SendMessage` する。comment-sensei はコメント違反を直接修正し、`{reviewed_paths, fix_count}` を報告する。
5. レビュアー横断で `critical + major` を合計する。
6. 合計が 0、または今回が許容された最後の反復だった場合、ループを抜ける。
7. それ以外の場合、指摘を受け取った各コーダーへ `SendMessage` し、自スコープ内でそれらを修正させる。コーダーが修正を完了にしたら、いずれかが `has_comments == true` を報告した場合は `{comments_present}` を true に設定し（すでに true ならそのまま）、ビルド / テストをグリーンに保つためステップ 5（QA）を 1 回再実行し、その後このループのステップ 3 へ戻る。

## ステップ 7 — クリーンアップと報告

1. `--commit` が ON かつ QA が通過した場合、実装をコミットする: 変更されたソースファイルのみをステージし（`.claude/tmp` は除く）、変更を説明する簡潔なメッセージで 1 回コミットする（finding ID なし）。
2. teammate をシャットダウンする: 各 teammate へ `SendMessage` で `{type: "shutdown_request"}` を送り、シャットダウンを待つ。
3. `TeamDelete`。
4. 作業用ディレクトリを削除する: `${CLAUDE_PLUGIN_ROOT}/scripts/rm-tmp.sh {tmp_dir}`。
5. コンソールへ報告する: チームのロスター、実行したフェーズ（反復回数を含む）、変更されたファイル、QA 結果（`summary_line`、あれば `workflow_warning`）、および未解決の対応必須指摘または未修正の QA 失敗。
