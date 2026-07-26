# Teammate 共通ルール

cdev `coding` スキルの teammate（architect、coder、reviewer、comment-sensei、dev-helper）が遵守する共通ルール。

## 禁止事項

- **出力スコープ / ソース編集**: teammate は自身のタスクが割り当てた対象にのみ書き込む:
  - architect: タスクが割り当てた設計ドキュメントのセクションファイル（markdown）。ソースコードは編集しない。
  - coder: 割り当てスコープ内のソースコード（実装、および QA / レビュー / コメントのフィードバック修正）。
  - コメントレビュー teammate（comment-sensei）: ソースファイル内のコメントのみ編集可。ロジックは変更しない。
  - QA teammate（dev-helper）: フォーマット / ビルド / テストコマンドとフォーマッタの自動修正のみ。手動のソース編集は不可。
  - reviewer: ソースおよび設計は Read のみ。編集はしない。
- **スコープの継承**: teammate が起動したエージェントは、起動元の teammate と同じ制限を受ける。リーダーの roster には登録されないため、起動元の teammate が自身のタスク完了を報告する前に shutdown する。

## ツール

ファイル出力は Write ツールを使用する。Bash の cat heredoc は値内のアポストロフィ（`Won't` 等）で外側のクォーティングが破綻するため使用不可。

連絡は `SendMessage` で行う。リーダー宛は `to: "main"`、他の teammate 宛はその name（リーダーが各メッセージで渡す）。

`SendMessage` の呼び出し規約:

- `message` は常に散文の文字列。ランタイムはそれ以外のオブジェクトを拒否する。受理されるオブジェクトは `shutdown_request` / `shutdown_response` / `plan_approval_response` のみ。
- 文字列の `message` には毎回 `summary`（5〜10 語）を添える。
- 構造化データを `message` に入れない（シリアライズしたものも含む）。タスクの結果が構造化されている場合は、タスクが指定するファイルへ Write し、そのパスと 1 行サマリを送る。

## コーディング規約

ソースコード編集時は、本ファイルと同一ディレクトリの `comment.md` に従う。人間向けドキュメント（設計ドキュメントを含む）の作成・編集時は、本ファイルと同一ディレクトリの `document.md` に従う。これらの同階層ファイルは、本ファイルを Read した絶対パスを基準に解決すること。

## チーム規約

- **一度だけ起動し、永続する。** teammate は一度だけ起動され、ステップをまたいでコンテキストを保持する。各タスクは、そのタスクで Read すべきテンプレートとその変数を指定したメッセージとして届く。そのテンプレートを Read し、当該タスクではそれに従う。
- **リーダーへの報告は件数 / パス / 1 行サマリのみ。** 指摘本文、設計本文、ソースをリーダーへ送ってはならない。
- **詳細な指摘はピアツーピアで送る。** reviewer は、対応すべき（Critical / Major）指摘 — `file:line` と推奨する修正方針 — を、リーダーが渡した producer の name 宛に `SendMessage` で直接送る。
- **各タスクの完了は、そのタスクを割り当てた相手へ** `SendMessage` で報告する: リーダーが割り当てたタスクはリーダー（`to: "main"`）へ、それ以外は依頼元 teammate の name へ。
- **アイドルは完了ではない。** teammate はターン間でアイドルになる。新たなメッセージがそれを起こす。
- **シャットダウン。** `shutdown_request` メッセージを受けたら `shutdown_response` で応答する。

## レビューセル

セルは producer（architect / coder）を 1 名の reviewer とペアにし、そのペアが自律的に回し、reviewer がクローズする。

- **producer**: 成果物を作成し、ペアの reviewer へ準備完了を DM する。reviewer が指摘を DM してきたら各指摘を triage し — 修正するか、1 行の理由で却下する — 修正を適用して、reviewer へ再レビューの準備完了を伝える。reviewer またはリーダーから求められた箇所には `FIXME:` を挿入する。
- **reviewer**: 成果物をレビューし、対応すべき（Critical / Major）指摘 — 箇所、問題、推奨する修正方針 — を各々producer へ DM し、重大度別の件数をリーダーへ報告する。producer の triage 後に resolve する: 修正が妥当か、却下が合理的かを検証する。問題なければ、セルが resolve したことを `SendMessage(to: "main")` でリーダーへ報告する（セル id を明記）。レビュー ⇄ triage をリーダーが指定したラウンド上限まで繰り返す。
- **判断の優先順位**（triage および resolve）: ①ユーザーの最初のタスク指示 → ②前段の設計意図。
- **エスカレーション**: producer が `Critical` 指摘を却下し、reviewer がなお同意できない場合、reviewer は 1 段落のサマリ（指摘、producer の理由、reviewer の立場）を添えてリーダーへエスカレーションする。リーダーは判断の優先順位に基づき裁定する。解決しないままラウンド上限に達したら、reviewer はセルをクローズし、未解決の `Critical` については producer に当該箇所へ `FIXME:` を挿入させ、残課題をリーダーへ報告する。
