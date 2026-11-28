---
name: fix
description: /creview:respond ステップ 2 で担当指摘を修正する修正サブエージェント向けプロンプト
template_id: 2f8a1c5d-7b94-4e63-a1c8-5d3f9b2e7a14
---

担当指摘 `{{ids}}` を `{{stage}}` 段で順次修正する。`{{plugin_root}}/rules/sub-agent.md` を Read し共通禁止事項を遵守する。

id の修正が行う編集は、その修正要件（sub-agent.md § 修正要件）が求める編集と、対訳の追随のようにプロジェクトの CLAUDE.md がそれに伴って求める編集である。修正が触れるかどうかによらず、sub-agent.md のソース編集の項がこの段の修正サブエージェントに許す種類のファイルを、この段のファイルとする。修正の編集のうち、この段のファイルに落ちるものと、この段がステップ 5 を行う場合はその ADR ファイルに落ちるものを行う。次のものは編集せずに残し、それぞれのファイルと変更を当該 id の `description` と `memo_value` に記す。ただし、当該 id のほかの段がすでに行った修正の編集は除く:

- この段のファイル以外のファイルに落ちる修正の編集。
- ラウンド固有のオーバーライドが作成を禁じるファイルに落ちる修正の編集。
- 修正の編集を超えて必要だと気付き、自分では行わない変更: この段のファイル以外のファイルにある当該指摘のスコープ内の穴、または修正がコードと食い違ったままにしたドキュメント。

入力（id == "{finding-id}" で引く）:

- レビュードキュメント `{{document_path}}` — ヘッダーから `- **Source:**` の箇条書きを、METADATA マーカー前後から description / location を取得し、メタデータブロックから当該指摘の確定判定を取得する: `Triage:`（Will Fix + 理由）、`Estimate:`（▶️ Maintain または 🚧 Alternative。Cost / Future / Signals を伴い、Alternative の場合は FIXME 付与の方向性も含む）、および `Verification:`。フィールドが繰り返す場合は最後の値を使う。
- `{{tmp_dir}}/targets.jsonl` — `items[]` が各 id の `assignee`、`stages`（当該 id を修正する段として定めたもの。`["code"]`、`["docs"]`、または `["code", "docs"]`。`docs` 段は、`code` 段が `docs_left: true` を返した id も修正する）、`estimate`（Maintain | Alternative）、`adr`（レビュードキュメントと同じディレクトリにあるその指摘の ADR ファイル名、または null）、`fix_plan`（`/creview:triage` の見積で確定した修正プラン。各エントリ `{file:line — 変更内容}` の文字列配列。空配列のこともある）を与える。
- `docs` 段のみ: `{{diff_path}}` — コード修正段の後に作業ツリーを HEAD と比べた `fetch-diff.sh` の出力で、コードが変わった箇所の手がかりとなる。この実行の前からある未コミットの変更を含む場合もある。

各 id について:

1. 当該 id の修正要件を起点とし、関連ソースを現在の状態で Read する。`docs` 段では、ドキュメントが記述するコードを、この実行のコード修正を含めて Read する。`{{diff_path}}` が `(none)` でなければそれも読み、当該 id の `{{tmp_dir}}/statuses/{finding-id}.jsonl` が存在すればそれも読む。
2. この段が行う修正の編集（CLAUDE.md のコーディング規約準拠）:
   - Estimate ▶️ Maintain: 通常の修正。`docs` 段では、編集を当該指摘のスコープ内にとどめ、修正の編集を超えて編集するドキュメントファイルを探さない。コードの動作を述べる編集では、記述するコードが現在行うことを述べる。修正要件がそれと異なる記述を求める場合はコードに従い、その食い違いを `description` と `memo_value` に記す。
   - Estimate 🚧 Alternative: FIXME: コメント追加のみ（ロジック変更なし。ドキュメントファイルの既存の記述も変えない）。文言は修正要件が与えるものに沿う。
