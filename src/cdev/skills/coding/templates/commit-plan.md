---
name: commit-plan
description: cdev /coding ステップ 5 で、作業ツリーの変更を論理的な変更ごとのコミットに分け、commit-plan.py に渡す計画を書くコミット計画タスク（dev-helper）向けプロンプト
template_id: 24c5ea40-4550-47e6-bd21-9026658866f3
---

`{{plugin_root}}/rules/commit-plan.md` を Read し、それに従って、作業ツリーの変更を論理的な変更ごとのコミットに分ける計画を `{{output_path}}` に書き、`commit-plan.py check` に合格させる。

起点と対象: B は `HEAD`、T は `{{target_dir}}` の作業ツリー。`commit-plan.py` の `paths` と `check` は、`--worktree` と、`{{exclude}}` の各パスごとの `--exclude` オプションを付けて実行する。

入力: タスク `{{task}}`、`{{design_paths}}` の設計ドキュメント、`paths` が挙げるファイルとその差分。未追跡の新しいファイルは `git diff` に現れないので Read で読む。

`{{rejection}}` が `(none)` でなければ、前回の計画が受理されなかった理由である `check` の `errors` を述べている。それが解消するように計画を直す。

書くのは `{{output_path}}` だけで、共有インデックス、ref、作業ツリーを変えない。計画ファイルはルールの § 計画ファイル のレコードファイルであり、`{{plugin_root}}/rules/teammate.md` § ツール の、`.jsonl` ファイルを 1 つのオブジェクトとして 1 行で書く規則は適用しない。

完了をリーダーへ報告する（`SendMessage` の `to: "main"`）: `{{output_path}}` と計画のコミット数を 1 行で示し、`errors` のない失敗があればその `error` を添える。
