---
name: respond
description: Will-Fix / Maintain / Alternative のレビュー指摘を修正し、ビルドを検証し、修正状況をレビュードキュメントに反映する。triage / estimate メタデータ付きのレビュードキュメントが存在し、ユーザーが指摘への対応を求めたとき（例「レビュー指摘を修正して」）に能動的に使用する。
allowed-tools: Agent, Read, Write, Edit, Glob, Grep, Bash(grep:*), Bash(ls:*), Bash(find:*), Bash(mkdir:*), Bash(git log:*), Bash(git diff:*), Bash(git show:*), Bash(git add:*), Bash(git commit:*), Bash(git status:*), Bash(${CLAUDE_PLUGIN_ROOT}/scripts/fetch-diff.sh:*), Bash(${CLAUDE_PLUGIN_ROOT}/scripts/del-tmp.sh:*), Bash(python3 ${CLAUDE_PLUGIN_ROOT}/skills/respond/scripts/compile-review.py:*), Bash(python3 ${CLAUDE_PLUGIN_ROOT}/scripts/render-review.py:*)
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

- `--commit`（デフォルト OFF）— 修正後のソースコードをステップ 5 でコミットする。
- `--adr`（デフォルト OFF）— 実装時の設計判断にまだ ADR が無い場合に、修正サブエージェントが ADR ファイルを新規作成することを許可する（スケルトン: `${CLAUDE_PLUGIN_ROOT}/rules/adr-format.md`）。`Estimate:` メタデータから参照されている ADR ファイル（`/creview:triage --adr` が作成。ユーザーが編集している場合もある）の修正前の読み込みと修正後の更新は、このオプションに寄らず実行される。

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

本スキルは専門家エージェントを同梱しない。各指摘の assignee は `Triage:` メタデータ（`(assignee: {specialist})`）から読み取る。これは `/creview:triage` が**反映先プロジェクトの** `.claude/agents/` に対して記録したものである。リーダーはその assignee 名をそのまま `subagent_type` に渡す。assignee が存在しない、または解決できない場合は `general-purpose` を使う。ビルド／テスト修正専門家は、フォーマット・ビルド・テスト検証 Sub が反映先プロジェクトの `.claude/agents/`（または `general-purpose`）から解決する。

## 内部処理（中間ファイル）

各判定は中間ファイルに書き出し、`compile-review.py` が集約する。リーダー（あなた）は判定結果本文を context に載せない。

### 作業用ディレクトリ

```
{tmp_dir} = .claude/tmp/creview-respond-{timestamp}/
{tmp_dir}/targets.jsonl        ← select-fix-targets サブエージェントの出力
{tmp_dir}/statuses/{id}.jsonl  ← 修正サブエージェントの出力（指摘 1 件 1 ファイル）
{tmp_dir}/events.jsonl         ← compile-review.py の出力（render-review.py 入力）
```

書き出しには **Write ツール**を使う。Bash の cat heredoc は値内のアポストロフィ（例: `Won't`）でクォーティングが破綻するため使用不可。

ステップ 1 開始時にリーダー（あなた）が `mkdir -p {tmp_dir}/statuses` で `{tmp_dir}` を作成し、各サブエージェントに `{tmp_dir}` を渡す。

## ステップ 1 — 修正対象の選別（select-fix-targets サブエージェントへ委譲）

`Agent(subagent_type="general-purpose", prompt=...)` で起動する。Sub はレビュードキュメントを Read し、修正対象選別ルールを適用し、`{tmp_dir}/targets.jsonl` を Write する。

テンプレート `select-fix-targets.md`、`template_id` `7c3e9a1d-5b48-4f62-9a8c-2d6f1b3e7a95`、変数 `plugin_root = ${CLAUDE_PLUGIN_ROOT}`、`document_path = {document_path}`、`tmp_dir = {tmp_dir}`、オーバーライド `(該当なし)`。戻り値: `{path, fix_count, by_assignee: [{assignee, ids: [id, ...]}], template_id}` — 本文は読み込まない。

`fix_count == 0` の場合、ステップ 2〜5 をスキップしてステップ 6（編纂。反映するものなし → 「修正対象なし」を報告）へ進む。

## ステップ 2 — 修正（専門家サブエージェントへ並列委譲）

`by_assignee` の各 `{assignee, ids}` ごとに `Agent(subagent_type=assignee, prompt=...)` で修正サブエージェントを起動する。異なる assignee は並列起動する。同一 assignee 内の ids はテンプレートの並列化制約に従う。

テンプレート `fix.md`、`template_id` `2f8a1c5d-7b94-4e63-a1c8-5d3f9b2e7a14`、変数 `plugin_root = ${CLAUDE_PLUGIN_ROOT}`、`ids = {ids}`、`document_path = {document_path}`、`tmp_dir = {tmp_dir}`、`adr_flag = {on|off、--adr に従う}`、`timestamp = {timestamp}`、オーバーライド `(該当なし)`。各エージェントの戻り値: `{items: [{id, path}, ...], template_id}` — `items` のみを集め、status 本文は読み込まない。

## ステップ 3 — コメントレビュー（comment-sensei サブエージェントへ委譲）

修正サブエージェントが追加・変更したコメントが `${CLAUDE_PLUGIN_ROOT}/rules/comment.md` の規律に違反していないかを comment-sensei にレビューさせ、違反があれば修正させる。comment-sensei には今回の修正差分（`fetch-diff.sh` 出力）とレビュードキュメント（`{document_path}`）を渡し、変更されたコメントを把握しつつ各指摘の趣旨を棄損しない範囲で調整させる。追加・変更されたコメントが無い場合、サブエージェントは何もせず終了してよい。

