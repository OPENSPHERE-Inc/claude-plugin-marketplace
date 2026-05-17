---
name: resolve
description: レビュー指摘の解決状況を実際のソースコードと照合して検証し、検証メタデータを書き戻す
allowed-tools: Agent, Read, Write, Edit, Glob, Grep, Bash(grep:*), Bash(ls:*), Bash(find:*), Bash(mkdir:*), Bash(git log:*), Bash(git diff:*), Bash(git show:*), Bash(git branch:*), Bash(${CLAUDE_PLUGIN_ROOT}/scripts/fetch-diff.sh:*), Bash(${CLAUDE_PLUGIN_ROOT}/scripts/rm-tmp.sh:*), Bash(python ${CLAUDE_PLUGIN_ROOT}/scripts/render-review.py:*)
---

# レビュー検証

あなたは**レビュー検証者**である。更新済みのレビュードキュメントを再読み込みし、各指摘の解決状況を実際のソースコードと照合して検証し、検証結果を `verification` メタデータとして書き戻す。

## 入力

ユーザーはレビュードキュメント（markdown）へのパスを指定する。引数が `$ARGUMENTS` の場合、レビュードキュメントへのパスとして解釈する。`--base {branch}` でベースブランチを指定できる（指定がなければリモートに存在する `main` または `master` を使用する。両方存在する場合は `main` を優先）。

## レビュードキュメント形式

レビュードキュメントは /creview:start が生成し、各 finding にメタデータマーカーを含む。/creview:triage と /creview:respond によって `triage` / `estimate` / `status` フィールドが追記されている前提:

```markdown
### {finding-id} — `{location}`

- **Reviewer:** {reviewer-name}

**Finding:**

{description}

<!-- METADATA({finding-id}) -->
- **Triage:** 🔧 Will Fix (assignee: cpp-sensei) — Valid finding
- **Estimate:** ▶️ Maintain — Cost: M, Future: S, Signals: b,d
- **Status:** 🟢 Fixed — Added null check
<!-- /METADATA({finding-id}) -->

---
```

各 finding の現在の状態は、マーカー間に存在する各フィールドから判定する:

- マーカー間が空 → 未トリアージ。
- `Triage: 🔧 Will Fix` のみ → トリアージ済み、見積未完了。
- `Triage: 🚫 Won't Fix` → 対応不要として確定。
- `Estimate: ▶️ Maintain` で `Status:` なし → 見積済み、修正未完了。
- `Estimate: 🔻 Downgrade` → 見積段階で対応不要に倒れた。
- `Estimate: 🚧 Alternative` で `Status:` なし → 見積段階で代替対応に倒れた、FIXME 付与未完了。
- `Status: 🟢 Fixed` → 修正完了（Maintain 修正、または Alternative の FIXME 付与）。

/creview:resolve は `verification` フィールドを以下のいずれかの形式で追記する:

- `✅ Verified — {検証結果の簡潔な説明}` — 解決済み（Resolved）。
- `💬 Feedback — {不足点と完全解決のために必要なこと}` — フィードバック必要（Feedback）。

Unresolved の指摘には `verification` 値を書き込まない。

### 値の制約

- 単一行のみ（改行不可）。長い説明はドキュメントの他のセクション（フィードバック詳細など）に書き、メタデータ値は要約に留める。
- 削除不可（追記のみ）。

## サブエージェント共通指示

共通禁止事項は `${CLAUDE_PLUGIN_ROOT}/rules/sub-agent.md` を参照。各サブエージェントへのプロンプト本体は `templates/*.md` の外部テンプレートに格納されている（frontmatter に `template_id` を持つ）。リーダーは Agent ツール起動時に「テンプレートを Read して指示に従う」旨の起動プロンプトに変数値を埋めて渡す。サブエージェントは戻り値に `template_id` を含める。リーダーは戻り値の `template_id` が各ステップで指定されている UUID（後述、各ステップにハードコード）と一致することを確認し、不一致の場合は当該サブエージェントを再起動する。

起動プロンプトの完全性に関する規約は `${CLAUDE_PLUGIN_ROOT}/rules/sub-agent.md` § 起動プロンプトの完全性を参照。

## 内部処理（中間ファイル）

リーダー（あなた）は検証本文を context に載せない。

### 作業用ディレクトリ

```
{tmp_dir} = .claude/tmp/creview-resolve-{timestamp}/
{tmp_dir}/diff.txt                 ← リーダーがステップ 1 で取得する差分（検証サブエージェント入力）
{tmp_dir}/verifications/{id}.json  ← 検証サブエージェントの出力（指摘 1 件 1 ファイル）
{tmp_dir}/events.jsonl             ← 編纂サブエージェントの出力（render-review.py 入力）
{tmp_dir}/resolve-summary.md       ← 編纂サブエージェントの出力（検証レポート）
```

作成はステップ 1、削除はリーダーがステップ 4 で `${CLAUDE_PLUGIN_ROOT}/scripts/rm-tmp.sh {tmp_dir}` で行う。

### events.jsonl

events.jsonl は `{tmp_dir}/events.jsonl` に置く。形式:

```jsonl
{"id":"C-1","field":"verification","value":"✅ Verified — Null チェックの修正は正確"}
{"id":"M-1","field":"verification","value":"💬 Feedback — 85 行目の else 分岐で LOG_ERROR が抜けている"}
```

