---
name: respond
description: Will-Fix / Maintain / Alternative のレビュー指摘を修正し、ビルドを検証し、修正状況をレビュードキュメントに反映する。修正が作成・変更した AI 向けプロンプトファイルには、プロンプト規律のセルフチェック、圧縮、解釈テストも行う。triage / estimate メタデータ付きのレビュードキュメントが存在し、ユーザーが指摘への対応を求めたとき（例「レビュー指摘を修正して」）に能動的に使用する。
allowed-tools: Agent, Read, Write, Edit, Glob, Grep, Bash(cd:*), Bash(grep:*), Bash(ls:*), Bash(find:*), Bash(mkdir:*), Bash(git log:*), Bash(git diff:*), Bash(git show:*), Bash(git rev-parse:*), Bash(git add:*), Bash(git commit:*), Bash(git status:*), Bash(${CLAUDE_PLUGIN_ROOT}/scripts/fetch-diff.sh:*), Bash(${CLAUDE_PLUGIN_ROOT}/scripts/del-tmp.sh:*), Bash(python3 ${CLAUDE_PLUGIN_ROOT}/scripts/gh-pr.py:*), Bash(python3 ${CLAUDE_PLUGIN_ROOT}/skills/respond/scripts/compile-review.py:*), Bash(python3 ${CLAUDE_PLUGIN_ROOT}/scripts/render-review.py:*)
---

# レビュー対応（修正）

あなたは**レビュー対応リーダー**として、すでに `triage` / `estimate` メタデータ（`/creview:triage` が記録）を持つレビュードキュメントを読み、修正対象の指摘を選別し、適切な専門エージェントに修正を委任し、ビルド検証で品質を確保し、修正の `status` を `render-review.py` 経由でレビュードキュメントに反映する。

レビュー対応リーダー自身は修正作業を行わず、プロセス全体のオーケストレーションと結果の集約・判断を行う。修正作業はすべてサブエージェントに委任する。

本スキルの前に `/creview:triage {document}` を実行する。本スキルは `triage` が `🔧 Will Fix`、`estimate` が `▶️ Maintain` または `🚧 Alternative` で、かつ未着手の指摘のみを修正する — `status` がまだ無いか、`status` はあるが検証が `💬 Feedback` を返したもの。

## 入力

ユーザーはレビュードキュメント（markdown）へのパスを指定する。引数が `$ARGUMENTS` の場合、レビュードキュメントへのパスとして解釈する。

## タイムスタンプ（`{timestamp}`）

`{timestamp}` はステップ 1 の開始時に一度だけ決定する現在日時文字列（`YYYYMMDD-HHMMSS` 形式、例: `20240101-120000`）。以降の全ステップで同一値を使う。

## オプション

- `--commit`（デフォルト OFF）— 修正後のソースコードをステップ 5 でコミットする。ワークツリーでは ON になる（§ ワークツリー）。
- `--adr`（デフォルト OFF）— 実装時の設計判断にまだ ADR が無い場合に、修正サブエージェントが ADR ファイルを新規作成することを許可する（スケルトン: `${CLAUDE_PLUGIN_ROOT}/rules/adr-format.md`）。`Estimate:` メタデータから参照されている ADR ファイル（`/creview:triage --adr` が作成。ユーザーが編集している場合もある）の修正前の読み込みと修正後の更新は、このオプションに寄らず実行される。

## ワークツリー

`${CLAUDE_PLUGIN_ROOT}/rules/doc-worktree.md` に従う。その `plugin_root` 変数は `${CLAUDE_PLUGIN_ROOT}` とし、`doc-checkout` の末尾に `--fix-branch` を付ける。`pr_worktree` が true の場合は、次の PR ワークツリー向けオーバーライドを追加する:

