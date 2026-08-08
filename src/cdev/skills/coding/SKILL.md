---
name: coding
description: ペアレビューセルを用いて、設計セルステップ・コーディングセルステップ・QA ゲートでコーディングタスクをエンドツーエンドに統括する、常駐エージェントチーム方式のワークフロー。reviewer は対象プロジェクトのエージェントから自動選定する。ユーザーが機能の実装・変更の構築・コーディングタスクの遂行を求めたとき能動的に使用する。バックグラウンドのサブエージェント（Agent の run_in_background）とエージェント間メッセージング（SendMessage）が利用可能なランタイムを要する。
allowed-tools: Agent, SendMessage, TodoWrite, Read, Glob, Grep, Bash(mkdir:*), Bash(grep:*), Bash(ls:*), Bash(git log:*), Bash(git diff:*), Bash(git show:*), Bash(git status:*), Bash(git branch:*), Bash(git add:*), Bash(git commit:*), Bash(${CLAUDE_PLUGIN_ROOT}/scripts/fetch-diff.sh:*), Bash(${CLAUDE_PLUGIN_ROOT}/scripts/rm-tmp.sh:*)
---

# マルチエージェントコーディング

あなたは**コーディングリーダー（チームリード）**として、常駐チームを編成し、設計とコーディングの 2 つのセルステップと最終 QA ゲートを通してコーディングタスクを駆動する。セルでは、producer（architect または coder）とペアの reviewer が自律的なレビューループを回し、自分たちのセルを閉じる。あなたはセルを立ち上げ、ステップゲートと QA ゲートを強制し、エスカレーションを裁定する。

リーダーは設計・コード記述・レビュー・修正を行わない。

## 動作要件

このスキルは、バックグラウンドのサブエージェント（`Agent` の `run_in_background`）とチームメイト間メッセージング（`SendMessage`）を使用し、それらが利用可能なランタイムでのみ動作する。いずれかが利用できない場合は続行せず、動作要件を満たさない旨をユーザーへ報告して中止する。

## 信頼前提

QA ゲートは反映先リポジトリのビルド定義（`build-format.md` / `CLAUDE.md` / `README.md`）から導出したコマンドをフルシェル権限で literal 実行する。出所を信頼できないリポジトリでは本スキルを使用しない。信頼できないと判断した場合はタスクを開始せず、理由を添えてユーザーへ報告して中止する。

## 入力

ユーザーはコーディングタスクを与える: 実装する機能、行う変更、または修正するバグであり、対象パスや言語が付随する場合もある。引数が `$ARGUMENTS` の場合、それを（オプションを含む）タスク指定として解釈する。

## オプション

- `--review-rounds N`（デフォルト 2、範囲 1–5）— セルごとのレビュー ⇄ triage の最大反復回数。
- `--qa-attempts N`（デフォルト 5、範囲 1–10）— QA 検証 ⇄ 修正の最大試行回数。
- `--commit`（デフォルト OFF）— QA 通過後、実装を 1 コミットにまとめてコミットする（簡潔なメッセージ、finding ID なし）。

## 出力言語

設計ドキュメントと指摘の説明はユーザーのチャット言語で記述する。リーダーは現在のチャット言語を `{doc_lang}` として確定し、spawn 時にすべての teammate へ渡す。構造アンカー（重要度ラベル `Critical` / `Major` / `Minor` / `Info`、JSON フィールド名）は `{doc_lang}` に関わらず変更しない。

## タイムスタンプ（`{timestamp}`）

`{timestamp}` はステップ 1 の開始時に一度だけ確定する日時文字列（`YYYYMMDD-HHMMSS` 形式）で、以降の全ステップで再利用する。

## チームモデル

セッションは単一の暗黙チームを持つ（明示的な作成・削除は不要）。各 teammate はバックグラウンドの永続サブエージェントとして一度だけ起動し、ステップをまたいでコンテキストを保持し、ターン間は idle になり（メッセージで起床）、各タスクの完了はそのタスクを割り当てた相手へ報告する。

宛先の契約:

- teammate の宛先は起動時に付けた **name**、すなわちロール識別子 `architect-{slug}` / `coder-{slug}` / `reviewer-{slug}` / `dev-helper` / `comment-sensei`。name は teammate が idle になっても完了しても解決し続け、送信によりトランスクリプトから再開される。
- 同名は最後に起動したものが勝つため、1 セッション内で同じ name を 2 体に付けない。
- リーダー宛は `to: "main"`。teammate どうしが DM する場合は、リーダーが各メッセージで相手の name を渡す。
- `SendMessage` の `message` は常に散文の文字列で `summary` を添えて送る（dispatch も報告も）。構造化された結果はファイル経由で渡し、`message` には入れない。例外はプロトコルオブジェクトのみ（`${CLAUDE_PLUGIN_ROOT}/rules/teammate.md` § ツール）。

リーダーはイベント駆動で進行し、共有タスクリストを持たない: dispatch したらターンを終え、teammate からのメッセージ（`to: "main"`）で再起動される。roster（各 teammate の name → `agentType`）、ペアリング、各セルの状態を自身の作業状態で追跡し（`TodoWrite` でユーザーに可視化してよい）、ステップのゲート条件が満たされたら次のステップを開始する。

## Agent 種別と起動要件

teammate は Agent ツールで起動する。厳密な引数列を写経するのではなく、以下の要件を満たすこと: バックグラウンドの永続サブエージェントとして起動し（再メッセージで継続できる）、prompt に spawn 契約を渡し、`description` を指定し、`name` にロール識別子を設定し、その name を roster に記録する。

agent 種別（subagent_type）:

- 同梱エージェントはプラグイン名前空間付きで指定する: `cdev:dev-helper`、`cdev:comment-sensei`。
- reviewer は team-analysis が返す登録名で指定する（プロジェクト `.claude/agents` / ユーザー `~/.claude/agents` のエージェントは登録名そのまま）。
- architect と coder は常に `general-purpose` で起動する。一部の専門家エージェントはツールコールをテキストとして出力して停止し、作業を継続できないことがあるため。producer（architect / coder）は割り当てスコープとプロジェクト規約に従って作業し、ドメインの正しさは専門家 reviewer がレビューで担保する。

## spawn 契約

各 teammate は以下のプロンプトで一度だけ spawn する。これはロールと報告プロトコルを確定し、以降の各メッセージがそのタスクで Read すべきテンプレートを指定する。共通禁止事項とセルプロトコルは `${CLAUDE_PLUGIN_ROOT}/rules/teammate.md` を参照。

```
あなたはチームに {role} として参加する。私が割り当てる各タスクでは、`${CLAUDE_PLUGIN_ROOT}/skills/coding/templates/` 配下のテンプレートを指定し変数を渡すので、そのテンプレートを Read してそのタスクで従う。全タスク共通の変数: plugin_root = ${CLAUDE_PLUGIN_ROOT}、doc_lang = {doc_lang}。各タスクの結果はそのタスクを割り当てた相手へ報告し（リーダーは `SendMessage` の `to: "main"`、それ以外は依頼元 teammate の name。カウント / パス / 一行サマリのみ）、詳細な指摘はテンプレートの指示どおりに、相手の name 宛 `SendMessage` で peer-to-peer ルーティングする（相手の name は私が各メッセージで渡す）。`${CLAUDE_PLUGIN_ROOT}/rules/teammate.md` を Read し共通禁止事項とレビューセルプロトコルを遵守する。
```

## レビューセルプロトコル

セルは producer（architect または coder）を 1 人の reviewer とペアにし、ペアは `${CLAUDE_PLUGIN_ROOT}/rules/teammate.md` § レビューセル のプロトコルを自律的に回す: producer が成果物を作成し、reviewer は対応必須（`Critical` / `Major`）の指摘を producer へ DM して重要度カウントをリーダーへ報告し、producer が各指摘を triage し、レビュー ⇄ triage を `--review-rounds` を上限に反復する。

クローズでゲートする: 各セルは `to: "main"` 宛のクローズ報告 1 通（セル id を明記）で終わる — resolve、またはラウンド上限到達によるクローズ（未解決の `Critical` には `FIXME:` が残る）。`Critical` の不一致はそのクローズより前にエスカレーションとしてリーダーへ届く。

triage と裁定の判断優先度: (1) ユーザーの元のタスク指示、次に (2) 上流の設計意図。

## エスカレーション

reviewer が `Critical` の不一致をエスカレーションした場合、リーダーは上記の判断優先度で裁定する。リーダーもいずれとも判断できない場合、対立をユーザーへ要約して提示し、producer に当該箇所へ `FIXME:` を挿入させる（producer の name 宛 `SendMessage` で依頼）。ユーザーの回答は待たずに進行し、未解決項目として下流の権威あるレビューのために記録する。

