---
name: loop
description: コーディングタスクを /cdev:coding と /creview:rounds の 1 本のパイプラインとして、ユーザーの判断を仰がずに実行する。レビューが発散を検出したら、同じブランチでタスクを /cdev:coding に差し戻す。レビューの後はポストモーテムが、終了するか、開始コミットからやり直すかを決める。差し戻しとやり直しは、それぞれ上限の回数の内で行う。ユーザーがこのスキルを名指ししたとき、またはコーディングタスクを実装からレビューまで無人で通すよう求めたときに使用する。creview プラグイン、バックグラウンドのサブエージェント（Agent の run_in_background）とエージェント間メッセージング（SendMessage）が利用可能なランタイム、深さ 3 以上のサブエージェントのネスト起動を要する。
allowed-tools: Skill, Agent, Read, Write, Glob, Grep, Bash(cd:*), Bash(mkdir:*), Bash(git rev-parse:*), Bash(git branch:*), Bash(git check-ref-format:*), Bash(git status:*), Bash(git log:*), Bash(git show:*), Bash(git diff:*), Bash(git grep:*), Bash(python3 ${CLAUDE_PLUGIN_ROOT}/scripts/check-jsonl.py:*), Bash(${CLAUDE_PLUGIN_ROOT}/scripts/del-tmp.sh:*)
---

# コーディングループ

あなたは**ループリーダー**として、コーディングタスクを `/cdev:coding` と `/creview:rounds` のサイクルに通す。レビューが発散を検出したら、同じ世代のうちにタスクを `/cdev:coding` へ差し戻す。世代の終わりには、ポストモーテムのサブエージェントが、終了するか、開始コミットから新しい世代を始めるかを判定する。あなたは設計・コード記述・レビュー・修正を行わない。保持するのは状態ファイル、パス、件数、終了理由、判定、短い警告文だけであり、設計、レビュー、発散調査レポート、ポストモーテム、ポストモーテムが書く申し送りの本文は Read しない。唯一の例外は、`/cdev:coding` のリーダーとして裁定するエスカレーション（§ 内側スキルの実行）である: その § エスカレーション に従い、そのサイクルの申し送りを Read してよく、差し戻しの申し送りなら、それが参照するポストモーテムの申し送りも Read してよい。

## 動作要件

このスキルは `/cdev:coding` と `/creview:rounds` の動作要件を引き継ぐ。次のいずれかに当たる場合は、ステップ 1 で何も作らずに、理由を示して終了する:

- `Agent` の `run_in_background`、または `SendMessage` が利用できない。
- 利用できるスキルに `creview:rounds` がない: creview プラグインの導入をユーザーに求める。
- リポジトリの出所を信頼できない。判断は `/cdev:coding` の信頼前提と同じとする。

ネストの深さは事前に確かめられない: 足りなければ `/creview:rounds` がエラーで終わる（§ 停止条件）。

両スキルはこのセッションでインライン実行し、サブエージェントに委ねない: `/cdev:coding` のリーダーは、チームメイトから `to: "main"` で届くメッセージを受けるメインセッションでなければならず、`/creview:rounds` を委ねるとネストが 1 段深くなる。

## 入力

引数が `$ARGUMENTS` の場合、それをコーディングタスクとオプションとして解釈する。`{task}` は引数から § オプション のオプションを除いたものであり、どのサイクルでも書き換えずに `/cdev:coding` へ渡す。

## オプション

- `--branch {name}`（デフォルト `cdev-loop-{timestamp}`）— 成果物ブランチの名前。作業ブランチとターニングポイントの名前の接頭辞を兼ねる（§ 名前とパス）。
- `--max-sendbacks N`（デフォルト 2、範囲 0–5）— 世代あたりの差し戻し回数の上限。
- `--max-generations N`（デフォルト 3、範囲 1–5）— 世代数の上限。
- `--pursuit`（デフォルト OFF）— 残存問題のない世代でも、明確に上回るアプローチを示せる場合はポストモーテムが redo とすることを許す。
- `--output {dir}`（デフォルト `.claude/tmp/cdev-loop-{timestamp}/`）— 実行ディレクトリ `{loop_dir}`。

パススルー: `--review-rounds N`（範囲 1–10）と `--qa-attempts N`（範囲 1–10）は `{coding_args}` として `/cdev:coding` へ、`--max-rounds N`（範囲 1–20）、`--adversarial`、`--adr` は `{rounds_args}` として `/creview:rounds` へ渡す。どちらも、指定がなければ空とする。

