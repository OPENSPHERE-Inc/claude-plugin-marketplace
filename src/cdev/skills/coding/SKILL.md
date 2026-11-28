---
name: coding
description: ペアレビューセルを用いて、設計セルステップ・コーディングセルステップ・QA ゲートでコーディングタスクをエンドツーエンドに統括する、常駐エージェントチーム方式のワークフロー。AI 向けプロンプトファイルには、コーディングセルでのプロンプト規律セルフチェックと圧縮、QA ゲートでの解釈テストも行う。reviewer は対象プロジェクトのエージェントから自動選定する。ユーザーがリポジトリ内での機能の実装・変更の構築・コーディングタスクの遂行を求めたとき、リポジトリ内の AI 向けプロンプトファイル（エージェント定義・SKILL.md・ルール・スラッシュコマンド・プロンプトテンプレート）の作成や修正を含め、能動的に使用する。リポジトリ外のファイル（`~/.claude/` 配下など）、1 体のエージェントで直接済む小さな編集（ルールへの 1 項目の追記など）、ファイルになっていないプロンプトの起草、`--worktree` なしでの未コミットの変更がある作業ツリーには使わない。バックグラウンドのサブエージェント（Agent の run_in_background）とエージェント間メッセージング（SendMessage）が利用可能なランタイムを要する。
allowed-tools: Agent, SendMessage, TaskStop, TodoWrite, Read, Write, Glob, Grep, Bash(cd:*), Bash(mkdir:*), Bash(grep:*), Bash(ls:*), Bash(git log:*), Bash(git diff:*), Bash(git show:*), Bash(git status:*), Bash(git branch:*), Bash(git rev-parse:*), Bash(git add:*), Bash(git commit:*), Bash(git reset -q), Bash(${CLAUDE_PLUGIN_ROOT}/scripts/fetch-diff.sh:*), Bash(${CLAUDE_PLUGIN_ROOT}/scripts/del-tmp.sh:*), Bash(${CLAUDE_PLUGIN_ROOT}/scripts/worktree.sh:*), Bash(${CLAUDE_PLUGIN_ROOT}/scripts/restore.sh:*), Bash(python3 ${CLAUDE_PLUGIN_ROOT}/scripts/check-jsonl.py:*), Bash(python3 ${CLAUDE_PLUGIN_ROOT}/scripts/commit-plan.py:*)
---

# マルチエージェントコーディング

あなたは**コーディングリーダー（チームリード）**として、常駐チームを編成し、設計・コード・ドキュメントの 3 種類のセルと最終 QA ゲートを通してコーディングタスクを駆動する。セルでは、producer（architect、coder、または writer）とペアの reviewer が自律的なレビューループを回し、自分たちのセルを閉じる。あなたはセルを立ち上げ、ステップゲートと QA ゲートを強制し、エスカレーションを裁定する。ドキュメントファイル（`${CLAUDE_PLUGIN_ROOT}/rules/teammate.md` § ドキュメントファイル の定義による）は、コードセルがすべてクローズした後にドキュメントセルで、コードを持たない writer が書く。AI 向けプロンプトファイル（`${CLAUDE_PLUGIN_ROOT}/rules/prompt.md` の定義による）は設計セルとコードセルを通る。加えて `prompt-sensei` がそのコードセルでセルフチェックと圧縮を行い、QA ゲートで解釈をテストする。

リーダーはコードとドキュメントについて、設計・記述・レビュー・修正を行わない。

## 動作要件

このスキルは、バックグラウンドのサブエージェント（`Agent` の `run_in_background`）とチームメイト間メッセージング（`SendMessage`）を使用し、それらが利用可能なランタイムでのみ動作する。いずれかが利用できない場合は続行せず、動作要件を満たさない旨をユーザーへ報告して中止する。teammate がサブエージェントを起動できるかどうか（`prompt-sensei` が AI 向けプロンプトファイルの解釈テスト担当を Agent ツールで起動するのに要する）は中止の理由にしない: 起動できない場合は、解釈テストがそのファイルを未テストとして記録する。

## 信頼前提

QA ゲートは反映先リポジトリのビルド定義（`build-format.md` / `CLAUDE.md` / `README.md`）から導出したコマンドをフルシェル権限で literal 実行する。出所を信頼できないリポジトリでは本スキルを使用しない。信頼できないと判断した場合はタスクを開始せず、理由を添えてユーザーへ報告して中止する。

## 入力

ユーザーはコーディングタスクを与える: 実装する機能、行う変更、または修正するバグであり、対象パスや言語が付随する場合もある。引数が `$ARGUMENTS` の場合、それを（オプションを含む）タスク指定として解釈する。

## オプション

- `--review-rounds N`（デフォルト 5、範囲 1–10）— セルごとのレビュー ⇄ triage の最大反復回数。
- `--qa-attempts N`（デフォルト 5、範囲 1–10）— QA 検証 ⇄ 修正の最大試行回数。
- `--strict-docs`（デフォルト OFF）— セルの reviewer が、人向けテキスト（ドキュメントファイルと人向けコメント）にある指摘を、セルの最初のレビューだけでなく各ラウンドで新たに挙げるようにする（ステップ 3-4 の `strict_docs`）。
- `--commit`（デフォルト OFF）— QA 通過後、実装を論理的な変更ごとのコミットに分けてコミットする（ステップ 5）。
- `--worktree[=branch]`（デフォルト OFF）— タスクを `branch` 上の別の git ワークツリーで実行する（§ ワークツリー）。`=branch` を省略すると、現在の HEAD から新しいブランチ `cdev-coding-{timestamp}` を作成する。`--commit` を有効にする。
- `--output {dir}` — 設計ドキュメントの出力先ディレクトリ（`{design_dir}`）を指定する。
- `--handoff {path}`（デフォルト 未指定）— この実行への申し送り。書式を問わない Markdown ファイル。team-analysis、architect、設計 reviewer がこれを Read する。判断優先度ではタスクの次に位置し（§ レビューセルプロトコル）、`--worktree` 指定時は、設計はこれが挙げるターニングポイントへファイルを復元してよい。
- `--team-tag {tag}`（デフォルト 未指定）— すべての teammate の name に `-{tag}` を付ける（§ チームモデル）。`tag` は英数字とハイフンからなる 1〜16 文字で、英数字で始まる。このタグをセッション内の以前の実行が使っていないことは呼び出し側が保証し、スキルは検証しない。
- `--commit-always`（デフォルト OFF）— `--commit` を含意し、実行がステップ 4 に入っていれば、QA と解釈テストの結果にかかわらずステップ 5 でコミットする。
- `--result {path}`（デフォルト 未指定）— 実行の結果を JSON で `path` に書く（§ 結果ファイル）。