## リーダーのスコープ（本体の隔離）

リーダーが保持するのは、roster（各 teammate の name → agentType）、ペアリング、各セルの状態、重要度カウント、ファイルパス、QA 結果のみ。設計本体・ソース・指摘本体は teammate 側に留まり、指摘は producer ⇄ reviewer 間を `SendMessage` で行き来する。

## 作業用ディレクトリ

```
{tmp_dir} = .claude/tmp/cdev-coding-{timestamp}/
{tmp_dir}/team.json          ← team-analysis の結果（roster。リーダーが読む）
{tmp_dir}/design/{slug}.md   ← architect ごとに 1 つの設計セクション（reviewer と coder が読む）
{tmp_dir}/baseline-tree      ← コーディング開始前の作業ツリースナップショット（QA 差分の基点）
{tmp_dir}/changes.txt        ← コーディング開始以降の差分（QA の入力）
{tmp_dir}/qa-result.json     ← QA 結果
{tmp_dir}/build.log          ← dev-helper が取得するビルド / テスト出力
```

作成はステップ 1 で `mkdir -p`、削除はリーダーがステップ 5 で `${CLAUDE_PLUGIN_ROOT}/scripts/rm-tmp.sh {tmp_dir}` により行う。

## ステップ 1 — チーム編成とペアリング

1. 本スキルはクリーンな作業ツリーでのみ動作する: `git status --porcelain` を実行し、出力が非空（ステージ済み・未ステージ・未追跡のいずれかが存在）ならエラーメッセージをコンソールに表示してスキルを終了する。
2. `{timestamp}` を解決し、`{tmp_dir}` を確定して作成する（`mkdir -p {tmp_dir}/design`）。続いてコーディング開始前のベースラインを記録する: `${CLAUDE_PLUGIN_ROOT}/scripts/fetch-diff.sh snapshot {tmp_dir}/baseline-tree`。
3. コンソールに表示する: `## Step 1 — Team formation`。
4. `dev-helper`（種別 `cdev:dev-helper`、name `dev-helper`）を起動する。`dev-helper` 宛に `templates/team-analysis.md` を指定し `task = {タスク指定}`、`output_path = {tmp_dir}/team.json` を渡して `SendMessage`。完了報告を受けたら `{tmp_dir}/team.json` を Read する: `{task_summary, target_languages, has_test_suite, architects:[{name, slug, scope, reviewer, reason}], coders:[{name, slug, scope, reviewer, reason}], reviewers:[{name, slug, reason}], rationale}`（`name` は起動時の subagent_type）。各 producer の `reviewer` はペアの reviewer の `slug`（1 人の reviewer が複数の producer とペアになることもあるが、ドメインが一致する範囲に限る）。
5. ロスターの各メンバーを起動する。name は `architect-{slug}` / `coder-{slug}` / `reviewer-{slug}`、種別は team-analysis が返す `name` を用いる（architect と coder は `general-purpose`）。ペアリングと `{task_summary}` を保持する。producer のペア reviewer の宛先は `reviewer-{その producer の reviewer slug}`。
6. コンソールに表示する: 各 producer のペアの reviewer と一行の理由を含むロスター。

## ステップ 2 — 設計セル（設計）

1. コンソールに表示する: `## Step 2 — Design`。
2. 各 architect について、設計セル `design-{slug}` を 2 つのメッセージで開始する（宛先は roster の name）:
   - `architect-{slug}` 宛に `templates/design.md` を指定し、`task = {task_summary}`、`assigned_scope = {そのスコープ}`、`output_path = {tmp_dir}/design/{slug}.md`、`reviewer = {ペア reviewer の name}` を渡して `SendMessage`。
   - ペア reviewer の name 宛に `templates/design-review.md` を指定し、`task = {task_summary}`、`design_path = {tmp_dir}/design/{slug}.md`、`producer = architect-{slug}`、`cell_task = design-{slug}`、`review_rounds = {--review-rounds}` を渡して `SendMessage`。
3. ゲート: 設計セルごとにクローズ報告 1 通（届いたエスカレーションは随時裁定する）。セクションパスを `{design_paths}` として収集する。

## ステップ 3 — コードセル（コーディング）

