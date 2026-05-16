---
name: start
description: 対象プロジェクトのエージェントから自動選定したレビュアーで並列コードレビューを起動する
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

## オプション

- `--base {branch}` — ベースブランチを指定する。デフォルトは `main` または `master`。
- `--output {path}` — 最終レポートの出力先パス (`{final_doc_path}`) を指定する。

### デフォルトのレビュー対象

ユーザーがレビュー対象を明示的に指定しなかった場合、以下をデフォルトのレビュー対象とする:

1. 現在のブランチ固有のコミット — ベースブランチとの分岐点以降のすべてのコミット（`git log {base}..HEAD` に相当）。
2. ワーキングツリーの変更 — ステージ済み（`git diff --cached`）および未ステージ（`git diff`）の変更。

ベースブランチが `--base` で指定されていない場合、リモートに存在する `main` または `master` を使用する（両方存在する場合は `main` を優先）。

### 出力先 (`{final_doc_path}`)

- `--output` 指定があればその値。
- 指定がない場合のデフォルト: `.claude/tmp/creview-start-{timestamp}.md`（`{timestamp}` は作業用ディレクトリ名と同じ値）。tmp_dir 配下には置かない（ステップ 4 で削除されるため）。
- 上位のオーケストレーター（/creview:rounds 等）から呼び出される場合は呼び出し側がパスを指定する。

## サブエージェント共通指示

共通禁止事項は `${CLAUDE_PLUGIN_ROOT}/rules/sub-agent.md` を参照。各サブエージェントへのプロンプト本体は `templates/*.md` の外部テンプレートに格納されている（frontmatter に `template_id` を持つ）。リーダーは Agent ツール起動時に「テンプレートを Read して指示に従う」旨の起動プロンプトに変数値を埋めて渡す。サブエージェントは戻り値に `template_id` を含める。リーダーは戻り値の `template_id` が各ステップで指定されている UUID（後述、各ステップにハードコード）と一致することを確認し、不一致の場合は当該サブエージェントを再起動する。

起動プロンプトの完全性に関する規約は `${CLAUDE_PLUGIN_ROOT}/rules/sub-agent.md` § 起動プロンプトの完全性を参照。

## ステップ 1 — レビュー範囲の特定と差分取得

リーダー（あなた）は差分内容を Read しない。差分の解析・行数算出・必要レビュアー候補の選定はスコープ解析サブエージェントに委譲し、戻り値（行数 + 候補リスト + サマリ）のみ受け取る。

1. ユーザーの入力に基づき、レビュー対象（ベースブランチ・対象パス等）と明示要求レビュアー（あれば）を特定する。
2. 作業用ディレクトリを作成する:
   - 一時ディレクトリ: `.claude/tmp/creview-start-{timestamp}/`
   - レビュアー出力サブディレクトリ: `{tmp_dir}/reviews/`
   - `mkdir -p` で両方作成する。
3. 差分情報をスクリプトで取得する:
   - 出力ファイルパス: `{tmp_dir}/diff.txt`
   - 以下を実行:
     ```
     ${CLAUDE_PLUGIN_ROOT}/scripts/fetch-diff.sh {base} {tmp_dir}/diff.txt
     ```
4. スコープ解析サブエージェントを起動して差分を解析させる。起動プロンプト例:

```
最初の行動として `${CLAUDE_PLUGIN_ROOT}/skills/start/templates/scope-analysis.md` を必ず Read する。Read 完了前に他の判断・行動・ツール呼び出しを行わない。Read 後はその指示に従う。

変数（テンプレート中の {{...}} placeholder を置換）:
- plugin_root: ${CLAUDE_PLUGIN_ROOT}
- tmp_dir: {tmp_dir}
- user_requested: {user_requested}

ラウンド固有のオーバーライド（テンプレートの指示に従った後に適用）:
- (none)

戻り値に template_id（テンプレートの frontmatter から Read）を含める。
```

5. サブエージェントから戻り値（`{line_count, recommended_reviewers, extension_summary, rationale, template_id}`）を受け取る。
6. `template_id` が `b3e2f1a7-9c84-4d56-8e3b-7f1a4c9d2e85` と一致することを確認する。一致しない場合はサブエージェントを再起動する。
7. `recommended_reviewers` をそのまま最終レビュアーリストとして確定し、各要素の `name` をステップ 2 で `subagent_type` に渡す。
8. `line_count == 0` の場合、空のレビュードキュメントを `{final_doc_path}` に生成してステップ 4 へ直接進む。