### 出力先（`{design_dir}`）

- `--output` 指定があればその値。
- 指定がない場合のデフォルト: `.claude/tmp/cdev-coding-{timestamp}-design/`。`{tmp_dir}` 配下には置かない（ステップ 5 で削除されるため）。

### 結果ファイル（`--result`）

Write ツールで 1 つの JSON オブジェクトを 1 行で書く。既存のファイルは置き換え、親ディレクトリがなければ作る。ファイルが既にある場合は先に Read する: Write は、このセッションで Read していないファイルの置き換えを拒否する。ステップ 5 の手順 5 で書くほか、ステップ 5 に至らないあらゆる終了 — § 動作要件 と § 信頼前提 による中止、およびステップ 1 での各終了 — でも、終了する前に書く。ワークツリーのセットアップ後の終了では、ティアダウンの後に書く。`.claude` か `.claude/tmp` がシンボリックリンクの間は書かない: ステップ 1 手順 5 の `del-tmp.sh` を通過する前の終了では、先に `${CLAUDE_PLUGIN_ROOT}/scripts/del-tmp.sh --dry {tmp_dir}` を実行し（ステップ 1 より前の終了では、その時点で `{timestamp}` を確定する）、ゼロ終了したときだけ書き、非ゼロ終了の場合はそのエラーをコンソールに表示して終了する。書いたファイルを `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/check-jsonl.py {path}` で検証する。エラーなら修正して、もう 1 度だけ検証する。書き込みか 2 度目の検証が失敗した場合は、エラーをコンソールに表示し、それ以外は何も変えない。

```json
{"committed": true, "commit": "<sha>", "commit_count": 1, "commit_warning": null,
 "branch": "<name>",
 "design_paths": ["<abs path>"], "restored_from": ["<turning point name>"],
 "restore_refused": [{"turning_point": "<name>", "path": "<path>", "reason": "<reason>"}],
 "doc_departures": [{"path": "<path>", "departure": "<string>"}],
 "qa": {"passed": true, "environmental": false, "summary": "<summary_line>"},
 "prompt_test": {"passed": true, "failed": ["<path>"],
                 "untested": [{"path": "<path>", "reason": "<reason>"}]},
 "fixme_count": 0, "escalations": 0, "team_fallback": false, "docs_unwritten": false,
 "aborted": null, "kept_worktree": null}
```

- `committed`: ステップ 5 の手順 1 でコミットを作った場合に true、それ以外は false。
- `commit`: ステップ 5 の手順 1 で作った最後のコミットの SHA。それ以外は null。
- `commit_count`: ステップ 5 の手順 1 で作ったコミットの数。`commit-plan.py commit` の分とフォールバックのコミットを合わせて数える。作らなかった場合は 0。
- `commit_warning`: null、または次のうち起きたものを述べる文字列: フォールバックとその理由、`commit-plan.py commit` の `tree_match` が false だったこと、フォールバックのコミットの失敗。
- `branch`: ソースが載るブランチ — `--worktree` 指定時は `worktree.sh` の `branch=`、それ以外は `{start_branch}`。detached `HEAD` の場合と、その値が分かる前に実行が終わった場合は null。
- `design_paths`: `{design_paths}` を絶対パスで。ステップ 2 の手順 3 のゲートを通過しなかった場合は空配列。
- `restored_from`: `{restored_from}`。ない場合は空配列。
- `restore_refused`: `{restore_refused}`。ない場合は空配列。
- `doc_departures`: ステップ 5 の時点の `{doc_departures}`。ない場合は空配列。
- `qa`: 最後の QA 試行の `success`、`environmental`、`{summary_line}`。ステップ 4 が QA の報告を 1 つも受けなかった場合は `false`、`false`、null。
- `prompt_test`: ステップ 4 の最後の試行の `{prompt_pass}`、`{prompt_failed_files}`、`{prompt_untested_files}`（未テストのファイルはそれぞれ理由を添え、解釈テストが結果を書かなかった場合は `path` を null とした要素 1 つとする）。ステップ 4 のどの試行もこれらを設定しなかった場合は `false` と空配列。
- `fixme_count`: 未解決項目のために残した `FIXME:` の数 — ラウンド上限でクローズしたセルが未解決の `Critical` に残したと報告したものと、裁定できなかったエスカレーションのために挿入させたもの。コードから数えた数ではない。
- `escalations`: 受けたエスカレーションの数。
- `team_fallback`: チームの再編成がステップ 1 のロスターにフォールバックした場合に true。
- `docs_unwritten`: ステップ 3 の手順 4 が、設計が挙げるドキュメントファイルの writer を見つけられなかった場合に true。
- `aborted`: ステップ 4 を終えてステップ 5 に来た場合は null。それ以外は `{"step": <1-4>, "reason": "<string>"}` で、実行が止まったステップを示す。§ 動作要件 と § 信頼前提 による中止はステップ 1 とする。
- `kept_worktree`: ティアダウンで残したワークツリーのパス。それ以外は null。
- `reason`、`summary`、`commit_warning`、`departure` は `{doc_lang}` で書く。

## 出力言語

設計ドキュメントと指摘の説明はユーザーのチャット言語で記述する。リーダーは現在のチャット言語を `{doc_lang}` として確定し、spawn 時にすべての teammate へ渡す。構造アンカー（重要度ラベル `Critical` / `Major` / `Minor` / `Info`、JSON フィールド名）は `{doc_lang}` に関わらず変更しない。

## タイムスタンプ（`{timestamp}`）

`{timestamp}` はステップ 1 の開始時に一度だけ確定する日時文字列（`YYYYMMDD-HHMMSS` 形式）で、以降の全ステップで再利用する。

## ワークツリー（`--worktree`）

`--worktree` 指定時、ソースの変更とコミットは別の git ワークツリー内でのみ行い、メイン作業ツリーのソースには触れない。実行が使う `.claude/`（`{tmp_dir}`、設計ドキュメント、プロジェクトの agents / rules）はメイン作業ツリーのものとする。

セットアップ:

1. `${CLAUDE_PLUGIN_ROOT}/scripts/worktree.sh create {branch}` を実行する（`{branch}`: オプションの値またはそのデフォルト）。出力される `main_root=` / `worktree_path=` / `branch=` の各行を 3 つとも保持する。非ゼロ終了した場合はそのエラーを表示してスキルを終了する。
2. Bash の `cd {worktree_path}` でセッションをワークツリーへ移す。以降に spawn する teammate はそこで作業する。続けて別の Bash 呼び出しで `git rev-parse --show-toplevel` が `{worktree_path}` を出力することを確認し、出力しない場合は作業ディレクトリが持続していないので、ティアダウンを実行して終了する。ティアダウンまでは、ほかに素の `cd` を実行しない: セッション全体と以降に起動するサブエージェントの作業ディレクトリが動く。別のディレクトリにはコマンド自身のオプション（例: `git -C dir`）かサブシェルで到達する。`EnterWorktree` / `ExitWorktree` は使わない: その隔離はワークツリー外（メイン作業ツリーの `.claude/tmp/` を含む）への Write / Edit を拒否する。

パスの基点: `{tmp_dir}`、デフォルトの `{design_dir}`、相対パスの `--output`・`--handoff`・`--result` は、セットアップ後は `{main_root}` を基点に解決する。セットアップより前と、`--worktree` を指定しない実行の全体では、`git rev-parse --show-toplevel` の出力を基点に解決する。これはセットアップが `main_root=` として出力するパスと同じである。ステップ 1 手順 1 の `--handoff` の確認と、そこでの終了時に書く結果ファイルもこれに従い、サブディレクトリで開始したセッションも含む。タスク指定はそのまま team-analysis へ渡す。teammate は `${CLAUDE_PLUGIN_ROOT}/rules/teammate.md` に従ってそのパスを `{target_dir}` 基準で解決し、`{target_dir}` 外の絶対パスは読み取り専用の参照とする。`--worktree` を指定しない場合、`{main_root}` は `(none)` とする。

ティアダウン — セットアップ後のあらゆる終了経路で、起動した teammate を停止（Step 5 の手順 2）してから実行する:

1. Bash の `cd {main_root}` でセッションを戻す。
2. `${CLAUDE_PLUGIN_ROOT}/scripts/worktree.sh remove {worktree_path}` を実行する。未コミットの変更があるワークツリーは残して非ゼロ終了するので、その場合はそのワークツリーのパスを報告する。

## チームモデル

セッションは単一の暗黙チームを持つ（明示的な作成・削除は不要）。各 teammate はバックグラウンドの永続サブエージェントとして一度だけ起動し、ステップをまたいでコンテキストを保持し、ターン間は idle になり（メッセージで起床）、各タスクの完了はそのタスクを割り当てた相手へ報告する。

宛先の契約:

- teammate の宛先は起動時に付けた **name**、すなわちロール識別子 `architect-{slug}` / `coder-{slug}` / `writer-{slug}` / `reviewer-{slug}` / `dev-helper` / `comment-sensei` / `prompt-sensei`。name は teammate が idle になっても完了しても解決し続け、送信によりトランスクリプトから再開される。
- 同名は最後に起動したものが勝つため、1 セッション内で同じ name を 2 体に付けない。
- `--team-tag` 指定時、teammate の name はロール識別子の後ろに `-{tag}` を付けたもの（例: `coder-backend-{tag}`、`writer-readme-{tag}`、`dev-helper-{tag}`）であり、あなたが扱う name はすべてこのタグ付きの name である: spawn する name、宛先、teammate に渡す name（`reviewer`、`producer`、`comment_reviewer`、`prompt_reviewer` の各変数を含む）、roster と再 spawn 待ちに記録する name、照合する name（ステップ 2 の手順 4 の新しいメンバーの判定、ステップ 4 の手順 7a の name の選択）、`taken_names` に挙げる name、`TaskStop` で止める name。subagent_type にはタグを付けない。本スキルがほかの箇所に書くロール識別子（`dev-helper`、`architect-{slug}` など）は、タグ付きの name を表す。
- リーダー宛は `to: "main"`。teammate どうしが DM する場合は、リーダーが各メッセージで相手の name を渡す。
- `SendMessage` の `message` は常に散文の文字列で `summary` を添えて送る（dispatch も報告も）。構造化された結果はファイル経由で渡し、`message` には入れない。例外はプロトコルオブジェクトのみ（`${CLAUDE_PLUGIN_ROOT}/rules/teammate.md` § ツール）。

リーダーはイベント駆動で進行し、共有タスクリストを持たない: dispatch したらターンを終え、teammate からのメッセージ（`to: "main"`）で再起動される。roster（各 teammate の name → `agentType`）、再 spawn 待ちの teammate、ペアリング、各セルの状態を自身の作業状態で追跡し（`TodoWrite` でユーザーに可視化してよい）、ステップのゲート条件が満たされたら次のステップを開始する。

## Agent 種別と起動要件

teammate は Agent ツールで起動する。厳密な引数列を写経するのではなく、以下の要件を満たすこと: バックグラウンドの永続サブエージェントとして起動し（再メッセージで継続できる）、prompt に spawn 契約を渡し、`description` を指定し、`name` にロール識別子を設定し、spawn が通った時点でその name を roster に記録する。それまでは、拒否された teammate の name・種別・ペアリングを再 spawn 待ちとして保持する。

作業中の teammate は、セッション内で実行中のサブエージェントに対するランタイムの上限（`CLAUDE_CODE_MAX_CONCURRENT_SUBAGENTS`、既定 20）の数に入り、上限に達していると spawn は `Concurrent subagent limit reached` で拒否される。この拒否は、エラーが再試行しないよう告げていても失敗ではない。実行数が上限を下回れば spawn は再び成功するためである。拒否された teammate の spawn が通るまでは、その teammate 宛てのメッセージと、その name を別の teammate に渡すメッセージ（その name を `reviewer`、`producer`、`comment_reviewer`、`prompt_reviewer` として渡すセルの開始メッセージなど）を保留し、セルの開始メッセージは片方を保留するなら 2 通とも保留する。保留したメッセージは、そのメッセージが宛てるか name を渡す、拒否された teammate すべての spawn が通った時点で送り、セルの開始メッセージは 2 通ともそうなった時点でそろえて送る。このターンで送る他のメッセージを、保留中のエスカレーションへの裁定も含めて送った後に、リーダーを起こす報告か完了通知でまだ届いていないものがあるかを判断する。そうした報告や通知の送り手は、spawn した、またはメッセージを送った teammate でその後ターンを終えていないもの（spawn したばかりの teammate も含む）と、リーダーを待っていない開いているセル（開始メッセージを保留しているセルは開いているセルに数えない）である。あれば、そのいずれかに起こされたときに、拒否された teammate を spawn し直す。なければリーダーを起こすイベントは来ないので、エラーを表示して Step 5 に進む。