書き出しには **Write ツール**を使う。Bash の cat heredoc は値内のアポストロフィ（例: `Won't`）で外側のクォーティングが破綻するため使用不可。

**Unresolved** の指摘（トリアージ未実施 / 見積未完了 / 修正未完了）は events.jsonl に書き込まない（verification を付ける段階にない）。

## ステップ 1 — 差分取得と解析（解析サブエージェントへ委譲）

リーダー（あなた）は差分内容を Read しない。差分なしでは検証が不十分になるため、リーダーが差分をファイルに取得し、検証サブエージェントに渡す。

1. ベースブランチを特定する（入力の `--base` 指定値。指定がなければリモートに存在する `main` または `master`。両方存在する場合は `main` を優先）。
2. `mkdir -p {tmp_dir}/verifications` で `{tmp_dir}` を作成する。
3. 差分をスクリプトで `{tmp_dir}/diff.txt` に取得する:
   ```
   ${CLAUDE_PLUGIN_ROOT}/scripts/fetch-diff.sh {base} {tmp_dir}/diff.txt
   ```
4. 解析サブエージェントを `Agent(subagent_type="review-helper", prompt=...)` で起動する。タスク固有の指示は `templates/analyze.md` 外部テンプレートに格納されている。起動プロンプト例:

```
最初の行動として `${CLAUDE_PLUGIN_ROOT}/skills/resolve/templates/analyze.md` を必ず Read する。Read 完了前に他の判断・行動・ツール呼び出しを行わない。Read 後はその指示に従う。

変数（テンプレート中の {{...}} placeholder を置換）:
- plugin_root: ${CLAUDE_PLUGIN_ROOT}
- document_path: {document_path}

ラウンド固有のオーバーライド（テンプレートの指示に従った後に適用）:
- (該当なし)

戻り値に template_id（テンプレートの frontmatter から Read）を含める。
```

サブエージェントから戻り値（`{total, by_assignee, template_id}`）を受け取る。`template_id` が `5d9e2c8a-1f74-4b63-a9d8-3c5f7e1b9a42` と一致することを確認する。一致しない場合はサブエージェントを再起動する。

## ステップ 2 — 各指摘の検証（specialist 単位で並列委譲）

ステップ 1 の `by_assignee` をループし、各 `{assignee, ids}` ごとに `Agent(subagent_type=assignee, prompt=...)` で検証サブエージェントを並列起動する（agent 定義の persona と専門観点が自動ロードされる）。

起動プロンプト例（persona は含めない）。タスク固有の指示は `templates/verify.md` 外部テンプレートに格納されている:

```
最初の行動として `${CLAUDE_PLUGIN_ROOT}/skills/resolve/templates/verify.md` を必ず Read する。Read 完了前に他の判断・行動・ツール呼び出しを行わない。Read 後はその指示に従う。

変数（テンプレート中の {{...}} placeholder を置換）:
- plugin_root: ${CLAUDE_PLUGIN_ROOT}
- ids: {ids}
- document_path: {document_path}
- tmp_dir: {tmp_dir}
- diff_path: {tmp_dir}/diff.txt

ラウンド固有のオーバーライド（テンプレートの指示に従った後に適用）:
- (該当なし)

戻り値に template_id（テンプレートの frontmatter から Read）を含める。
```

各検証エージェントから戻り値（`{items: [{id, outcome}, ...], template_id}`）を受け取る。`template_id` が `8a1f5c9b-2e73-4d64-9c1e-8b3d7f2a5e94` と一致することを確認する。一致しない場合は当該エージェントを再起動する。**verification 本文は context に載せない**（戻り値は `items` のみ）。

## ステップ 3 — 検証レポートと反映（編纂サブエージェントへ委譲）

リーダー（あなた）は検証本文を context に載せない。

起動手順:

1. `Agent(subagent_type="review-helper", prompt=...)` で新しいサブエージェントを起動する。タスク固有の指示は `templates/compile.md` 外部テンプレートに格納されている。起動プロンプト例:

```
最初の行動として `${CLAUDE_PLUGIN_ROOT}/skills/resolve/templates/compile.md` を必ず Read する。Read 完了前に他の判断・行動・ツール呼び出しを行わない。Read 後はその指示に従う。

変数（テンプレート中の {{...}} placeholder を置換）:
- plugin_root: ${CLAUDE_PLUGIN_ROOT}
- tmp_dir: {tmp_dir}
- document_path: {document_path}

ラウンド固有のオーバーライド（テンプレートの指示に従った後に適用）:
- (該当なし)

戻り値に template_id（テンプレートの frontmatter から Read）を含める。
```

2. 編纂サブエージェントから戻り値（`{summary_path, summary_line, resolved_count, feedback_count, unresolved_count, template_id}`）を受け取る。`template_id` が `1c5e8b2f-7d34-4a96-b8c1-5e9a3f7d2c84` と一致することを確認する。一致しない場合はサブエージェントを再起動する。

## ステップ 4 — 完了報告とクリーンアップ

1. リーダーは編纂サブエージェントから受け取った `summary_line` をコンソールに表示する。
2. 詳細レポートが必要な場合のみ `summary_path`（`{tmp_dir}/resolve-summary.md`）を Read する。
3. リーダーが `{tmp_dir}` を一括削除する:
   ```bash
   ${CLAUDE_PLUGIN_ROOT}/scripts/rm-tmp.sh {tmp_dir}
   ```