範囲外の値と、次のオプションでは、エラーを表示して終了する:

- `--worktree`、`--commit`、`--incremental`: 常に有効である旨をエラーに添える。
- `--confirm`、`--confirm-round`、`--base`。
- `--on-divergence`、`--result`、`--handoff`、`--team-tag`、`--commit-always`: このスキルが内側スキルに指定する。

## 名前とパス

- `{loop_branch}`: `--branch` の値、またはそのデフォルト。内側スキルは `{branch}` を自身の変数に使う。
- `{repo_root}`: ステップ 1 での `git rev-parse --show-toplevel` の出力。メイン作業ツリーのルートである。
- `{loop_dir}`: 絶対パス。相対パスの `--output` は `{repo_root}` を基点に解決する。
- `{hhmmss}`: `{timestamp}` の時刻部。
- 世代 g の作業ブランチ: `{loop_branch}-g{g}`。
- 世代 g のサイクル c のターニングポイント（TP）: TP-A `{loop_branch}-tp/g{g}c{c}-coding-start` と TP-B `{loop_branch}-tp/g{g}c{c}-coding-done`。
- 成果物ブランチ: `{loop_branch}`。

ブランチは、どの作業ツリーにも触れない `git branch {name} {commit}` でのみ作成する。TP は動かさず、消さない。作業ブランチの履歴は書き換えない。

サイクルのディレクトリ `{loop_dir}/g{g}c{c}/` は `design/`、`coding-result.json`、`review/`、`rounds-result.json`、`handoff.md` を持つ。世代 g のポストモーテムは `{loop_dir}/g{g}/` に書く。

## 内側スキルの実行

Skill ツールで、各ステップが挙げる引数を付けて起動する。ユーザーが直接起動したときと同じく、そのスキルのリーダーとして最後のステップまで務め、それから起動した手順の次の手順へ進む: 内側スキルの完了報告でこのスキルは終わらない。ステップ 1 のエラーや動作要件の未達など、内側スキルが最後のステップに至らずに終了した場合も、同じくそこへ進む。結果は結果ファイルで判断し、ファイルがないことも結果の 1 つとする。内側スキルの実行中は、`plugin_root` と `CLAUDE_PLUGIN_ROOT` のプレースホルダーが示すそのプラグインルート、`{timestamp}`、`{tmp_dir}`、`{branch}` などの変数は、そのスキルが確定する値である。戻った後は、このスキルの値に戻る。

`EnterWorktree` / `ExitWorktree` は使わない: ワークツリーの作成と移動は内側スキルが行う。戻るたびに `git rev-parse --show-toplevel` が `{repo_root}` を出力することを確かめる。出力しない場合は `cd {repo_root}` を実行して別の Bash 呼び出しで確かめ直し、それでも出力しなければエラー終了とする（ステップ 6）。

## 状態ファイル

`{loop_dir}/state.json` が実行の進行の正である。1 つの JSON オブジェクトとして Write で書き、書くたびに `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/check-jsonl.py {loop_dir}/state.json` で検証し、エラーなら直して再検証する。書けない、または検証に通るよう直せない場合は、エラーを表示して終了する。書けるなら `loop-summary.md`（ステップ 6）を書く。

書くもの:

- `position`。ステップ 2〜6 をそれぞれ始めるときに書く。
- 繰り返すと壊れる副作用。起こした直後に書く: 作業ブランチの作成（その世代の項目）、TP の作成（`turning_points`）、内側スキルの起動（サイクルの `coding.started` / `review.started` は起動の直前に true を書き、`skill_dir` は Skill ツールが示すスキルのベースディレクトリを、起動の直後、その手順に入る前に書く）。
- 差し戻しでは、増やした c と `sendbacks`、新しいサイクルの項目、`position` を 1 回の書き込みで書く。
- 各ステップの結果。分かった時点で書く。