agent 種別（subagent_type）:

- 同梱エージェントはプラグイン名前空間付きで指定する: `cdev:dev-helper`、`cdev:comment-sensei`、`cdev:prompt-sensei`。
- reviewer は team-analysis かチームの再編成が返す登録名で指定する（プロジェクト `.claude/agents` / ユーザー `~/.claude/agents` のエージェントは登録名そのまま）。その名前とステップ 4 の手順 7a の `{suggested_specialist}` について: 名前 `{X}` が利用可能なエージェントでなく、`:` を含まず、`${CLAUDE_PLUGIN_ROOT}/agents/{X}.md` が存在するときは、代わりに `cdev:{X}` を種別とし、roster にはこれをその teammate の `agentType` として記録する。ステップ 2 の手順 4 は、エントリの `name` を `team.jsonl` の `name` と比べ、roster の `agentType` とは比べない。
- architect、coder、writer は常に `general-purpose` で起動する。一部の専門家エージェントはツールコールをテキストとして出力して停止し、作業を継続できないことがあるため。producer（architect / coder / writer）は割り当てスコープとプロジェクト規約に従って作業し、ドメインの正しさは専門家 reviewer がレビューで担保する。

## spawn 契約

各 teammate は以下のプロンプトで一度だけ spawn する。これはロールと報告プロトコルを確定し、以降の各メッセージがそのタスクで Read すべきテンプレートを指定する。共通禁止事項とセルプロトコルは `${CLAUDE_PLUGIN_ROOT}/rules/teammate.md` を参照。

```
あなたはチームに {role} として参加する。私が割り当てる各タスクでは、`${CLAUDE_PLUGIN_ROOT}/skills/coding/templates/` 配下のテンプレートを指定し変数を渡すので、そのテンプレートを Read してそのタスクで従う。全タスク共通の変数: plugin_root = ${CLAUDE_PLUGIN_ROOT}、doc_lang = {doc_lang}、main_root = {main_root}、target_dir = {target_dir}。各タスクの結果はそのタスクを割り当てた相手へ報告し（リーダーは `SendMessage` の `to: "main"`、それ以外は依頼元 teammate の name。カウント / パス / 一行サマリのみ）、詳細な指摘はテンプレートの指示どおりに、相手の name 宛 `SendMessage` で peer-to-peer ルーティングする（相手の name は私が各メッセージで渡す）。`${CLAUDE_PLUGIN_ROOT}/rules/teammate.md` を Read し共通禁止事項とレビューセルプロトコルを遵守する。
```

## レビューセルプロトコル

セルは producer（architect、coder、または writer）を 1 人の reviewer とペアにし、ペアは `${CLAUDE_PLUGIN_ROOT}/rules/teammate.md` § レビューセル のプロトコルを自律的に回す: producer が成果物を作成し、reviewer は対応必須（`Critical` / `Major`）の指摘を producer へ DM して重要度カウントをリーダーへ報告し、producer が各指摘を triage し、レビュー ⇄ triage を `--review-rounds` を上限に反復する。

クローズでゲートする: 各セルは `to: "main"` 宛のクローズ報告 1 通（セル id を明記）で終わる — resolve、またはラウンド上限到達によるクローズ（未解決の `Critical` には `FIXME:` が残る）。`Critical` の不一致はそのクローズより前にエスカレーションとしてリーダーへ届く。

triage と裁定の判断優先度: (1) ユーザーの元のタスク指示、次に (2) `--handoff` 指定時はその申し送り、次に (3) 上流の設計意図。

ドキュメントセルでは、この優先度より先に次の規則を適用する: コードが何をするかの記述はコードに従い、優先度が決めるのは何をドキュメント化するかだけである。設計やタスクと食い違うコードに従ったドキュメントは、writer がその食い違いを乖離として挙げていれば指摘にならない。挙げていなければ、その指摘の修正は乖離として挙げることであり、ドキュメントは変えない。ドキュメントをタスクや設計に合わせてコードと矛盾させる修正は決して採らない。

## エスカレーション

reviewer が `Critical` の不一致をエスカレーションした場合、リーダーは上記の判断優先度で裁定する。ドキュメントセルでは、先に上記の規則を適用する。`--handoff` 指定時、リーダーは裁定のために申し送りを Read してよい: 申し送りはタスクの入力であり、§ リーダーのスコープ が teammate 側に留める本体ではない。リーダーもいずれとも判断できない場合、対立をユーザーへ要約して提示し、producer に当該箇所へ `FIXME:` を挿入させる（producer の name 宛 `SendMessage` で依頼）。ユーザーの回答は待たずに進行し、未解決項目として下流の権威あるレビューのために記録する。

## リーダーのスコープ（本体の隔離）

リーダーが保持するのは、roster（各 teammate の name → agentType）、再 spawn 待ちの teammate、ペアリング、各セルの状態、重要度カウント、ファイルパス、QA と解釈テストの結果、設計が復元元とするターニングポイントの名前、coder と writer が拒否されたと報告する復元エントリ、writer が報告する乖離、エスカレーションの数と未解決項目のために残した `FIXME:` の数、コミット計画のパス、`commit-plan.py` の出力（`paths` がパスを挙げたかどうか、`check` の `errors`、作ったコミットとその件名、`tree_match`）のみ。設計本体・ソース・ドキュメント本体・指摘本体・コミット計画の本体は teammate 側に留まり、リーダーはコミット計画を Read しない。指摘は producer ⇄ reviewer 間を `SendMessage` で行き来する。

## 作業用ディレクトリ

```
{tmp_dir} = .claude/tmp/cdev-coding-{timestamp}/
{tmp_dir}/team.jsonl               ← team-analysis の結果（roster。リーダーが読む）
{tmp_dir}/team-reassign.jsonl      ← チーム再編成の結果（coder / writer / reviewer。リーダーが読む）
{tmp_dir}/baseline-tree            ← コーディング開始前の作業ツリースナップショット（差分の基点）
{tmp_dir}/changes.txt              ← コーディング開始以降の差分（ドキュメントセルと QA の入力）
{tmp_dir}/qa-result.jsonl          ← QA 結果
{tmp_dir}/build.log                ← dev-helper が取得するビルド / テスト出力
{tmp_dir}/prompt-test.jsonl        ← AI 向けプロンプトファイルの解釈テスト結果
{tmp_dir}/commit-plan.jsonl        ← コミット計画（dev-helper が書き、commit-plan.py が読む）
```