## ステップ 2 — 並列レビュアーの起動

選択したすべてのレビュアーを Agent ツールで同時に起動する。各レビュアーは指摘を stdout に返さず、専用ファイルに Write する。レビューリーダー（あなた）はレビュアー出力本体を context に載せない（後段の集約サブエージェントが読み取る）。

### レビュアー出力ファイル

- 各レビュアーごとに 1 ファイル: `{tmp_dir}/reviews/{reviewer-name}.md`
- 内容は「指摘の番号付きリスト」だけ（前後の挨拶や全体サマリは入れない）
- フォーマット: `[重要度] file_path:line — 問題の説明とその重要性。` の番号付きリスト

### エージェント起動プロンプト

Agent ツール起動時は `subagent_type={name}`（スコープ解析 Sub が対象プロジェクトの `.claude/agents/` から解決した名前、または `general-purpose`）を指定する。agent 定義の persona と観点は自動でロードされる。起動プロンプトに persona / 観点は含めない。タスク固有の指示は `templates/reviewer.md` 外部テンプレートに格納されている。

```
最初の行動として `${CLAUDE_PLUGIN_ROOT}/skills/start/templates/reviewer.md` を必ず Read する。Read 完了前に他の判断・行動・ツール呼び出しを行わない。Read 後はその指示に従う。

変数（テンプレート中の {{...}} placeholder を置換）:
- plugin_root: ${CLAUDE_PLUGIN_ROOT}
- targets: {targets}
- base: {base}
- diff_path: {diff_path}
- output_path: {output_path}

ラウンド固有のオーバーライド（テンプレートの指示に従った後に適用）:
- (none)

戻り値に template_id（テンプレートの frontmatter から Read）を含める。
```

各レビュアーから戻り値（`{path, critical, major, minor, info, template_id}`）を受け取る。`template_id` が `4d8c2e5b-1f73-4a96-b2e8-9c1d3a7f4b62` と一致することを確認する。一致しない場合は当該レビュアーを再起動する。

## ステップ 3 — レポートの統合（集約サブエージェントへ委譲）

すべてのレビュアーが完了した後、集約サブエージェントを起動してレポート統合を委任する。
レビューリーダーは集約処理（各レビュアーファイルの Read・重複排除・並べ替え・成果物 Write）を行わず、レビュアー出力本体を context に載せない。

`Agent(subagent_type="review-helper", prompt=...)` で起動する（model は review-helper の agent 定義に従う。リーダーから model 指定はしない）。

### 集約サブエージェントの起動プロンプト

タスク固有の指示は `templates/aggregator.md` 外部テンプレートに格納されている。

```
最初の行動として `${CLAUDE_PLUGIN_ROOT}/skills/start/templates/aggregator.md` を必ず Read する。Read 完了前に他の判断・行動・ツール呼び出しを行わない。Read 後はその指示に従う。

変数（テンプレート中の {{...}} placeholder を置換）:
- plugin_root: ${CLAUDE_PLUGIN_ROOT}
- tmp_dir: {tmp_dir}
- reviewer_paths_list: {reviewer_paths_list}
- final_doc_path: {final_doc_path}
- round_num_or_omitted: {round_num_or_omitted}
- targets_description: {targets_description}
- reviewer_names_csv: {reviewer_names_csv}

ラウンド固有のオーバーライド（テンプレートの指示に従った後に適用）:
- (none)

戻り値に template_id（テンプレートの frontmatter から Read）を含める。
```

集約サブエージェントから戻り値（`{doc_path, findings_total, severity_counts, duplicates_merged, template_id}`）を受け取る。`template_id` が `7a5f8c1d-3e92-4b67-9c4a-2d8e1f7b3c54` と一致することを確認する。一致しない場合はサブエージェントを再起動する。

## ステップ 4 — 一時ファイルのクリーンアップ

集約サブエージェントが最終レポートの Write を完了した後、ステップ 1 で作成した作業用ディレクトリ全体（`diff.txt` と `reviews/` 配下のレビュアーファイルを含む）を削除する。

```bash
${CLAUDE_PLUGIN_ROOT}/scripts/rm-tmp.sh {tmp_dir}
```
