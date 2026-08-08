---
name: start
description: 対象プロジェクトのエージェントから自動選定したレビュアーで並列コードレビューを起動する。ユーザーが変更・ブランチ・PR のレビューを求めたとき（例「このコードをレビューして」）や、まとまった実装が完了した直後に能動的に使用する。
allowed-tools: Agent, Read, Glob, Grep, Bash(${CLAUDE_PLUGIN_ROOT}/scripts/fetch-diff.sh:*), Bash(${CLAUDE_PLUGIN_ROOT}/scripts/rm-tmp.sh:*), Bash(grep:*), Bash(ls:*), Bash(find:*), Bash(mkdir:*), Bash(git log:*), Bash(git diff:*), Bash(git show:*)
---

# 並列コードレビュー

あなたは**レビューリーダー**として、専門レビュアーを使った並列コードレビューを統括し、各レビュアーの指摘を 1 つのレポートに統合する。

レビューリーダーはレビュアーの役割を担わず、レビュー全体のオーケストレーションと集約・判断を行う。レビュアーの役割はすべてサブエージェントに委任する。

## ラウンド番号

引数にラウンド番号（例: `Round 1`、`Round 2`）が含まれる場合は、レポートタイトルに反映する。

## 入力

ユーザーはレビュー対象として以下の 1 つ以上を指定する:
- ファイルパスまたは glob パターン
- git diff 範囲（例: `HEAD~3..HEAD`、ブランチ名、PR）
- レビュー対象領域の説明

引数が `$ARGUMENTS` の場合、レビュー対象の指定（ラウンド番号やオプションを含む）として解釈する。

## タイムスタンプ（`{timestamp}`）

`{timestamp}` はステップ 1 の開始時に一度だけ決定する現在日時文字列（`YYYYMMDD-HHMMSS` 形式、例: `20240101-120000`）。以降の全ステップで同一値を使う。

## オプション

- `--base {branch}` — ベースブランチを指定する。デフォルトは `main` または `master`。
- `--output {path}` — 最終レポートの出力先パス (`{final_doc_path}`) を指定する。
- `--adversarial`（デフォルト OFF）— ステップ 2 のレビュアーを敵対的レビュアーテンプレートで実行する。

### 敵対的モードの値

`--adversarial` は以下の値を確定する。ステップ 2 とステップ 3 で使用する:

- OFF（デフォルト）: `{reviewer_template}` = `reviewer.md`、`{reviewer_template_id}` = `4d8c2e5b-1f73-4a96-b2e8-9c1d3a7f4b62`、`{review_mode}` = `standard`
- ON: `{reviewer_template}` = `adversarial-reviewer.md`、`{reviewer_template_id}` = `2e68714d-36e4-4a4c-a557-d34a81661cb1`、`{review_mode}` = `adversarial`

### デフォルトのレビュー対象

ユーザーがレビュー対象を明示的に指定しなかった場合、以下をデフォルトのレビュー対象とする:

1. 現在のブランチ固有のコミット — ベースブランチとの分岐点以降のすべてのコミット（`git log {base}..HEAD` に相当）。
2. ワーキングツリーの変更 — ステージ済み（`git diff --cached`）および未ステージ（`git diff`）の変更。

ベースブランチが `--base` で指定されていない場合、リモートに存在する `main` または `master` を使用する（両方存在する場合は `main` を優先）。

### 出力先 (`{final_doc_path}`)

- `--output` 指定があればその値。
- 指定がない場合のデフォルト: `.claude/tmp/creview-start-{timestamp}.md`。tmp_dir 配下には置かない（ステップ 4 で削除されるため）。
- 上位のオーケストレーター（/creview:rounds 等）から呼び出される場合は呼び出し側がパスを指定する。

## 出力言語

レビュードキュメントの散文（指摘の説明、サマリ本文）はユーザーのチャット言語で記述する。リーダーは現在のチャットでユーザーが使用している言語を判定し `{doc_lang}`（例: `日本語`、`English`）として確定し、ステップ 2 のレビュアーおよびステップ 3 の集約サブエージェントへ変数として渡す。

構造アンカー（重要度見出し `## Critical` / `## Major` / `## Minor` / `## Info`、finding-id、メタデータマーカー）は後工程（triage / respond / resolve）の解析対象のため `{doc_lang}` に関わらず変更しない。

## サブエージェントの起動

共通禁止事項と起動プロンプトの完全性は `${CLAUDE_PLUGIN_ROOT}/rules/sub-agent.md` および同 § 起動プロンプトの完全性 を参照。各サブエージェントへの指示は `templates/*.md` の外部テンプレート（frontmatter に `template_id` を持つ）にあり、起動プロンプトはその内容を引用せず、テンプレートを Read させる。

サブエージェントはすべて以下のプロンプトで起動し、テンプレート・変数・オーバーライドは各ステップの指定で置換する:

```
最初の行動として `${CLAUDE_PLUGIN_ROOT}/skills/start/templates/{template}` を必ず Read する。Read 完了前に他の判断・行動・ツール呼び出しを行わない。Read 後はその指示に従う。

変数（テンプレート中の {{...}} placeholder を置換）:
- {name}: {value}

ラウンド固有のオーバーライド（テンプレートの指示に従った後に適用）:
- (none)

戻り値に template_id（テンプレートの frontmatter から Read）を含める。
```

戻り値の `template_id` が各ステップで指定した UUID と一致することを確認し、不一致の場合は当該サブエージェントを再起動する。

## 内部処理（中間ファイル）