作成はステップ 1 で `mkdir -p`、削除はリーダーがステップ 5 で `${CLAUDE_PLUGIN_ROOT}/scripts/del-tmp.sh {tmp_dir}` により行う。

設計ドキュメントは `{design_dir}/design-{slug}.md`（architect ごとに 1 つの設計セクション。reviewer と coder が読む）に置き、実行後も残す。

## ステップ 1 — チーム編成とペアリング

1. `git rev-parse --show-prefix` の出力が空でない（セッションがリポジトリのサブディレクトリにある）場合は、スキルにはリポジトリルートでの起動が必要である旨のエラーを表示してスキルを終了する。続いて、`--team-tag` が § オプション の示す形式でないか、`--handoff` が既存のファイルでない場合は、エラーを表示してスキルを終了する。
2. `--worktree` 指定時は § ワークツリー のセットアップを実行する。
3. すべての teammate が受け取る作業対象 `{target_dir}` を確定する: `--worktree` 指定時は `{worktree_path}`、それ以外は `git rev-parse --show-toplevel` の出力。
4. 本スキルはクリーンな作業ツリーでのみ動作する: `git status --porcelain -uall` を実行し、`.claude/tmp/` 配下、`.claude/worktrees/` 配下、`--output` の指定先配下、`--handoff` と `--result` のファイルを除く出力が非空（ステージ済み・未ステージ・未追跡のいずれかが存在）ならエラーメッセージをコンソールに表示してスキルを終了する。これらには過去の実行の設計ドキュメントと `--worktree` 実行のワークツリーが残るため除外する。
5. `{tmp_dir}` と `{design_dir}` を確定する。作成する前に、シンボリックリンクの `.claude` を拒否する `${CLAUDE_PLUGIN_ROOT}/scripts/del-tmp.sh --dry {tmp_dir}` を実行し、非ゼロ終了の場合はそのエラーを表示してスキルを終了する。両者を作成する（`mkdir -p`）。続いてコーディング開始前のベースラインを記録する: `${CLAUDE_PLUGIN_ROOT}/scripts/fetch-diff.sh snapshot {tmp_dir}/baseline-tree`。あわせて、`HEAD` のコミットを `{start_head}`、現在のブランチを `{start_branch}`（detached `HEAD` ではなし）として記録する。
6. コンソールに表示する: `## Step 1 — Team formation`。
7. `dev-helper`（種別 `cdev:dev-helper`、name `dev-helper`）を起動する。`dev-helper` 宛に `templates/team-analysis.md` を指定し `task = {タスク指定}`、`handoff_path = {--handoff のファイルの絶対パス、または (none)}`、`output_path = {tmp_dir}/team.jsonl` を渡して `SendMessage`。完了報告を受けたら `{tmp_dir}/team.jsonl` を Read する: `{task_summary, target_languages, has_test_suite, has_prompts, has_docs, architects:[{name, slug, scope, reviewer, reason}], coders:[{name, slug, scope, reviewer, reason}], writers:[{name, slug, scope, reviewer, reason}], reviewers:[{name, slug, reason}], rationale}`（`name` は起動時の subagent_type）。各 producer の `reviewer` はペアの reviewer の `slug`（1 人の reviewer が複数の producer とペアになることもあるが、ドメインが一致する範囲に限る）。
8. ロスターの各メンバーを起動する。name は `architect-{slug}` / `coder-{slug}` / `writer-{slug}` / `reviewer-{slug}`、種別は team-analysis が返す `name` に § Agent 種別と起動要件 が与える種別を用いる（architect、coder、writer は `general-purpose`）。ペアリングと `{task_summary}` を保持する。producer のペア reviewer の宛先は `reviewer-{その producer の reviewer slug}`。
9. コンソールに表示する: 各 producer のペアの reviewer と一行の理由を含むロスター。

## ステップ 2 — 設計セルとチームの再編成（設計）

1. コンソールに表示する: `## Step 2 — Design`。
2. 各 architect について、設計セル `design-{slug}` を 2 つのメッセージで開始する（宛先は roster の name）:
   - `architect-{slug}` 宛に `templates/design.md` を指定し、`task = {task_summary}`、`assigned_scope = {そのスコープ}`、`handoff_path = {ステップ 1 の手順 7 と同じ}`、`output_path = {design_dir}/design-{slug}.md`、`reviewer = {ペア reviewer の name}` を渡して `SendMessage`。
   - ペア reviewer の name 宛に `templates/design-review.md` を指定し、`task = {task_summary}`、`design_path = {design_dir}/design-{slug}.md`、`handoff_path = {ステップ 1 の手順 7 と同じ}`、`producer = architect-{slug}`、`cell_task = design-{slug}`、`review_rounds = {--review-rounds}` を渡して `SendMessage`。
3. ゲート: 設計セルごとにクローズ報告 1 通（届いたエスカレーションは随時裁定する）。セクションパスを `{design_paths}` として、クローズ報告が設計の復元元と述べるターニングポイントの名前を重複なく `{restored_from}` として収集する。`has_prompts` はクローズ報告から決める: いずれかのクローズ報告がその設計で AI 向けプロンプトファイルを作成または編集すると述べた場合は true、すべてのクローズ報告がその設計ではどちらもしないと述べた場合は false にし、それ以外は変えない。さらに 2 つのフラグを同じ方法で決める: `has_docs` は team-analysis の値から始め、クローズ報告がその設計の変更ファイル一覧にドキュメントファイルが含まれると述べるかどうかから決める。`has_code` は true から始め、一覧にドキュメントファイル以外のファイルが含まれると述べるかどうかから決める。
4. 設計が持ち込むファイルを含むすべてのファイルに producer（coder または writer）と領域の reviewer が付いた状態でステップ 3 を始めるよう、チームを再編成する。コンソールに表示する: `## Step 2 — Team re-formation`。`dev-helper` 宛に `templates/team-reassign.md` を指定し、`design_paths = {design_paths}`、`roster_path = {tmp_dir}/team.jsonl`、`taken_names = {このセッションで起動したすべての teammate の name}`、`team_tag = {--team-tag の値、または (none)}`、`output_path = {tmp_dir}/team-reassign.jsonl` を渡して `SendMessage`。完了報告を受けたら `{tmp_dir}/team-reassign.jsonl` を Read する: `{coders:[{name, slug, scope, reviewer, reason}], writers:[{name, slug, scope, reviewer, reason}], reviewers:[{name, slug, reason}], rationale}`。ロール名（`coder-{slug}` / `writer-{slug}` / `reviewer-{slug}`）が roster にも再 spawn 待ちの teammate にもないエントリが新しいメンバーである。
   - 次のどれかにあたる場合は、どれにあたるかを示して `dev-helper` にタスクを 1 度だけ差し戻す: ファイルがないか上の形式に合わないこと、roster の coder / writer / reviewer に同じ `slug` のエントリがないか、そのエントリの `name`（coder と writer では `reviewer` も）が異なること、出力の `coders` 内、`writers` 内、`reviewers` 内のいずれかに同じ `slug` のエントリが 2 つあること、coder か writer の `reviewer` が出力の `reviewers` のどのエントリの `slug` でもないこと。差し戻した後もどれかにあたる場合は、ステップ 1 の roster のままステップ 3 を始める: そのことをコンソールに示し、ステップ 5 の報告のために保持する。
   - そうでなければ、新しいメンバーをステップ 1 の手順 8 と同じく起動し、各 coder と各 writer のスコープとペアの reviewer を出力のものに置き換える。
   - コンソールに表示する: ステップ 1 の手順 9 と同じ形のロスター。追加したメンバーと、スコープが変わった coder と writer を示す。