- フォーマット・ビルド・テスト検証サブエージェントへ: `build-format-detection.md の段階 2 は、{target_dir} 配下のファイルからではなく、{main_root}/CLAUDE.md、次に {main_root}/README.md から解決する。コマンドは通常どおり {target_dir} で実行する。`
- `trust` が `off` のとき、select-fix-targets サブエージェントへ: `location または fix_plan が、{target_dir} に置いていないエージェントファイルのいずれかのパスを指す修正対象は、--trust なしでレビューしたためそのファイルをチェックアウトしていないという理由で not_ready へ移す。`

`merge_base` が null でない場合は、解釈テストサブエージェントに次のオーバーライドを追加する。`{target_dir}` はその値で書く: `各テスト担当のプロンプトに次を加える: {target_dir} 配下のファイルだけを開く。プロンプトが指す {target_dir} 外のファイルは利用できないものとし、利用できないファイルを読めないことだけを理由に項目を unclear と報告しない。` `pr_worktree` が true かつ `trust` が `off` の場合は、そのオーバーライドの末尾に次を加える: `{target_dir} 配下の CLAUDE.md、CLAUDE.local.md、AGENTS.md、.mcp.json、.claude も、大文字小文字を問わずどの深さでも利用できないものとする。{target_dir} はそれらを除外している。`

## レビュードキュメント形式

レビュードキュメントは `/creview:start` が生成し、`/creview:triage` が更新する。各指摘はメタデータブロックを持つ:

```markdown
<!-- METADATA({finding-id}) -->
- **Triage:** 🔧 Will Fix (assignee: cpp-sensei) — Valid finding
- **Estimate:** ▶️ Maintain — Cost: M, Future: S, Signals: b,d — Plan: (1) src/foo.cpp:42 — null チェック追加
<!-- /METADATA({finding-id}) -->
```

`/creview:triage --adr` を使った場合、`Estimate:` 値は ` — Plan: ` の直前に ` — ADR: {ファイル名}` セグメントを持つことがある。ファイル名はレビュードキュメントと同じディレクトリにあるその指摘の ADR ファイルを指す。

`/creview:resolve` を通過した指摘は `Verification:` 行も持つ。そこが `💬 Feedback` の場合、記録済みの修正は不十分と判定されている。

本スキルは以下を追記する:

- `status`（ステップ 6）— 値の形式: `🟢 Fixed — {修正内容の簡潔な説明}`。

### 修正対象選別ルール

指摘が修正対象となるのは以下が**すべて**成立する場合（METADATA マーカーから読み取り、フィールドが繰り返す場合は最後の値を使う）:

- `Triage:` が `🔧 Will Fix`（assignee は `(assignee: {specialist})` からパースする）。
- `Estimate:` が `▶️ Maintain`（通常修正）または `🚧 Alternative`（FIXME 付与のみ）。
- `Status:` が存在しない、または `Verification:` が `💬 Feedback`。メタデータは追記専用のため、再修正に差し戻された指摘も以前の `Status:` を持ち続ける。

`Triage: 🚫 Won't Fix`、`Estimate: 🔻 Downgrade`、および `Status:` が `🟢 Fixed` で `Verification:` が無いか `✅ Verified` の指摘はスキップする。

## サブエージェントの起動

共通禁止事項・ワンショット起動形態（`run_in_background: false`）・起動プロンプトの完全性は `${CLAUDE_PLUGIN_ROOT}/rules/sub-agent.md` を参照。各サブエージェントへの指示は `templates/*.md` の外部テンプレート（frontmatter に `template_id` を持つ）にあり、起動プロンプトはその内容を引用せず、テンプレートを Read させる。

サブエージェントはすべて以下のプロンプトで起動し、テンプレート・変数・オーバーライドは各ステップの指定で置換する:

```
最初の行動として `${CLAUDE_PLUGIN_ROOT}/skills/respond/templates/{template}` を必ず Read する。Read 完了前に他の判断・行動・ツール呼び出しを行わない。Read 後はその指示に従う。

変数（テンプレート中の {{...}} placeholder を置換）:
- {name}: {value}

ラウンド固有のオーバーライド（テンプレートの指示に従った後に適用）:
- (該当なし)

戻り値に template_id（テンプレートの frontmatter から Read）を含める。
```

