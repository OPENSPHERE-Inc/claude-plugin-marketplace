---
name: triage
description: レビュー指摘事項のトリアージと修正コストの見積を行い、トリアージ / 見積メタデータをレビュードキュメントに永続化する（ソース修正は行わない）。/creview:start のレビュードキュメントが存在し、どの指摘に対応するかの判断や修正コストの見積が次の作業となるときに能動的に使用する。
allowed-tools: Agent, Read, Write, Edit, Glob, Grep, Bash(grep:*), Bash(ls:*), Bash(find:*), Bash(mkdir:*), Bash(git log:*), Bash(git diff:*), Bash(git show:*), Bash(${CLAUDE_PLUGIN_ROOT}/scripts/rm-tmp.sh:*), Bash(python3 ${CLAUDE_PLUGIN_ROOT}/skills/triage/scripts/compile-review.py:*), Bash(python3 ${CLAUDE_PLUGIN_ROOT}/scripts/render-review.py:*)
---

# レビュートリアージ & 見積

あなたは**トリアージリーダー**として、レビュードキュメントを処理し、一次トリアージを別サブエージェントに委譲し、Will Fix 指摘について専門家サブエージェントに見積を実施させ、統合サマリを生成し、`triage` / `estimate` メタデータを `render-review.py` 経由でレビュードキュメントに永続化する。

トリアージリーダー自身はトリアージや見積作業を担わず、プロセスのオーケストレーションとその成果の集約・判断を行う。トリアージと見積作業はすべてサブエージェントに委任する。

修正フェーズは別スキル（`/creview:respond`）である。本スキルはトリアージ / 見積の判定をドキュメントに永続化した時点で停止し、修正前にユーザーがそれらを確認できるようにする。

## 入力

ユーザーはレビュードキュメント（markdown）へのパスを指定する。引数が `$ARGUMENTS` の場合、レビュードキュメントへのパスとして解釈する。

## タイムスタンプ（`{timestamp}`）

`{timestamp}` はステップ 1 の開始時に一度だけ決定する現在日時文字列（`YYYYMMDD-HHMMSS` 形式、例: `20240101-120000`）。以降の全ステップで同一値を使う。

## レビュードキュメント形式

レビュードキュメントは `/creview:start` が生成し、各 finding にメタデータマーカー（`<!-- METADATA({finding-id}) -->` 〜 `<!-- /METADATA({finding-id}) -->`）を含む:

```markdown
### {finding-id} — `{location}` [{categories}]

- **Reviewer:** {reviewer name}

**Finding:**

{description of the issue}

<!-- METADATA({finding-id}) -->
<!-- /METADATA({finding-id}) -->

---
```

`{categories}` は `/` 区切りで連結された 1 つ以上のカテゴリラベル（例: `バグ`、`保守性/可読性`）。レビュアー出力にカテゴリが欠落していた場合は括弧自体が省略される。

本スキルはマーカーの間に以下のフィールドを追加する:

- `triage`（ステップ 1）— 値の形式: `🔧 Will Fix (assignee: {specialist}) — {判定理由}` / `🚫 Won't Fix — {対応不要の理由}`。
- `estimate`（ステップ 2）— 値の形式: `▶️ Maintain — Cost: {S/M/L}, Future: {S/M/L}, Signals: {none\|a,b,c,d,e,f} — Plan: (1) {file:line — 変更} (2) ...` / `🔻 Downgrade — Cost: ..., Future: ..., Signals: ... — {格下げ理由}` / `🚧 Alternative — Cost: ..., Future: ..., Signals: ... — FIXME 付与: {方向性} — Plan: (1) {file:line — FIXME 文言} ...`。` — Plan: ` は Maintain / Alternative のみに付加し、見積で確定した修正プランを単一行に畳んだもの（Downgrade には付かない）。

`status`（設定者: `/creview:respond`）と `verification`（設定者: `/creview:resolve`）は本スキルの対象外である。

### 値の制約

- 単一行のみ（改行不可）。長い rationale は finding 本文側に書き、メタデータ値は要約に留める。例外として `estimate` の ` — Plan: ` セグメントは要約せず fix_plan 全エントリを保持する。単一行制約は維持し、各エントリは ` (n) ` 番号マーカーで連結し改行を含めない。
- 追記のみ（削除不可）。同 (id, field) は last write wins。

### 絵文字対応表

- `triage` / `Will Fix` → 🔧（修正対象として確定）
- `triage` / `Won't Fix` → 🚫（対応不要として確定）
- `estimate` / `Maintain` → ▶️（トリアージ判定を維持し修正に進む）
- `estimate` / `Downgrade` → 🔻（トリアージ判定を覆して修正しない、代替手段なし）
- `estimate` / `Alternative` → 🚧（トリアージ判定は覆るが FIXME コメント付与等のより軽い手段で代替）