## ステップ 3 — コードセルとドキュメントセル（コーディング）

1. `has_code` が false の場合は、`has_prompts` を false にする。
2. `comment-sensei`（種別 `cdev:comment-sensei`、name `comment-sensei`）を role `the comment reviewer; a coder DMs you to review comments per templates/comment-review.md` で起動する。ステップ 4 の QA 修正セルがこれを `comment_reviewer` として渡すので、`has_code` にかかわらず起動する。`has_prompts` が true の場合は、`prompt-sensei`（種別 `cdev:prompt-sensei`、name `prompt-sensei`）も role `the prompt reviewer; a coder DMs you to self-check and compress its prompt files per templates/prompt-review.md, and I assign the interpretation test per templates/prompt-test.md` で起動する。
3. `has_code` が false の場合は、コードセルを開始しない。そうでなければ、コンソールに表示する: `## Step 3 — Coding`。各 coder について、コードセル `code-{slug}` を 2 つのメッセージで開始する（宛先は roster の name）:
   - `coder-{slug}` 宛に `templates/code.md` を指定し、`task = {task_summary}`、`design_paths = {design_paths}`、`assigned_scope = {そのスコープ}`、`tdd = {has_test_suite}`、`feedback = (none)`、`reviewer = {ペア reviewer の name}`、`comment_reviewer = comment-sensei`、`prompt_reviewer = {has_prompts が true なら prompt-sensei、それ以外は (none)}` を渡して `SendMessage`。
   - ペア reviewer の name 宛に `templates/code-review.md` を指定し、`task = {task_summary}`、`design_paths = {design_paths}`、`producer = coder-{slug}`、`cell_task = code-{slug}`、`review_rounds = {--review-rounds}`、`strict_docs = {--strict-docs 指定時は on、それ以外は off}` を渡して `SendMessage`。

   ゲート: コードセルごとに、そのクローズ報告と、その coder からあなたへの報告の両方（届く順序は問わない。エスカレーションは裁定する）。coder の報告が拒否されたと挙げる復元エントリを、それぞれのターニングポイント、パス、理由とともに `{restore_refused}` として収集する。
4. 手順 3 のゲートを満たしたら、または手順 3 が開始するコードセルが 1 つもない場合はただちに（開始メッセージを保留しているセルも数える）: `has_docs` が false の場合は、ドキュメントセルを開始しない。そうでなければ、コンソールに表示する: `## Step 3 — Documentation`。roster にも再 spawn 待ちの teammate にも writer がいない場合は、設計が挙げるドキュメントファイルに writer がいないことをコンソールに示し、ステップ 5 の報告のために保持して、ドキュメントセルを開始しない。そうでなければ `${CLAUDE_PLUGIN_ROOT}/scripts/fetch-diff.sh diff {tmp_dir}/baseline-tree {tmp_dir}/changes.txt` で差分を取得し、各 writer（再 spawn 待ちのものを含む）について、ドキュメントセル `doc-{slug}` を 2 つのメッセージで開始する（宛先は roster の name）:
   - `writer-{slug}` 宛に `templates/doc.md` を指定し、`task = {task_summary}`、`design_paths = {design_paths}`、`assigned_scope = {そのスコープ}`、`diff_path = {tmp_dir}/changes.txt`、`feedback = (none)`、`reviewer = {ペア reviewer の name}` を渡して `SendMessage`。
   - ペア reviewer の name 宛に `templates/doc-review.md` を指定し、`task = {task_summary}`、`design_paths = {design_paths}`、`diff_path = {tmp_dir}/changes.txt`、`assigned_scope = {その writer のスコープ}`、`producer = writer-{slug}`、`cell_task = doc-{slug}`、`review_rounds = {--review-rounds}`、`strict_docs = {手順 3 と同じ}` を渡して `SendMessage`。

   ゲート: ドキュメントセルごとに、そのクローズ報告と、その writer からあなたへの報告の両方（届く順序は問わない。エスカレーションは裁定する）。writer の報告は乖離を挙げる: それぞれ、そのスコープのファイルと、そこでコードが設計やタスクとどう食い違うか。各 writer の最新の報告の乖離を `{doc_departures}` として保持する。writer の報告が拒否されたと挙げるエントリを、それぞれのターニングポイント、パス、理由とともに、重複なく `{restore_refused}` に加える。

## ステップ 4 — QA ゲート

QA 検証 ⇄ 修正のループを `--qa-attempts` を上限に実行する。