```json
{"task": "<タスク>", "timestamp": "...", "repo_root": "<abs>", "loop_dir": "<abs>",
 "skill_dir": "<abs>", "start_commit": "<S>", "branch": "<loop_branch>", "doc_lang": "<チャットの言語>",
 "limits": {"max_sendbacks": 2, "max_generations": 3, "pursuit": false},
 "coding_args": "<パススルーのオプション、または空文字列>", "rounds_args": "<同上>",
 "position": {"generation": 1, "cycle": 2, "step": "review"},
 "generations": [
   {"generation": 1, "work_branch": "...-g1", "sendbacks": 1, "unresolved_divergence": false,
    "cycles": [
      {"cycle": 1, "handoff": null,
       "coding": {"started": true, "skill_dir": "<abs>", "result_path": "...",
                  "committed": true, "qa_passed": true, "prompt_test_passed": true,
                  "restored_from": [], "fixme_count": 0},
       "review": {"started": true, "skill_dir": "<abs>", "result_path": "...",
                  "end_reason": "divergence", "rounds": 3}}],
    "postmortem": {"md_path": "...", "json_path": "...", "verdict": "redo",
                   "basis": "residual", "adopted_generation": null,
                   "summary_line": "...", "fallback": null}}],
 "turning_points": [{"name": "...", "commit": "<sha>", "kind": "coding-start",
                     "generation": 1, "cycle": 1}],
 "adopted_generation": null,
 "warnings": [{"generation": 1, "cycle": 1, "source": "coding", "message": "..."}],
 "end": null}
```

- トップレベルの `skill_dir`: このスキルのベースディレクトリ。このスキルの起動時に Skill ツールが示したもの。
- `position.step`: `init`、`coding`、`review`、`sendback`、`postmortem`、`finish` のいずれか。
- `coding` / `review`: `started` と `skill_dir` は起動時に、ほかのフィールドは結果ファイルから書く。
- `postmortem.fallback`: ステップ 5 が自身の判定で代替した場合はその理由、それ以外は null。
- `end`: ステップ 6 で書く。`{"kind": "normal"|"error", "step": "<止まったステップ>", "error": "<文字列>"|null, "output_branch": "<名前>"|null}`。
- `warnings`: 短い警告文だけを書く。`coding-result.json` からは、未通過の QA（環境起因かどうかを添える）、解釈テストが未通過または未テストとしたファイル、チーム再編成のフォールバック。`rounds-result.json` からは、その `workflow_warnings` と `prompt_warnings`。あなた自身のものとしては、発散調査レポートの欠落、ポストモーテムの代替判定、成果物ブランチの作成失敗。`source` は `coding`、`review`、`postmortem`、`finish` のいずれか。

コンテキストから自分の位置が分からない場合は、このファイルと、そのトップレベルの `skill_dir` にある `SKILL.md` を Read する。Read した `SKILL.md` の `CLAUDE_PLUGIN_ROOT` のプレースホルダーは展開されないまま残る: Read した元の `skill_dir` の 2 階層上のディレクトリとみなす。このスキルでも内側スキルでも同じとする。`position` から続ける:

- ファイルが記録している副作用は繰り返さない。
- 作成しようとする作業ブランチ、TP、成果物ブランチが、指すべきコミットに既にある場合は、作成せずに記録だけをする。作業ブランチや TP が別のコミットを指している場合は、エラー終了とする。成果物ブランチが別のコミットを指している場合は、ステップ 6 の手順 2 の作成の失敗として扱う。
- `position.step` が `coding` か `review` で、そのサイクルの `started` が true の場合:
  - `skill_dir` が記録されていなければ、内側スキルは最初の手順に入っていない: 起動し直す。
  - そのサイクルの結果ファイルがあれば、内側スキルは終わっている: そのステップの結果ファイルの扱いから続ける。
  - 結果ファイルがなく、内側スキルが終わったこと（完了報告、または途中での終了）がコンテキストにあれば、結果ファイルがない異常終了として扱う。
  - それ以外では、内側スキルはこのセッションでまだ実行中である: 起動し直さず、そのリーダーとして続ける。その指示がコンテキストにない場合は `{skill_dir}/SKILL.md` を Read する。
- `position.step` が `sendback` なら、ステップ 4 の手順 1 は済んでいる: 手順 2 から続ける。
- その世代の `postmortem` に判定が記録されていれば、その判定でステップ 5 の手順 5 から続ける。申し送りの書き込みと、判定が記録されていないポストモーテムの起動は、出力を上書きするだけである: やり直す。

## 申し送り

申し送りは `{doc_lang}` の Markdown で、次の節をこの順に持ち、見出しは `{doc_lang}` で書く: サイクル `g{g}c{c}` を示す表題、種別（差し戻しまたはグランドリセット）と起点、やり直す理由、方針、維持すること、避けること、戻り先の候補、参照資料（読み取り専用）。