戻り値の `template_id` が各ステップで指定した UUID と一致することを確認し、不一致の場合は当該サブエージェントを再起動する。

### 専門家エージェントの解決

本スキルは同梱エージェント 2 つを固定役割で実行する: `creview:comment-sensei`（ステップ 3）と、`creview:prompt-tester` を起動する `creview:prompt-sensei`（ステップ 3〜4）。各指摘の assignee は `Triage:` メタデータ（`(assignee: {specialist})`）から読み取る。これは `/creview:triage` が**反映先プロジェクトの** `.claude/agents/` に対して記録したものである。リーダーはその assignee 名をそのまま `subagent_type` に渡す。assignee が存在しない、または解決できない場合は `general-purpose` を使う。ビルド／テスト修正専門家は、フォーマット・ビルド・テスト検証 Sub が反映先プロジェクトの `.claude/agents/`（または `general-purpose`）から解決する。

## 内部処理（中間ファイル）

各判定は中間ファイルに書き出し、`compile-review.py` が集約する。リーダー（あなた）は判定結果本文を context に載せない。

### 作業用ディレクトリ

```
{tmp_dir} = .claude/tmp/creview-respond-{timestamp}/
{tmp_dir}/targets.jsonl        ← select-fix-targets サブエージェントの出力
{tmp_dir}/statuses/{id}.jsonl  ← 修正サブエージェントの出力（指摘 1 件 1 ファイル）
{tmp_dir}/prompt-test.jsonl    ← 解釈テストサブエージェントの出力（ステップ 4）
{tmp_dir}/events.jsonl         ← compile-review.py の出力（render-review.py 入力）
```

`{main_root}` は、上位フロー（例: `/creview:rounds`）がこのスキルを実行する場合は起動プロンプトが渡した `main_root`、スキルを直接起動した場合は `(該当なし)` とする。`{target_dir}` も同様に起動プロンプトが渡した `target_dir` とし、スキルを直接起動した場合は `git rev-parse --show-toplevel` の出力とする。ワークツリーでは両者を置き換える（§ ワークツリー）。

中止する場合: エラーを表示し、実行すべき時点であればティアダウン（§ ワークツリー）を実行し、`${CLAUDE_PLUGIN_ROOT}/scripts/del-tmp.sh {tmp_dir}` で `{tmp_dir}` を削除してスキルを終了する。

書き出しには **Write ツール**を使う。Bash の cat heredoc は値内のアポストロフィ（例: `Won't`）でクォーティングが破綻するため使用不可。

ステップ 1 開始時に、`{tmp_dir}` を作成する前にリーダー（あなた）がシンボリックリンクの `.claude` を拒否する `${CLAUDE_PLUGIN_ROOT}/scripts/del-tmp.sh --dry {tmp_dir}` を実行し、非ゼロ終了の場合はそのエラーを表示してスキルを終了する。続いてリーダーが `mkdir -p {tmp_dir}/statuses` で `{tmp_dir}` を作成し、各サブエージェントに `{tmp_dir}` を渡す。

## ステップ 1 — 修正対象の選別（select-fix-targets サブエージェントへ委譲）

`{tmp_dir}` を作成する前に、`git rev-parse --show-prefix` の出力が空でない（セッションがリポジトリのサブディレクトリにある）場合は、スキルにはリポジトリルートでの起動が必要である旨のエラーを表示してスキルを終了する。スキルを直接起動した場合は、`{tmp_dir}` を作成した後にドキュメントのコードの場所を決める（§ ワークツリー）。

`Agent(subagent_type="general-purpose", prompt=...)` で起動する。Sub はレビュードキュメントを Read し、修正対象選別ルールを適用し、`{tmp_dir}/targets.jsonl` を Write する。