1. コンソールに表示する: `## Step 4 — QA (attempt {n})`。
2. コーディング開始以降の差分を取得する: `${CLAUDE_PLUGIN_ROOT}/scripts/fetch-diff.sh diff {tmp_dir}/baseline-tree {tmp_dir}/changes.txt`。
3. `dev-helper` 宛に `templates/qa.md` を指定して `tmp_dir = {tmp_dir}`、`diff_path = {tmp_dir}/changes.txt`、`attempt_num = {n}` を渡して `SendMessage`。その 1 行の完了報告を `{summary_line}` として保持し、`{tmp_dir}/qa-result.jsonl` を Read する: `{success}` は `failure == null`、`{suggested_specialist}` / `{error_summary}` / `{environmental}` は `failure` の対応フィールド（`failure` が null なら `{environmental}` は false）。`workflow_warning` が非 null の場合、ステップ 5 のために保持する。
4. `has_prompts` が true の場合、手順 3 と同じターンで `prompt-sensei` 宛に `templates/prompt-test.md` を指定し、`task = {task_summary}`、`design_paths = {design_paths}`、`diff_path = {tmp_dir}/changes.txt`、`output_path = {tmp_dir}/prompt-test.jsonl`、`attempt_num = {n}`、`fixed_files = {前の試行の QA 修正セルの割り当てスコープのファイル。試行 1 では (none)}` を渡して `SendMessage`。その 1 行の完了報告を `{prompt_summary_line}` として保持し、`{tmp_dir}/prompt-test.jsonl` を Read する: `{prompt_pass}` はその `pass`、`{prompt_failed_files}` は `pass` が false かつ `untested` が null の各ファイルの `path`、`{prompt_untested_files}` は `untested` が非 null の各ファイルの `path` と `untested` の理由。そのファイルがないか、`files` フィールドを持たないか、その `attempt` が `{n}` でない場合は、解釈テストがこの試行の結果を書かなかったものとする: `{prompt_pass}` は false、`{prompt_failed_files}` は空とし、`{prompt_untested_files}` には解釈テストが結果を書かなかったことを記録する。`files` が空配列の結果は、テストするプロンプトファイルが 0 件の有効な結果であり、その `pass` を使う。`has_prompts` が false の場合、`{prompt_pass}` は true とする。
5. 手順 3〜4 の報告がそろったら、`success` と `prompt_pass` がともに true の場合はループを抜ける。
6. 修正可能な失敗は、`success == false` かつ `environmental` が false の場合のビルド / テスト失敗と、`{prompt_failed_files}` が空でない場合の解釈テスト失敗である。`success == false` かつ `environmental` が true の場合は、`error_summary` を環境起因の失敗としてコンソールに提示し、この失敗には QA 修正セルを回さない。`{prompt_untested_files}` も同様に理由とともにコンソールに提示し、QA 修正セルを回さない。修正可能な失敗がない場合はステップ 5 へ進む。
7. 試行回数が残っている場合: ビルド / テスト失敗が修正可能（手順 6）で、その `error_files` が null でも空でもない場合は、まずそこから、ファイルが writer（再 spawn 待ちのものを含む）のスコープにあるエントリを取り出し（スコープがそのファイルか、その上のディレクトリを挙げる場合）、その writer のドキュメントエラーとする: 以下のビルド / テスト失敗のファイルは残りであり、エントリが 1 つも残らなければ、その失敗には QA 修正セルを回さない。それ以外の場合は、ビルド / テスト失敗のファイルはその `error_files` であり、ドキュメントエラーはない。修正可能な失敗ごとに QA 修正セルを 1 つずつ並行して回す。ビルド / テスト失敗のファイルと `{prompt_failed_files}` が同じファイルを含む場合は、代わりに 2 つの失敗を 1 つの QA 修正セルで回す: スコープは両者のファイルの和集合、フィードバックは手順 b の 2 つのフィードバックをつなげたもの、セル id は `code-qa-{n}`、reviewer はビルド / テスト失敗に合わせる。
   a. 失敗スコープ — ビルド / テスト失敗のファイル、または `{prompt_failed_files}` — を `general-purpose` の coder と、失敗ドメインに一致するペア reviewer でカバーする（ビルド / テスト失敗では `{suggested_specialist}` をヒントとし、解釈テスト失敗のドメインは AI 向けプロンプト）。適合する roster のメンバーは再利用し（2 つのセルに同じ coder を充てない。`prompt-sensei` の teammate はそのセルのファイルのプロンプトレビューと解釈テストを担うので、セルの reviewer にしない）、いなければ roster にも再 spawn 待ちの teammate にもない `coder-{slug}` / `reviewer-{slug}` を name として起動する。新規に起動する reviewer の subagent_type は、ビルド / テスト失敗では § Agent 種別と起動要件 が `{suggested_specialist}` に与える種別が利用可能なエージェントであればそれを、解釈テスト失敗では `cdev:prompt-sensei` を、それ以外は `general-purpose` を用いる。
   b. coder の name 宛に `templates/code.md` を指定し、`task = {task_summary}`、`design_paths = {design_paths}`、`assigned_scope = {失敗したファイル}`、`tdd = {has_test_suite}`、`feedback = {その失敗のフィードバック}`、`reviewer = {ペア reviewer の name}`、`comment_reviewer = comment-sensei`、`prompt_reviewer = {ステップ 3 と同じ}` を渡して `SendMessage`。そして reviewer の name 宛に `templates/code-review.md` を指定し、`task = {task_summary}`、`design_paths = {design_paths}`、`producer = {coder の name}`、`cell_task = {その失敗のセル id}`、`review_rounds = {--review-rounds}`、`strict_docs = {ステップ 3 と同じ}` を渡して `SendMessage`。失敗ごとの値:
      - ビルド / テスト: `feedback = QA failure — Read {tmp_dir}/qa-result.jsonl (failure section) and {tmp_dir}/build.log; fix the build/test error.`、セル id `code-qa-{n}`。
      - 解釈テスト: `feedback = Prompt interpretation test failure — Read {tmp_dir}/prompt-test.jsonl (the files whose pass is false and untested is null); make each unclear item answerable from the prompt.`、セル id `prompt-qa-{n}`。
   c. この試行の QA 修正セルがすべてクローズしたら、または手順 7 がこの試行に QA 修正セルを 1 つも立てない場合はただちに（開始メッセージを保留しているセルも数える）、ドキュメントエラーを持つ writer がいる場合、または `has_docs` が true でこの試行で QA 修正セルが走った場合は、QA ドキュメントセルを開始する。手順 2 と同じく `{tmp_dir}/changes.txt` を取得し直す。その writer は、`has_docs` が true で QA 修正セルが走った場合はすべての writer（再 spawn 待ちのものを含む）、それ以外はドキュメントエラーを持つ writer とする。それぞれについて、セル `doc-qa-{n}-{slug}` をステップ 3 の手順 4 の 2 つのメッセージで開始する。`cell_task` はそのセル id、`feedback` は次のとおりとし、両方にあたる場合はつなげる:
      - ドキュメントエラー: `QA failure — Read {tmp_dir}/qa-result.jsonl (failure section) and {tmp_dir}/build.log; fix the errors they report in the documentation files of your scope.`
      - `has_docs` が true で QA 修正セルが走った: `Code changed in the QA-fix cells of attempt {n} — Read {tmp_dir}/changes.txt; bring the documentation of your scope in line with the code.`

      これらは QA 修正セルではない: 手順 4 の `fixed_files` はそのファイルを含めない。
   d. この試行の QA ドキュメントセルがすべてクローズしたら、または手順 c がこの試行に QA ドキュメントセルを 1 つも立てない場合はただちに（開始メッセージを保留しているセルも数える）、このループのステップ 1 へ戻る（再 QA）。そのゲートはクローズ報告だけとする。`{doc_departures}` は、writer の報告が届くたびに、遅れて届いたものも含めて更新する。