差し戻しの申し送りはあなたが書く。本文を Read せずに書ける内容に限る:

- 起点: 作業ブランチとその先頭のコミット。タスクはこのブランチに実装済みであり、発散の源泉を取り除く変更を設計・実装する。
- やり直す理由と方針: 発散調査レポートのパスと、各 `D-n` の Source とその推奨の Fix proposal に従うという指示。推奨案は `/creview:rounds` 向けに書かれているので、次のように読み替えるよう添える: 推奨案が担当指摘や修正サブエージェントを挙げていても、推奨案が記述するコードやプロンプトの変更内容を採る。推奨案が指摘を Won't Fix とする箇所や、判断をユーザーに委ねる箇所は、設計で判断し、受容する範囲とその前提を次のレビューが読むコードかドキュメントに明記する。トリアージの判断はそのレビューに引き継がれないからである。
- 維持すること: 発散に関わらない既存の実装とレビューでの修正。世代 2 以降では、参照資料にあるポストモーテムの申し送りの方針も維持する。この方針とその申し送りが避けるとしたことは、それらを知らずに書かれたレポートの Fix proposal より優先すると添える: 源泉はそれらの範囲内で除き、範囲内のどの変更でも除けない源泉は、方針にあることを設計に明記して世代のポストモーテムに委ねる。
- 避けること: レポートが源泉として挙げた形を再び持ち込むこと。世代 2 以降では、ポストモーテムの申し送りが避けるとしたことも避ける。
- 戻り先の候補: この世代でこれまでに作ったすべての TP を、名前、コミット、その時点で保持する内容とともに挙げる。g{g}c1 の TP-A は開始コミットで、実装前である。g{g}c{k} の TP-B は、サイクル k の `/cdev:coding` の後で、そのレビュー修正の前である。k > 1 の g{g}c{k} の TP-A は、サイクル k-1 のレビューの後のコードである。現在の先頭に積むことが既定であること、戻す場合は TP の内容をファイルに復元して前方へコミットし（コミットは `/cdev:coding` が行う）、履歴は書き換えないことを併記する。
- 参照資料: 発散調査レポート、世代 2 以降ではポストモーテムの申し送り（状態ファイルにある、その世代の最初のサイクルの `handoff`）、この世代の各サイクルの設計ドキュメント（`coding-result.json` の `design_paths`）、レビュードキュメント（`rounds-result.json` の `doc_paths`）、最終レポート（`rounds-result.json` の `final_report_path`）。結果ファイルからはこれらのパスだけを Read する。

## ステップ 1 — 初期化

1. `git rev-parse --show-prefix` の出力が空でない場合は、スキルにはリポジトリルートでの起動が必要である旨のエラーを表示してスキルを終了する。
2. オプションを解析して検証し（§ オプション）、§ 動作要件 を確かめる。
3. `{timestamp}`（`YYYYMMDD-HHMMSS`）、`{doc_lang}`（チャットの言語）、`{repo_root}`、`{loop_branch}`、`{loop_dir}` を確定する。
4. 次の場合はエラーを表示して終了する:
   - `git check-ref-format --branch {loop_branch}` が失敗する。
   - `git branch --list` が、`{loop_branch}`、`{loop_branch}/*`、`{loop_branch}-g*`、`{loop_branch}-tp`、`{loop_branch}-tp/*` のいずれかに当たるブランチを示す。`{loop_branch}/*` のブランチは `refs/heads/{loop_branch}` と共存できず、成果物ブランチを作れなくなる。
   - `{loop_dir}` が既にあり、空でない: 以前の実行が残した結果ファイルを、結果を書かずに終わった内側スキルの結果として誤読する。
5. `${CLAUDE_PLUGIN_ROOT}/scripts/del-tmp.sh --dry .claude/tmp/cdev-loop-{timestamp}` を実行する。シンボリックリンクの `.claude` または `.claude/tmp` はこれで拒否される。非ゼロ終了した場合はそのエラーを表示してスキルを終了する。`{loop_dir}` ではなくこのパスを渡す: del-tmp.sh は `.claude/tmp/` の外のパスを拒否する。その後 `mkdir -p` で `{loop_dir}` を作成する。
6. 開始コミット S を `git rev-parse HEAD` で記録する。`git status --porcelain` が何かを出力する場合は、未コミットの変更は S に含まれず、実行の対象外である旨をコンソールに示す。
7. `skill_dir` を記録し、`position` を g = 1、c = 1、`init` として `state.json` を初期化し、ステップ 2 へ進む。