テンプレート `select-fix-targets.md`、`template_id` `7c3e9a1d-5b48-4f62-9a8c-2d6f1b3e7a95`、変数 `plugin_root = ${CLAUDE_PLUGIN_ROOT}`、`main_root = {main_root}`, `target_dir = {target_dir}`、`document_path = {document_path}`、`tmp_dir = {tmp_dir}`、オーバーライド `(該当なし)`。戻り値: `{path, fix_count, by_assignee: [{assignee, ids: [id, ...]}], not_ready: [{id, reason}], template_id}` — 本文は読み込まない。`not_ready` はステップ 7 のために保持する。

`fix_count == 0` の場合、ステップ 2〜5 をスキップしてステップ 6（編纂。反映するものなし → 「修正対象なし」を報告）へ進む。

## ステップ 2 — 修正（専門家サブエージェントへ並列委譲）

起動前に、`${CLAUDE_PLUGIN_ROOT}/scripts/fetch-diff.sh HEAD {tmp_dir}/baseline.txt` を実行する。非ゼロ終了の場合は、そのエラーで中止する。`by_assignee` の各 `{assignee, ids}` ごとに `Agent(subagent_type=assignee, prompt=...)` で修正サブエージェントを起動する。異なる assignee は並列起動する。同一 assignee 内の ids はテンプレートの並列化制約に従う。

テンプレート `fix.md`、`template_id` `2f8a1c5d-7b94-4e63-a1c8-5d3f9b2e7a14`、変数 `plugin_root = ${CLAUDE_PLUGIN_ROOT}`、`main_root = {main_root}`, `target_dir = {target_dir}`、`ids = {ids}`、`document_path = {document_path}`、`tmp_dir = {tmp_dir}`、`adr_flag = {on|off、--adr に従う}`、`timestamp = {timestamp}`、オーバーライド `(該当なし)`。各エージェントの戻り値: `{items: [{id, path}, ...], template_id}` — `items` のみを集め、status 本文は読み込まない。

## ステップ 3 — コメントレビューとプロンプトレビュー（comment-sensei と prompt-sensei のサブエージェントへ委譲）

修正サブエージェントが追加・変更したコメントが `${CLAUDE_PLUGIN_ROOT}/rules/comment.md` の規律に違反していないかを comment-sensei にレビューさせ、違反があれば修正させる。comment-sensei には今回の修正差分（`fetch-diff.sh` 出力）とレビュードキュメント（`{document_path}`）を渡し、変更されたコメントを把握しつつ各指摘の趣旨を棄損しない範囲で調整させる。追加・変更されたコメントが無い場合、サブエージェントは何もせず終了してよい。

リーダーは起動前に `${CLAUDE_PLUGIN_ROOT}/scripts/fetch-diff.sh HEAD {tmp_dir}/changes.txt` で修正差分を取得する。`Agent(subagent_type="creview:comment-sensei", prompt=...)` で起動する。

テンプレート `comment-review.md`、`template_id` `4a8e2d6f-9b15-4c73-8a2d-7f1e5c9b3d68`、変数 `plugin_root = ${CLAUDE_PLUGIN_ROOT}`、`main_root = {main_root}`, `target_dir = {target_dir}`、`tmp_dir = {tmp_dir}`、`diff_path = {tmp_dir}/changes.txt`、`document_path = {document_path}`、オーバーライド `(該当なし)`。戻り値: `{reviewed_paths, fix_count, template_id}`。

comment-sensei が戻った後、プロンプトレビューを実行する。`{tmp_dir}/statuses/*.jsonl` の `files` 配列のみを読む（判定本文ではなく運用データである）。それらのファイルに拡張子 `.md` のものが無い場合は、プロンプトレビューをスキップし、空の `prompt_files` を保持する。そうでなければ `${CLAUDE_PLUGIN_ROOT}/scripts/fetch-diff.sh HEAD {tmp_dir}/changes.txt` を再度実行し、`Agent(subagent_type="creview:prompt-sensei", prompt=...)` で起動する。Sub はそれらのファイルのうちどれが AI 向けプロンプトファイルかを判定する。