リーダーは起動前に `${CLAUDE_PLUGIN_ROOT}/scripts/fetch-diff.sh HEAD {tmp_dir}/changes.txt` で修正差分を取得する。`Agent(subagent_type="comment-sensei", prompt=...)` で起動する。

テンプレート `comment-review.md`、`template_id` `4a8e2d6f-9b15-4c73-8a2d-7f1e5c9b3d68`、変数 `plugin_root = ${CLAUDE_PLUGIN_ROOT}`、`tmp_dir = {tmp_dir}`、`diff_path = {tmp_dir}/changes.txt`、`document_path = {document_path}`、オーバーライド `(該当なし)`。戻り値: `{reviewed_paths, fix_count, template_id}`。

## ステップ 4 — フォーマット・ビルド・テスト検証

リーダー（あなた）はフォーマッタやビルドコマンドを直接実行せず、ソースコードも読まない。フォーマット・ビルド・テスト検証 Sub は `${CLAUDE_PLUGIN_ROOT}/rules/build-format-detection.md` の手順（`build-format.md` 記述子をプロジェクト→ユーザー→プラグイン同梱スコープで再帰探索、無ければ `CLAUDE.md` → `README.md`）で反映先プロジェクトのフォーマット／ビルド／テスト手順を解決し、単発のフォーマット・ビルド・テスト実行のみ行う（テストはテスト手順が解決された場合のみ。いずれも解決できない場合は目視チェックのみとなり警告を返す）。Sub には今回の修正差分（`fetch-diff.sh` 出力）を渡し、変更内容がビルド／テストの結果に影響し得ない場合（コメントのみ等）は当該ステージを省略できる。ビルド／テスト失敗時はコードを読んで修正担当の専門家を判定して結果を返す（自分でコードは修正しない）。リーダーは専門家 Sub を起動して修正させ、ビルドとテストが通るまで検証 Sub と専門家 Sub を交互に再起動するループをオーケストレートする。

### ループ制御（リーダー）

最大試行回数: 5。以下を最大試行回数まで繰り返す:

1. `${CLAUDE_PLUGIN_ROOT}/scripts/fetch-diff.sh HEAD {tmp_dir}/changes.txt` で現在の修正差分（作業ツリー）を取得し、フォーマット・ビルド・テスト検証 Sub を `Agent(subagent_type="review-helper", prompt=...)` で起動する — テンプレート `format-build-verify.md`、`template_id` `9d3c5f8a-2b71-4e94-a8c5-1f7d3b9e2c46`、変数 `plugin_root = ${CLAUDE_PLUGIN_ROOT}`、`tmp_dir = {tmp_dir}`、`diff_path = {tmp_dir}/changes.txt`、`attempt_num = {attempt_num}`、オーバーライド `(該当なし)`。
2. 戻り値（`{path, success, format_violations_fixed, workflow_source, workflow_warning, summary_line, template_id}`）を受け取る。`workflow_warning` が非 null の場合はステップ 7 で提示するため保持する。
3. `success == true` ならループ終了。
4. `success == false` の場合:
   a. `{tmp_dir}/format-build-result.jsonl` を Read し、`failure` セクションから `suggested_specialist` / `error_summary` / `error_files` / `fix_guidance` / `log_path` を取得する（判定本体ではない operational data。ただしソースコード本体は Read しない）。
   b. `Agent(subagent_type=suggested_specialist, prompt=...)` でビルド／テスト修正専門家 Sub を起動する — テンプレート `build-fix.md`、`template_id` `6e2a9f5c-1d83-4b74-9c2e-5a8d3f1b7e29`、変数 `plugin_root = ${CLAUDE_PLUGIN_ROOT}`、`tmp_dir = {tmp_dir}`、オーバーライド `(該当なし)`。戻り値: `{description, template_id}`。
   c. ループの先頭に戻る（コードが書き変わっているのでフォーマット再確認が必要）。
5. 試行回数上限に達してもビルド／テストが通らない場合、ユーザーに `error_summary` を提示してループを抜け、ステップ 5 に進む。

## ステップ 5 — コミット（`--commit` 指定時のみ）

`--commit` が OFF の場合はこのステップをスキップする。この時点でソースコードは確定している — 修正、comment-sensei による調整、ビルド／テスト修正のすべてが作業ツリーにある。

1. ステップ 1 の `by_assignee` 単位が所有するファイルは、`{tmp_dir}/statuses/*.jsonl` のうちその単位の id が持つ `files` の和集合（`files` 配列のみを読む。判定本文ではなく運用データである）。各単位について、他の単位が所有していないファイルのみをステージングしてコミットする。
2. 作業ツリーに残った変更をまとめて最後の 1 コミットにする — 複数の単位が共有するファイルと、どの単位も所有しないファイルへの comment-sensei / ビルド修正の変更。残りが無ければこのコミットは作らない。
3. `git add -A` は使用しない。`{document_path}` および `{tmp_dir}` 配下はステージングしない。
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

リーダーはステップ 6 で受け取った `summary_line` をコンソールに表示する。ステップ 4 で `workflow_warning` を受け取っていた場合は、`summary_line` と併せて警告行として表示する。詳細テーブルが必要な場合のみ、更新後の `{document_path}` を Read し、`${CLAUDE_PLUGIN_ROOT}/skills/respond/templates/respond-summary.md` のフォーマットに従って表示する。