メイン作業ツリーのソースは変更しない。フェーズの合間は `{repo_root}` にいる。

## ステップ 2 — コーディングフェーズ

1. `position` を `coding` にする。コンソール: `## Loop g{g}c{c} — Coding`。
2. c = 1 の場合は作業ブランチを S に作成し、その世代の項目を最初のサイクルとともに記録する。そのサイクルの `handoff` は、g1 では null、それ以降は直前のポストモーテムの申し送りのパスとする。
3. TP-A を作成する: c = 1 の場合は S に、それ以外は作業ブランチの先頭に作る。コミットとともに記録する。
4. `{loop_dir}/g{g}c{c}/` を作成し、次の引数で `cdev:coding` を実行する（§ 内側スキルの実行）。g1c1 以外のすべてのサイクルで `--handoff` を加える:

   ```
   cdev:coding --worktree={loop_branch}-g{g} --output {loop_dir}/g{g}c{c}/design --result {loop_dir}/g{g}c{c}/coding-result.json --team-tag g{g}c{c}-{hhmmss} --commit-always [--handoff {loop_dir}/g{g}c{c}/handoff.md] [{coding_args}] {task}
   ```

5. 戻ったら `coding-result.json` を Read する。
   - ファイルがない、または有効な JSON でない、`aborted` が null でない、`kept_worktree` が null でない、のいずれかであれば、コーディングフェーズは異常終了している: エラー終了とする（ステップ 6）。
   - それ以外では、その結果と警告を記録し（§ 状態ファイル）、作業ブランチの先頭に TP-B を作成して記録し、ステップ 3 へ進む。QA や解釈テストが未通過でも進む。

## ステップ 3 — レビューフェーズ

1. `position` を `review` にする。コンソール: `## Loop g{g}c{c} — Review`。
2. 次の引数で `creview:rounds` を実行する。`--base` を世代の最初の TP-A とし、どのサイクルの Round 1 も世代全体を S からの差分としてレビューさせる: 差し戻しは、それまでの修正に横断的に手を入れる。

   ```
   creview:rounds {loop_dir}/g{g}c{c}/review --worktree={loop_branch}-g{g} --incremental --base {loop_branch}-tp/g{g}c1-coding-start --on-divergence stop --result {loop_dir}/g{g}c{c}/rounds-result.json [{rounds_args}]
   ```

3. 戻ったら `rounds-result.json` を Read し、その結果と警告を記録する。
4. その内容で進み先を決める:
   - ファイルがない、または読めない、`error` が null でない、`kept_worktree` が null でない、`end_reason` が `converged`、`max-rounds`、`divergence` のいずれでもない: エラー終了とする（ステップ 6）。
   - `converged` または `max-rounds`: ステップ 5 へ進む。
   - `divergence` で、`divergence_report_path` が null か、ファイルを指していない: 警告を記録し、その世代の `unresolved_divergence` を true にしてステップ 5 へ進む。
   - `divergence` で、その世代の `sendbacks` が `--max-sendbacks` 未満: ステップ 4 へ進む。
   - それ以外の `divergence`: `unresolved_divergence` を true にしてステップ 5 へ進む。

## ステップ 4 — 差し戻し

1. c とその世代の `sendbacks` を 1 増やし、新しいサイクルの項目と、`sendback` にした `position` とともに、1 回の書き込みで記録する。コンソール: `## Loop g{g}c{c} — Send-back`。
2. 差し戻しの申し送り（§ 申し送り）を `{loop_dir}/g{g}c{c}/handoff.md` に書き、そのパスをサイクルの `handoff` に記録して、ステップ 2 へ戻る。

## ステップ 5 — ポストモーテムとグランドリセット