テンプレート `prompt-review.md`、`template_id` `6be7d388-2c9d-41f1-a349-a47407e157f4`、変数 `plugin_root = ${CLAUDE_PLUGIN_ROOT}`、`main_root = {main_root}`, `target_dir = {target_dir}`、`tmp_dir = {tmp_dir}`、`diff_path = {tmp_dir}/changes.txt`、`baseline_path = {tmp_dir}/baseline.txt`、`document_path = {document_path}`、オーバーライド `(該当なし)`。戻り値: `{prompt_files: [{path, created}], violations_detected, violations_fixed, compressed_count, added_files, remaining: [{location, rule}], template_id}`。すべて保持する。

## ステップ 4 — フォーマット・ビルド・テスト検証と解釈テスト

リーダー（あなた）はフォーマッタやビルドコマンドを直接実行せず、ソースコードも読まない。フォーマット・ビルド・テスト検証 Sub は `${CLAUDE_PLUGIN_ROOT}/rules/build-format-detection.md` の手順（`build-format.md` 記述子をプロジェクト→ユーザー→プラグイン同梱スコープで再帰探索、無ければ `CLAUDE.md` → `README.md`）で反映先プロジェクトのフォーマット／ビルド／テスト手順を解決し、単発のフォーマット・ビルド・テスト実行のみ行う（テストはテスト手順が解決された場合のみ。いずれも解決できない場合は目視チェックのみとなり警告を返す）。Sub には今回の修正差分（`fetch-diff.sh` 出力）を渡し、変更内容がビルド／テストの結果に影響し得ない場合（コメントのみ等）は当該ステージを省略できる。ビルド／テスト失敗時はコードを読んで修正担当の専門家を判定して結果を返す（自分でコードは修正しない）。リーダーは専門家 Sub を起動して修正させ、ビルドとテストが通るまで検証 Sub と専門家 Sub を交互に再起動するループをオーケストレートする。ステップ 3 で空でない `prompt_files` を保持した場合は、各試行で解釈テストも実行し、ループは unclear 項目のあるファイルを、ビルド／テストの失敗と同じように修正する。

### ループ制御（リーダー）

最大試行回数: 5。ビルド／テストと解釈テストで共有する。1 から始まる各試行 n について:

1. `${CLAUDE_PLUGIN_ROOT}/scripts/fetch-diff.sh HEAD {tmp_dir}/changes.txt` で現在の修正差分（作業ツリー）を取得し、フォーマット・ビルド・テスト検証 Sub を `Agent(subagent_type="creview:review-helper", prompt=...)` で起動する — テンプレート `format-build-verify.md`、`template_id` `9d3c5f8a-2b71-4e94-a8c5-1f7d3b9e2c46`、変数 `plugin_root = ${CLAUDE_PLUGIN_ROOT}`、`main_root = {main_root}`, `target_dir = {target_dir}`、`tmp_dir = {tmp_dir}`、`diff_path = {tmp_dir}/changes.txt`、`attempt_num = {n}`、オーバーライド `(該当なし)`。
   `prompt_files` が空でない場合は、同じメッセージで解釈テスト Sub を `Agent(subagent_type="creview:prompt-sensei", prompt=...)` で起動する — テンプレート `prompt-test.md`、`template_id` `a3d8a6e0-5eb4-4540-b28b-b1ef6a4bfb52`、変数 `plugin_root = ${CLAUDE_PLUGIN_ROOT}`、`main_root = {main_root}`, `target_dir = {target_dir}`、`tmp_dir = {tmp_dir}`、`diff_path = {tmp_dir}/changes.txt`、`baseline_path = {tmp_dir}/baseline.txt`、`document_path = {document_path}`、`prompt_files = {prompt_files}`、`output_path = {tmp_dir}/prompt-test.jsonl`、`attempt_num = {n}`、`fixed_files = {fixed_files}`（試行 1 では `(none)`）、オーバーライド `(該当なし)`。