リーダー（あなた）はレビュアー出力本体を context に載せない。

### 作業用ディレクトリ

```
{tmp_dir} = .claude/tmp/creview-start-{timestamp}/
{tmp_dir}/diff.txt                    ← リーダーがステップ 1 で取得する差分（スコープ解析サブエージェント入力）
{tmp_dir}/reviews/{reviewer-name}.md  ← 各レビュアーの出力（指摘の番号付きリスト）
```

作成はステップ 1、削除はリーダーがステップ 4 で `${CLAUDE_PLUGIN_ROOT}/scripts/rm-tmp.sh {tmp_dir}` で行う。

## ステップ 1 — レビュー範囲の特定と差分取得

リーダー（あなた）は差分内容を Read しない。差分の解析・行数算出・必要レビュアー候補の選定はスコープ解析サブエージェントに委譲し、戻り値（行数 + 候補リスト + サマリ）のみ受け取る。

1. ユーザーの入力に基づき、レビュー対象（ベースブランチ・対象パス等）と明示要求レビュアー（あれば）を特定する。
2. `{timestamp}` を解決して `{tmp_dir}` を確定し、`mkdir -p {tmp_dir}/reviews` で作業用ディレクトリを作成する。
3. 差分情報をスクリプトで取得する:
   - 出力ファイルパス: `{tmp_dir}/diff.txt`
   - 以下を実行:
     ```
     ${CLAUDE_PLUGIN_ROOT}/scripts/fetch-diff.sh {base} {tmp_dir}/diff.txt
     ```
4. スコープ解析サブエージェントを起動して差分を解析させる — テンプレート `scope-analysis.md`、`template_id` `b3e2f1a7-9c84-4d56-8e3b-7f1a4c9d2e85`、変数 `plugin_root = ${CLAUDE_PLUGIN_ROOT}`、`tmp_dir = {tmp_dir}`、`user_requested = {user_requested}`、オーバーライド `(none)`。戻り値: `{line_count, recommended_reviewers, extension_summary, rationale, template_id}`。
5. `recommended_reviewers` をそのまま最終レビュアーリストとして確定し、各要素の `name` をステップ 2 で `subagent_type` に渡す。
6. `line_count == 0` の場合、空のレビュードキュメントを `{final_doc_path}` に生成してステップ 4 へ直接進む。

## ステップ 2 — 並列レビュアーの起動

選択したすべてのレビュアーを Agent ツールで同時に起動する。各レビュアーは指摘を stdout に返さず、専用ファイルに Write する。レビューリーダー（あなた）はレビュアー出力本体を context に載せない（後段の集約サブエージェントが読み取る）。

### レビュアー出力ファイル

- 各レビュアーごとに 1 ファイル: `{tmp_dir}/reviews/{reviewer-name}.md`
- 内容は「指摘の番号付きリスト」だけ（前後の挨拶や全体サマリは入れない）
- フォーマット: `[重要度] [カテゴリ] file_path:line — 問題の説明とその重要性。` の番号付きリスト。カテゴリは 1 件以上付与し、複数の場合は `/` で連結して 1 つの `[ ]` にまとめる（例: `[バグ/保守性]`）。プリセットの詳細はレビュアー向けテンプレート参照。

### レビュアーの起動

`subagent_type={name}`（スコープ解析 Sub が対象プロジェクトの `.claude/agents/` から解決した名前、または `general-purpose`）を指定する。agent 定義の persona と観点は自動でロードされる。起動プロンプトに persona / 観点は含めない。

テンプレート `{reviewer_template}`、`template_id` `{reviewer_template_id}`、変数 `plugin_root = ${CLAUDE_PLUGIN_ROOT}`、`targets = {targets}`、`base = {base}`、`diff_path = {diff_path}`、`output_path = {output_path}`、`doc_lang = {doc_lang}`、オーバーライド `(none)`。各レビュアーの戻り値: `{path, critical, major, minor, info, template_id}`。

## ステップ 3 — レポートの統合（集約サブエージェントへ委譲）

すべてのレビュアーが完了した後、集約サブエージェントを起動してレポート統合を委任する。
レビューリーダーは集約処理（各レビュアーファイルの Read・重複排除・並べ替え・成果物 Write）を行わず、レビュアー出力本体を context に載せない。

`Agent(subagent_type="review-helper", prompt=...)` で起動する（model は review-helper の agent 定義に従う。リーダーから model 指定はしない）。

テンプレート `aggregator.md`、`template_id` `7a5f8c1d-3e92-4b67-9c4a-2d8e1f7b3c54`、変数 `plugin_root = ${CLAUDE_PLUGIN_ROOT}`、`tmp_dir = {tmp_dir}`、`reviewer_paths_list = {reviewer_paths_list}`、`final_doc_path = {final_doc_path}`、`round_num_or_omitted = {round_num_or_omitted}`、`targets_description = {targets_description}`、`reviewer_names_csv = {reviewer_names_csv}`、`review_mode = {review_mode}`、`doc_lang = {doc_lang}`、オーバーライド `(none)`。戻り値: `{doc_path, findings_total, severity_counts, duplicates_merged, template_id}`。

## ステップ 4 — 一時ファイルのクリーンアップ

集約サブエージェントが最終レポートの Write を完了した後、ステップ 1 で作成した作業用ディレクトリ全体（`diff.txt` と `reviews/` 配下のレビュアーファイルを含む）を削除する。

```bash
${CLAUDE_PLUGIN_ROOT}/scripts/rm-tmp.sh {tmp_dir}
```