1. `position` を `postmortem` にする。コンソール: `## Loop g{g} — Post-mortem`。
2. `Agent(subagent_type="general-purpose", prompt=...)` でポストモーテムをフォアグラウンドで起動する。`{handoff_path}` は、g が `--max-generations` 未満であれば `{loop_dir}/g{g+1}c1/handoff.md`、それ以外は `(none)` とする。

   ```
   最初の行動として `${CLAUDE_PLUGIN_ROOT}/skills/loop/templates/postmortem.md` を必ず Read する。Read 完了前に他の判断・行動・ツール呼び出しを行わない。Read 後はその指示に従う。

   変数（テンプレート中の {{...}} placeholder を置換）:
   - plugin_root: ${CLAUDE_PLUGIN_ROOT}
   - main_root: (none)
   - target_dir: {repo_root}
   - task: {task}
   - state_path: {loop_dir}/state.json
   - generation: {g}
   - remaining_generations: {--max-generations から g を引いた値}
   - pursuit: {--pursuit 指定時は true、それ以外は false}
   - doc_lang: {doc_lang}
   - postmortem_md_path: {loop_dir}/g{g}/postmortem.md
   - postmortem_json_path: {loop_dir}/g{g}/postmortem.json
   - handoff_path: {handoff_path}

   戻り値に template_id（テンプレートの frontmatter から Read）を含める。
   ```

3. 戻り値の `template_id` が `158ca65c-c8f4-4d8f-bb6d-ce62fd015be1` であり、`postmortem.json` がテンプレートの書式の有効な JSON で、次を満たす場合に、結果を受け入れる:
   - `verdict` が `finish`: `adopted_generation` が 1 から g までの整数である。
   - `verdict` が `redo`: `basis` が `residual`、または `--pursuit` 指定時は `improvement` でもよい。さらに `{handoff_path}` が `(none)` でなければ、`handoff_path` がそれと一致し、既存のファイルを指す。

   それ以外では、もう 1 度だけ起動する。2 度目の結果も受け入れられない場合は、判定を finish、採用世代を g として代替し、その理由を `postmortem.fallback` と `warnings` に記録する。`postmortem.md` と申し送りは Read しない。
4. 判定をその世代の `postmortem` に記録する。
5. `redo` で g が `--max-generations` 未満なら、グランドリセットとする: g を 1 増やし、c = 1 として、ステップ 2 へ戻る。新しい作業ブランチとその TP-A はステップ 2 が S に作る。それ以外では、`adopted_generation` を判定の採用世代（`redo` の場合は g）とし、通常終了としてステップ 6 へ進む。

## ステップ 6 — 終了処理

1. `position` を `finish` にする。コンソール: `## Loop — Finish`。
2. 通常終了では、採用世代の作業ブランチの先頭に成果物ブランチ `{loop_branch}` を作成する。失敗した場合も通常終了のままとする: そのエラーを `end`（`output_branch` は null）と `warnings` に記録し、採用世代の作業ブランチが同じコミットを持つことを報告する。エラー終了では成果物ブランチを作成しない。
3. `end` を記録し、`{loop_dir}/loop-summary.md` を `{doc_lang}` で、`${CLAUDE_PLUGIN_ROOT}/rules/document.md` に従って書く。内容は次のとおり:
   - 各世代と各サイクルの終了理由。エラー終了では、止まったステップとエラー。
   - 差し戻し、各ポストモーテムの判定（`summary_line`、redo では `basis`）、採用世代。
   - TP の一覧と、それらをまとめて削除するためにユーザーが実行するコマンド: `git for-each-ref --format='%(refname:short)' 'refs/heads/{loop_branch}-tp/' | xargs git branch -D`。
   - 警告と、残ったワークツリー。
4. コンソールに報告する。通常終了では、成果物ブランチ、`loop-summary.md` のパス、世代数・サイクル数・差し戻し回数と各世代の判定。エラー終了では、止まったステップ、エラー、最後の作業ブランチ、`loop-summary.md` のパス。push と pull request の作成は行わない。

## 停止条件

次の場合に限り、自動の続行をやめ、ステップ 6 でエラー終了とする:

- ステップ 1 の前提を満たさない。この場合はステップ 1 で終了し、`loop-summary.md` は書かない。
- `/cdev:coding` が異常終了した（ステップ 2）。
- `/creview:rounds` がエラーで終わった（ステップ 3）。
- 結果ファイルが残ったワークツリーを示す。そのブランチを次のフェーズがチェックアウトできない。
- 作業ブランチか TP を作成できない、または作業ディレクトリを `{repo_root}` に戻せない。
- `state.json` を書けない、または検証に通るよう直せない。§ 状態ファイル の指示どおりに終了する。

それ以外は、ユーザーに尋ねずに自分で判断して続ける。エラー終了でも、それまでに作った TP と作業ブランチはすべて残す。
