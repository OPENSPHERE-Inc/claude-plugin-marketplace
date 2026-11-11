---
name: prompt-fix
description: /creview:respond ステップ 4 で、解釈テストに不合格だった AI 向けプロンプトファイルを、すべての unclear 項目にプロンプトから回答できるよう prompt-sensei が修正するためのプロンプト
template_id: cbbd9597-ca26-4308-a6d1-67cb18498aff
---

`{{result_path}}` で `pass` が false かつ `untested` が null の各ファイルについて、その `unclear_items` のすべてにプロンプトから回答できる状態にする。プロンプトは `{{plugin_root}}/rules/prompt.md` § 契約型プロンプトが定める契約型を保つ。`{{plugin_root}}/rules/sub-agent.md` を Read し共通禁止事項を遵守する。

- プロンプトが定めるゴールや契約に関わる項目には、その項目が関わる結果や契約を明示する。
- ゴールと契約を知る AI なら正しく実行できる方法についての項目には、ゴールを明示し、方法が読み手に委ねられていると読み取れる形にする。どの契約も求めない手順、場合分け、文言は足さない。
- 各修正がその指摘に対して確立した内容（🚧 Alternative の見積が指示した FIXME を含む）は損なわない。`{{tmp_dir}}/statuses/*.jsonl` が示す、そのファイルを変更した修正の指摘を `{{document_path}}` で読む。

編集はそれらのファイルに限る。その後、変更した箇所を `{{plugin_root}}/rules/prompt.md` に照らして再点検し、持ち込んだ違反を修正する。

戻り値: `{files: [path], template_id}`。`files` は編集したファイルのリポジトリ相対パス。`template_id` は本テンプレートの frontmatter から Read した値をそのまま含める。