## サブエージェント共通指示

共通禁止事項は `${CLAUDE_PLUGIN_ROOT}/rules/sub-agent.md` を参照。各サブエージェントへのプロンプト本体は `templates/*.md` の外部テンプレートに格納されている（frontmatter に `template_id` を持つ）。リーダーは Agent ツール起動時に「テンプレートを Read して指示に従う」旨の起動プロンプトに変数値を埋めて渡す。サブエージェントは戻り値に `template_id` を含める。リーダーは戻り値の `template_id` が各ステップで指定されている UUID（後述、各ステップにハードコード）と一致することを確認し、不一致の場合は当該サブエージェントを再起動する。

起動プロンプトの完全性に関する規約は `${CLAUDE_PLUGIN_ROOT}/rules/sub-agent.md` § 起動プロンプトの完全性を参照。

### 専門家エージェントの解決

本スキルは専門レビュアー / 修正エージェントを同梱しない。トリアージサブエージェントは `${CLAUDE_PLUGIN_ROOT}/rules/agents-detection.md` の手順で指摘ごとに担当を解決する（マッチ対象＝指摘内容、記録先＝assignee）。リーダーは解決された担当エージェント名をステップ 2 の `subagent_type` にそのまま渡す。

## 内部処理（中間ファイル）

各判定は中間ファイルに書き出し、`compile-review.py` が集約する。リーダー（あなた）は判定結果本体を context に載せない。

### 作業用ディレクトリ

```
{tmp_dir} = .claude/tmp/creview-triage-{timestamp}/
{tmp_dir}/triage.json          ← トリアージサブエージェントの出力
{tmp_dir}/estimates/{id}.json  ← 見積サブエージェントの出力（指摘 1 件 1 ファイル）
{tmp_dir}/events.jsonl         ← compile-review.py の出力（render-review.py 入力）
```

各サブエージェントは description / location / 既存メタデータ等の指摘本体情報を、`id` をキーにレビュードキュメントの METADATA マーカー前後から直接 Read して取得する。

### events.jsonl