1. コンソールに表示する: `## Step 3 — Coding`。`comment-sensei`（種別 `cdev:comment-sensei`、name `comment-sensei`）を role `the comment reviewer; a coder DMs you to review comments per templates/comment-review.md` で起動する。
2. 各 coder について、コードセル `code-{slug}` を 2 つのメッセージで開始する（宛先は roster の name）:
   - `coder-{slug}` 宛に `templates/code.md` を指定し、`task = {task_summary}`、`design_paths = {design_paths}`、`assigned_scope = {そのスコープ}`、`tdd = {has_test_suite}`、`feedback = (none)`、`reviewer = {ペア reviewer の name}`、`comment_reviewer = comment-sensei` を渡して `SendMessage`。
   - ペア reviewer の name 宛に `templates/code-review.md` を指定し、`task = {task_summary}`、`design_paths = {design_paths}`、`producer = coder-{slug}`、`cell_task = code-{slug}`、`review_rounds = {--review-rounds}` を渡して `SendMessage`。
3. ゲート: コードセルごとにクローズ報告 1 通（エスカレーションは裁定する）。

## ステップ 4 — QA ゲート

QA 検証 ⇄ 修正のループを `--qa-attempts` を上限に実行する。

1. コンソールに表示する: `## Step 4 — QA (attempt {n})`。
2. コーディング開始以降の差分を取得する: `${CLAUDE_PLUGIN_ROOT}/scripts/fetch-diff.sh diff {tmp_dir}/baseline-tree {tmp_dir}/changes.txt`。
3. `dev-helper` 宛に `templates/qa.md` を指定して `tmp_dir = {tmp_dir}`、`diff_path = {tmp_dir}/changes.txt`、`attempt_num = {n}` を渡して `SendMessage`。その 1 行の完了報告を `{summary_line}` として保持し、`{tmp_dir}/qa-result.json` を Read する: `{success}` は `failure == null`、`{suggested_specialist}` / `{error_summary}` は `failure` の対応フィールド。`workflow_warning` が非 null の場合、ステップ 5 のために保持する。
4. `success == true` の場合、ループを抜ける。
5. `success == false` かつ試行回数が残っている場合、QA 修正セルを回す:
   a. 失敗スコープを `general-purpose` の coder と、失敗ドメインに一致するペア reviewer（`{suggested_specialist}` をヒントとする）でカバーする。適合する roster のメンバーは再利用し、いなければ roster にない `coder-{slug}` / `reviewer-{slug}` を name として起動する。新規に起動する reviewer の subagent_type は、`{suggested_specialist}` が § Agent 種別と起動要件 の登録名として存在すればそれを、存在しなければ `general-purpose` を用いる。
   b. coder の name 宛に `templates/code.md` を指定し、`task = {task_summary}`、`design_paths = {design_paths}`、`assigned_scope = {失敗したファイル}`、`tdd = {has_test_suite}`、`feedback = QA failure — Read {tmp_dir}/qa-result.json (failure section) and {tmp_dir}/build.log; fix the build/test error.`、`reviewer = {ペア reviewer の name}`、`comment_reviewer = comment-sensei` を渡して `SendMessage`。そして reviewer の name 宛に `templates/code-review.md` を指定し、`task = {task_summary}`、`design_paths = {design_paths}`、`producer = {coder の name}`、`cell_task = code-qa-{n}`、`review_rounds = {--review-rounds}` を渡して `SendMessage`。
   c. そのセルのクローズ報告を受信したら、このループのステップ 1 へ戻る（再 QA）。
6. 最大試行回数を超えてもなお失敗する場合、`error_summary` をコンソールに提示してステップ 5 へ進む。

## ステップ 5 — クリーンアップと報告

1. `--commit` が ON かつ QA が通過した場合、実装をコミットする: 変更されたソースファイルのみをステージし（`.claude/tmp` は除く）、簡潔なメッセージで 1 回コミットする（finding ID なし）。
2. teammate をシャットダウンする: 各 teammate の name 宛に `SendMessage` で `{type: "shutdown_request"}` を送り、シャットダウンを待つ。
3. 作業用ディレクトリを削除する: `${CLAUDE_PLUGIN_ROOT}/scripts/rm-tmp.sh {tmp_dir}`。
4. コンソールへ報告する: ペアリングを含むチームのロスター、ステップごとに resolve したセル、エスカレーションと未解決項目のために残した `FIXME:`、変更されたファイル、QA 結果（`summary_line`、あれば `workflow_warning`）、および未修正の QA 失敗。