2. 検証の戻り値（`{path, success, environmental, format_violations_fixed, workflow_source, workflow_warning, summary_line, template_id}`）から、`workflow_warning` を前の試行の値に代えてステップ 7 のために保持する。`success == false` かつ `environmental == true` の場合は、`{tmp_dir}/format-build-result.jsonl` の `failure` セクションから `error_summary` を Read し、保持する `workflow_warning` を「環境起因でビルド／テスト検証が完了しなかった: {error_summary}」に置き換え、ユーザーに `error_summary` を提示する。この失敗にはビルド／テスト修正 Sub を起動しない。
3. 解釈テストの戻り値（`{path, attempt, pass, tested_count, failed_files, untested_files: [{path, reason}], summary_line, template_id}`）から、`failed_files`、`untested_files`、`summary_line` をそれぞれ `{prompt_failed_files}`、`{prompt_untested_files}`、`{prompt_summary_line}` として、前の試行の値に代えて保持する。戻り値にそれらが無い場合、または `attempt` が n でない場合は、`{prompt_failed_files}` を空とし、`prompt_files` の各パスを、解釈テストが結果を返さなかったという理由で `{prompt_untested_files}` として保持し、`{prompt_summary_line}` には解釈テストが結果を返さなかった旨を保持する。
4. ビルド／テストに `environmental == false` の失敗が無く、`{prompt_failed_files}` が空なら、ループを抜ける。
5. n が 5 の場合は、`{prompt_failed_files}` をユーザーに提示してループを抜ける。ビルド／テストが `environmental == false` で失敗していれば、`{tmp_dir}/format-build-result.jsonl` の `failure` セクションから `error_summary` を Read し、それもあわせて提示する。
6. それ以外は、修正を順に行う。両方の修正が同じファイルを編集し得るためである:
   a. ビルド／テストが `environmental == false` で失敗した場合は、`{tmp_dir}/format-build-result.jsonl` を Read し、`failure` セクションから `suggested_specialist` / `error_summary` / `error_files` / `fix_guidance` / `log_path` を取得する（判定本文ではない運用データ。ただしソースコード本体は Read しない）。`Agent(subagent_type=suggested_specialist, prompt=...)` でビルド／テスト修正専門家 Sub を起動する — テンプレート `build-fix.md`、`template_id` `6e2a9f5c-1d83-4b74-9c2e-5a8d3f1b7e29`、変数 `plugin_root = ${CLAUDE_PLUGIN_ROOT}`、`main_root = {main_root}`, `target_dir = {target_dir}`、`tmp_dir = {tmp_dir}`、オーバーライド `(該当なし)`。戻り値: `{description, template_id}`。
   b. `{prompt_failed_files}` が空でない場合は、プロンプト修正 Sub を `Agent(subagent_type="creview:prompt-sensei", prompt=...)` で起動する — テンプレート `prompt-fix.md`、`template_id` `cbbd9597-ca26-4308-a6d1-67cb18498aff`、変数 `plugin_root = ${CLAUDE_PLUGIN_ROOT}`、`main_root = {main_root}`, `target_dir = {target_dir}`、`tmp_dir = {tmp_dir}`、`document_path = {document_path}`、`result_path = {tmp_dir}/prompt-test.jsonl`、オーバーライド `(該当なし)`。戻り値: `{files, template_id}`。
   c. `{fixed_files}` を、a の `error_files` のパス（行番号を除く）と b の `files` の和集合とし、試行 n + 1 を始める。