3. セルフレビュー: 変更箇所再読、新たな問題（リグレッション・スレッド安全性・リソースリーク等）の混入を確認、見つけたら報告前に修正。
4. 修正にコメントの追加・変更が含まれる場合、`{{plugin_root}}/rules/comment.md` を Read し、追加・変更したコメントが同規律に違反していないかセルフチェックする。違反があれば報告前に修正する。
   - `FIXME:` / `TODO:` はステップ 2 の 🚧 Alternative のケースにのみ書く。この注記はその箇所をレビュー対象から外す根拠として恒久的に効くため、修正中に気付いた残余の穴を注記してはならない。▶️ Maintain では当該指摘のスコープ内で、この段のファイルにあるなら修正し、それ以外は注記せずに残し、`description` と `memo_value` には上の編集せずに残すものの一覧が求める場合に限り記す。
5. ADR（`code` 段で行う。`docs` 段では当該 id の `stages` が `code` を含まない場合に限り行う）:
   - `adr` が非 null: ADR を更新する — Status を `Accepted` にし、History エントリを追記する（日付 = `{{timestamp}}` の日付部を YYYY-MM-DD 形式で、`{レビュードキュメントのファイル名} / {finding-id}`、修正内容の 1 行要約）。Decision からの逸脱や実装中に行った設計判断があれば Decision / Consequences に記録する。
   - `adr` が null、`{{adr_flag}}` が on、かつ実装自体が恒久的なトレードオフを伴う複数の実行可能なアプローチから 1 つを選択した場合: レビュードキュメントと同じディレクトリに `{{{document_path}} の basename から .md を除いたもの}-adr-{finding-id}.md` を Status `Accepted`・Created History エントリ付きで Write する。スケルトンは `{{plugin_root}}/rules/adr-format.md` に従う。memo_value に ` — ADR: {ファイル名}` を追記する。
6. `{{tmp_dir}}/statuses/{finding-id}.jsonl` に Write。`docs` 段で当該 id の `stages` が `code` を含む場合は、コード修正段が書いたファイルに統合する: `id`、`specialist`、`verdict` と、`files` の既存のパスをすべて保つ。この段が変更したドキュメントファイルを `files` に加える。`text_only` は、コード修正段が true にしていれば true のまま保ち、それ以外は false にする。`description` と `memo_value` は両段を合わせた 1 つの修正として書き直し、コード修正段が編集せずに残した変更のうちこの段も行わないものはそのファイルとともに残し、` — ADR: {ファイル名}` があれば末尾に保つ。そのファイルがないか読めない場合は新しく書き、`files` にはこの段の変更だけを入れ、`text_only` は false とし、コード側の修正を確認できなかったことを `description` と `memo_value` に記す。

並列化制約（複数 id を担当する場合）:

- 同一ファイルに影響する複数 ids は順次処理（書き込み競合防止）。
- 異なるファイルに影響する ids は並列処理可。

`{{tmp_dir}}/statuses/{finding-id}.jsonl` 形式: `{id, specialist, verdict（targets.jsonl の estimate。Maintain | Alternative）, description（修正内容の簡潔な説明）, memo_value, files（この修正が変更したファイルのリポジトリ相対パス。ドキュメントファイルを含み、ADR ファイルは含めない）, text_only（ADR ファイルを `files` と同じく除き、この修正が行ったすべての編集が人向けテキスト（sub-agent.md § 人向けテキスト）に当たる場合に true。それ以外の場合と判断できない場合は false）}`

`description` と `memo_value` の散文は、`{{document_path}}` の既存 Finding 説明と同じ言語で記述する（`🟢 Fixed` ラベルと絵文字は固定）。

memo_value 形式（ステップ 5 で新規 ADR を作成した場合は ` — ADR: {ファイル名}` を末尾に追記する）:

- Maintain: `🟢 Fixed — {修正内容}`
- Alternative: `🟢 Fixed — FIXME コメントを {ファイル:行} に付与`（description にも同趣旨を含める）

戻り値: `{items: [{id, path, docs_left}, ...], template_id}`（items は担当した全 id を含む）。`docs_left` は、`code` 段で、当該 id の `stages` が `docs` を含まず、上の一覧の 1 項目目により編集せずに残した修正の編集がドキュメントファイルにある場合に true、それ以外は false とする。`template_id` は本テンプレートの frontmatter から Read した値をそのまま含める。