8. 最大試行回数を超えても修正可能な失敗が残る場合、残った失敗の `error_summary` と `{prompt_failed_files}` をコンソールに提示してステップ 5 へ進む。

## ステップ 5 — クリーンアップと報告

1. `--commit` が ON でステップ 4 のループが QA と解釈テストの双方の通過で抜けた場合、または `--commit-always` が ON で実行がステップ 4 に入っていた場合（QA と解釈テストの結果は問わず、ステップ 4 での spawn の拒否でステップ 5 に来た実行も含む）は、実装をコミットする。`--handoff` 指定時は、先に現在のブランチと `HEAD` のコミットがまだ `{start_branch}` と `{start_head}` であることを確かめ、そうでなければコミットせず、そのことを報告のために保持する。コミットでは、作業ツリーの変更を、`commit-plan.py` が常に除く `.claude/tmp` と `.claude/worktrees`、および `{commit_excludes}` を除いて、論理的な変更ごとのコミットに分けてコミットする。`{commit_excludes}` を、`{design_dir}` と、指定されていれば `--handoff` と `--result` のファイルの絶対パスとして確定し、その各パスを引用符で囲んだ `--exclude {path}` を並べたものを `{exclude_options}` とする。作った各コミットの SHA と件名、その数を、手順 5〜6 のために保持する。
   a. まず `git reset -q` を実行する。`commit-plan.py --worktree` がステージ済みの変更のあるインデックスを拒否するためである。次に `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/commit-plan.py paths --worktree {exclude_options}` を実行する。その `paths` が空ならコミットしない。
   b. `dev-helper` 宛に `templates/commit-plan.md` を指定し、`task = {task_summary}`、`design_paths = {design_paths}`、`exclude = {commit_excludes}`、`output_path = {tmp_dir}/commit-plan.jsonl`、`rejection = (none)` を渡して `SendMessage`。
   c. 完了報告を受けたら、`python3 ${CLAUDE_PLUGIN_ROOT}/scripts/commit-plan.py check --worktree {exclude_options} --plan {tmp_dir}/commit-plan.jsonl` を自ら実行する。出力に `errors` があって不合格の場合は、`dev-helper` にタスクを 1 度だけ差し戻す。`rejection` にはその `errors` を、メッセージの散文の中で 1 件ずつ 1 文で述べる。その報告を受けたら、もう 1 度 `check` を実行する。
   d. `check` が合格したら、`python3 ${CLAUDE_PLUGIN_ROOT}/scripts/commit-plan.py commit --worktree {exclude_options} --plan {tmp_dir}/commit-plan.jsonl` を Bash ツールの `run_in_background` で実行し、終了してから、その終了コードと出力で判断して先へ進む: コミットごとにプロジェクトのコミットフックが走るため、Bash ツールの最大のタイムアウトも超えることがある。成功して `tree_match` が false の場合は、そのことを `commit_warning` に記録し、それ以上はコミットしない。
   e. 次の場合は 1 回のコミットにフォールバックし、その理由を `commit_warning` に記録する: `dev-helper` が roster にいないか、`dev-helper` への `SendMessage` が失敗した場合、`paths` が非ゼロ終了した場合、`check` が `errors` のない失敗で終わったか、差し戻しの後も不合格の場合、`commit` が非ゼロ終了した場合（失敗するまでに作ったコミットは残す）。コミットする対象のうちまだコミットされていない変更をすべてステージし、`${CLAUDE_PLUGIN_ROOT}/rules/commit-plan.md` § メッセージ に従うメッセージで 1 回コミットする。そのルールの B は `HEAD`、`plugin_root`・`main_root`・`target_dir` は `${CLAUDE_PLUGIN_ROOT}`・`{main_root}`・`{target_dir}` と読む。ステージするものがなければコミットしない。フォールバックのコミットが失敗した場合は、そのことを `commit_warning` に足し、それ以上は何もしない。
2. teammate を停止する: roster の各 name を `task_id` として `TaskStop` を呼び、応答や通知を待たずに次の手順へ進む。アイドルの teammate には稼働中のタスクがないため、稼働していない旨の失敗は停止済みとみなす。`shutdown_request` は送らない: リーダーが待てる完了の合図がない。
3. 作業用ディレクトリを削除する: `${CLAUDE_PLUGIN_ROOT}/scripts/del-tmp.sh {tmp_dir}`。
4. `--worktree` 指定時は § ワークツリー のティアダウンを実行する。
5. `--result` 指定時は、結果ファイルを書く（§ 結果ファイル）。
6. コンソールへ報告する: 設計ドキュメントのパス（`{design_paths}`）、ペアリングを含むチームのロスター、チームの再編成がステップ 1 のロスターにフォールバックしたかどうか、ステップごとに resolve したセル（ドキュメントセルを含む）、エスカレーションと未解決項目のために残した `FIXME:`、変更されたファイル、ステップ 5 の手順 1 で作ったコミットの数と各件名、null でなければ `commit_warning`、coder か writer が拒否されたと報告した復元エントリ（ターニングポイント、パス、理由）、`{doc_departures}` の乖離、ステップ 3 で writer がいなかった場合は設計が挙げるドキュメントファイルにドキュメントセルが回らなかったこと、coder が報告したプロンプトレビューの件数、ステップ 4 を実行した場合の QA 結果（`summary_line`、あれば `workflow_warning`、`has_prompts` が true なら `prompt_summary_line`）、未修正の QA 失敗（`environmental` が true なら環境起因である旨を明示する）、解釈テストに不合格のままのプロンプトファイル、未テストのプロンプトファイルとその理由、稼働していない以外の理由で `TaskStop` が失敗した teammate、および spawn の拒否でステップ 5 に来た場合は、中断したステップと、spawn が拒否されたままの teammate。加えて、`--commit-always` が QA か解釈テストの未通過のままコミットした場合はそのこと、ブランチか `HEAD` が動いたためにコミットしなかった場合はそのこと、`--result` 指定時は結果ファイルのパスか、その書き出しに失敗したことを示す。`--worktree` 指定時はブランチと、ティアダウンで残したワークツリーがあればそれも加える。