ループの後、`{prompt_warning}` を設定する: `{prompt_failed_files}` か `{prompt_untested_files}` が空でない場合は、解釈テストに不合格のまま残った各ファイルと実行した試行回数、および未テストの各ファイルとその理由を示す文字列とする。それ以外の場合と、解釈テストを一度も実行しなかった場合は null とする。

## ステップ 5 — コミット（`--commit` 指定時のみ）

`--commit` が OFF の場合はこのステップをスキップする。この時点でソースコードは確定している — 修正、comment-sensei による調整、プロンプトレビューによる編集、ビルド／テスト修正とプロンプト修正のすべてが作業ツリーにある。

1. ステップ 1 の `by_assignee` 単位が所有するファイルは、`{tmp_dir}/statuses/*.jsonl` のうちその単位の id が持つ `files` の和集合（`files` 配列のみを読む。判定本文ではなく運用データである）。各単位について、他の単位が所有していないファイルのみをステージングしてコミットする。
2. 作業ツリーに残った変更をまとめて最後の 1 コミットにする — 複数の単位が共有するファイル、どの単位も所有しないファイルへの comment-sensei / prompt-sensei / ビルド修正の変更、およびプロンプトレビューが追加したテンプレートファイル（ステップ 3 の `added_files`）。残りが無ければこのコミットは作らない。
3. `git add -A` は使用しない。`{document_path}` および `{tmp_dir}`・`.claude/tmp/`・`.claude/worktrees/` 配下はステージングしない。
4. コミットメッセージ: 1〜3 行で、コードが現在何をするかを記述する。指摘 ID（`C-1`、`M-1` 等）は含めない。例: `fix: Add null check before accessing output pointer`
5. ステップ 4 がビルド／テスト失敗で抜けた場合もコミットする。`error_summary` は既にユーザーに提示されており、コミットされない変更は以降のどのラウンドのコミット範囲にも入らない。

## ステップ 6 — レビュードキュメントへの反映

リーダー（あなた）は判定本文を context に載せない。修正状況（`status`）は `compile-review.py` が `statuses/*.jsonl` から集約し events.jsonl 経由で markdown に反映する（`triage` / `estimate` は `/creview:triage` が永続化済み）。

1. 次を実行する（CWD はプロジェクトルート）:

   ```bash
   python3 ${CLAUDE_PLUGIN_ROOT}/skills/respond/scripts/compile-review.py {tmp_dir} {document_path}
   ```

2. stdout の結果 JSON（`{fixed_count, code_changed, summary_line, maintain, alternative}`）を受け取る。`fixed_count` は修正件数（statuses のファイル数）。

3. リーダーが `{tmp_dir}` を一括削除:
   ```bash
   ${CLAUDE_PLUGIN_ROOT}/scripts/del-tmp.sh {tmp_dir}
   ```

## ステップ 7 — サマリー

リーダーはステップ 6 で受け取った `summary_line` をコンソールに表示する。ステップ 4 で `workflow_warning` を受け取っていた場合は、`summary_line` と併せて警告行として表示する。ステップ 1 の `not_ready` が空でなければ、その id と理由を未修正のまま残った指摘として `summary_line` と併せて表示する（`fix_count == 0` でステップ 2〜5 をスキップした場合も同じ）。ステップ 3 で空でない `prompt_files` を保持した場合は、プロンプトレビューの件数（レビューしたファイル数、検出 / 修正した違反数、圧縮したファイル数）、その `added_files`、`remaining` の各違反の `location` と `rule`、および `{prompt_summary_line}` も表示する。`{prompt_warning}` が非 null の場合は、`workflow_warning` と同様に警告行として表示する。詳細テーブルが必要な場合のみ、更新後の `{document_path}` を Read し、`${CLAUDE_PLUGIN_ROOT}/skills/respond/templates/respond-summary.md` のフォーマットに従って表示する。

ワークツリーでは、ティアダウンを実行し（§ ワークツリー）、修正をコミットしたブランチを報告する。