最終的な markdown 反映には `{tmp_dir}/events.jsonl` を使う。生成は `compile-review.py` が中間 JSON（triage.json / estimates/*.json）の `memo_value` から行う。形式:

```jsonl
{"id":"C-1","field":"triage","value":"🔧 Will Fix (assignee: cpp-sensei) — reason"}
{"id":"C-1","field":"estimate","value":"▶️ Maintain — Cost: M, Future: S, Signals: b,d — Plan: (1) src/foo.cpp:42 — null チェック追加"}
```

### 一時ディレクトリの作成

ステップ 1 開始時にリーダー（あなた）が `mkdir -p {tmp_dir}/estimates` で `{tmp_dir}` を作成し、各サブエージェントに `{tmp_dir}` を渡す。

## ステップ 1 — トリアージ（トリアージサブエージェントへ委譲）

トリアージは**修正作業を行う専門エージェントとは別個の単一サブエージェント**に委譲する（バイアス分離のため）。トリアージ Sub はレビュードキュメントを直接 Read して指摘抽出とステージ判定およびトリアージ判定を一段で行う。判定結果は**ファイルに Write** させ、リーダーの context に判定本体を載せない。

1. `Agent(subagent_type="general-purpose", prompt=...)` でサブエージェントを起動する。モデル指定はしない。タスク固有の指示は `templates/triage.md` 外部テンプレートに格納されている。起動プロンプト例:

```
最初の行動として `${CLAUDE_PLUGIN_ROOT}/skills/triage/templates/triage.md` を必ず Read する。Read 完了前に他の判断・行動・ツール呼び出しを行わない。Read 後はその指示に従う。

変数（テンプレート中の {{...}} placeholder を置換）:
- plugin_root: ${CLAUDE_PLUGIN_ROOT}
- document_path: {document_path}
- tmp_dir: {tmp_dir}
- previous_round_doc_paths: {previous_round_doc_paths}（標準フローでは "(none)"。/creview:rounds 等の上位フローから過去ラウンドの doc_path 一覧が渡される場合のみ非空）

ラウンド固有のオーバーライド（テンプレートの指示に従った後に適用）:
- (none)

戻り値に template_id（テンプレートの frontmatter から Read）を含める。
```

2. 戻り値（`{path, will_fix_count, wontfix_count, by_stage, by_assignee, template_id}`）を受け取る。triage の本文は読み込まない。
3. `template_id` が `1e9c4f7a-5b82-4d63-a1c8-3f7d2e9b4a15` と一致することを確認する。一致しない場合はサブエージェントを再起動する。
4. トリアージサマリ（件数）をユーザーに提示する。

`will_fix_count == 0` の場合、ステップ 2 をスキップしてステップ 3（編纂。Won't Fix の triage 値のみ永続化）へ進む。

## ステップ 2 — 見積（専門家サブエージェントへ並列委譲）

ステップ 1 で受け取った `by_assignee` 配列をループする。各 `{assignee, ids}` ごとに `Agent(subagent_type=assignee, prompt=...)` で専門家サブエージェントを並列起動する。各サブエージェントは担当 ids を一括見積し、id ごとに `{tmp_dir}/estimates/{id}.json` を Write する。

1. 起動プロンプト例（persona は含めない）。タスク固有の指示は `templates/estimate.md` 外部テンプレートに格納されている:

```
最初の行動として `${CLAUDE_PLUGIN_ROOT}/skills/triage/templates/estimate.md` を必ず Read する。Read 完了前に他の判断・行動・ツール呼び出しを行わない。Read 後はその指示に従う。

変数（テンプレート中の {{...}} placeholder を置換）:
- plugin_root: ${CLAUDE_PLUGIN_ROOT}
- ids: {ids}
- document_path: {document_path}
- tmp_dir: {tmp_dir}

ラウンド固有のオーバーライド（テンプレートの指示に従った後に適用）:
- (none)

戻り値に template_id（テンプレートの frontmatter から Read）を含める。
```

2. すべての見積エージェントから戻り値（`{items: [{id, verdict}, ...], template_id}`）を受け取る。各エージェントの `template_id` が `8b2d5f1c-7a93-4e64-b8d1-2c5e9a3f7b48` と一致することを確認する。一致しない場合は当該エージェントを再起動する。estimate の本文は読み込まない。

3. 見積結果サマリ（レビュー + トリアージ + 見積を 1 枚に統合したテーブル + レビュードキュメントへのリンク）を生成するため、集約サブエージェントを `Agent(subagent_type="review-helper", prompt=...)` で起動する。

```
最初の行動として `${CLAUDE_PLUGIN_ROOT}/skills/triage/templates/estimate-summary.md` を必ず Read する。Read 完了前に他の判断・行動・ツール呼び出しを行わない。Read 後はその指示に従う。

変数（テンプレート中の {{...}} placeholder を置換）:
- plugin_root: ${CLAUDE_PLUGIN_ROOT}
- tmp_dir: {tmp_dir}
- document_path: {document_path}

ラウンド固有のオーバーライド（テンプレートの指示に従った後に適用）:
- (none)

戻り値に template_id（テンプレートの frontmatter から Read）を含める。
```

戻り値（`{summary_path, summary_line, maintain_count, downgrade_count, alternative_count, template_id}`）を受け取る。`template_id` が `5c1e9b7a-3d48-4a96-b8e2-7f3c5a1d4b29` と一致することを確認する。一致しない場合はサブエージェントを再起動する。リーダーは `summary_line` だけを context に保持し、テーブル本体は載せない。

## ステップ 3 — レビュードキュメントへの反映

リーダー（あなた）は判定本体を context に載せない。トリアージ / 見積判定は `compile-review.py` が中間 JSON から集約し events.jsonl 経由で markdown に反映する（`status` / `verification` は対象外）。

1. 次を実行する（CWD はプロジェクトルート）:

   ```bash
   python3 ${CLAUDE_PLUGIN_ROOT}/skills/triage/scripts/compile-review.py {tmp_dir} {document_path}
   ```

2. stdout の結果 JSON（`{fixed_count, code_changed, summary_line, will_fix, wont_fix, maintain, alternative, downgrade}`）を受け取る。`fixed_count` は常に 0（本スキルは status を書き込まない）。`triage` / `estimate` フィールドのみ反映される。

## ステップ 4 — サマリーと後片付け

1. リーダーは見積集約サブエージェントから受け取った `summary_line` をコンソールに表示し、続けて次を表示する: 「トリアージ / 見積を `{document_path}` に永続化しました。Maintain / Alternative 指摘を修正するには `/creview:respond {document_path}` を実行してください。」
2. 詳細テーブルが必要な場合のみ `summary_path` を Read する。
3. リーダーが `{tmp_dir}` を一括削除する:
   ```bash
   ${CLAUDE_PLUGIN_ROOT}/scripts/rm-tmp.sh {tmp_dir}
   ```
