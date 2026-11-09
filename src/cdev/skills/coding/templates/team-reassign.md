---
name: team-reassign
description: cdev /coding ステップ 2 のチーム再編成タスク（dev-helper）向けプロンプト。閉じた設計が追加・変更する各ファイルを team-analysis の割り当て規則で coder に割り当て、合う既存のメンバーがいなければ coder / reviewer を加える
template_id: 6dd623b7-91fb-45a7-acf4-cf08646878aa
---

設計セクションが追加・変更する各ファイルがちょうど 1 人の coder のスコープに入り、各 coder が領域の一致する reviewer とペアになるよう、チームの coder を再編成し、その結果の coder / reviewer を `{{output_path}}` に書く。実装は一切しない。

設計セクション: `{{design_paths}}` 内のすべてのファイルを Read する。
ロスター: `{{roster_path}}`（team-analysis の結果）
このセッションで使用済みの name: `{{taken_names}}`

`{{plugin_root}}/skills/coding/templates/team-analysis.md` を Read し、その割り当て規則を使う。そのテンプレート自体のタスクは行わない。エージェントプールは `{{plugin_root}}/rules/agents-detection.md` § 列挙 に従って構築する。

制約:

- ロスターの coder と reviewer はすべて、`name`・`slug`・`reviewer` を変えずに残す。
- 設計セクションが追加・変更する各ファイルは、次の 3 つをすべて満たす coder ちょうど 1 人のスコープに入り、ほかの coder のスコープには入らない（スコープがファイルを持つとは、そのファイルか上位のディレクトリを挙げていることを指す）:
  - 割り当て規則上、その coder がそのファイルを持てる: プロンプトファイルはスコープにほかのソースがない coder にだけ、それ以外のファイルはスコープにプロンプトファイルがない coder にだけ渡す。
  - そのファイルが、その coder のペアの reviewer の領域に入る。設計が AI 向けプロンプトファイルでないファイルのために追加するテストはテスト対象のファイルの領域に、AI 向けプロンプトファイルのためのテストはテスト自身の領域に入るものとする。
  - そのファイルが、設計が AI 向けプロンプトファイルでないほかのファイルのために追加するテストで、再編成後にそのほかのファイルを持ち、スコープにプロンプトファイルがない coder がいれば、テストを持つのはその coder である。AI 向けプロンプトファイルのためのテストは、プロンプトファイルでないほかのファイルと同じく、スコープにプロンプトファイルがない coder に渡す。
- ファイルを持つ coder が 3 つを満たせば、そのファイルはその coder に残す。満たさなければ、そのファイルを持つスコープから外し、3 つを満たす既存 coder に、いなければ新しい coder に渡す。
- 新しいメンバーの `slug` は kebab-case とし、そのロール名（`coder-{slug}` / `reviewer-{slug}`）が `{{taken_names}}` にも、出力のほかのエントリのロール名にも重ならないものにする。
- 割り当てるのは `{{target_dir}}` 配下のパスだけとする。
- `scope` / `reason` / `rationale` は {{doc_lang}} で記述し、`name` / `slug` はそのまま。

`{{output_path}}` の形式。ロスターのものを含むすべての coder と reviewer を挙げ、各フィールドはロスターの `coders` / `reviewers` と同じ意味を持つ:

```
{"coders": [{"name": <string>, "slug": <string>, "scope": <string>, "reviewer": <string>, "reason": <string>}], "reviewers": [{"name": <string>, "slug": <string>, "reason": <string>}], "rationale": <string>}
```

新しい reviewer の `name` は agents-detection.md § 結果 の指定どおりに記録する。

リーダー（`SendMessage` の `to: "main"`）へ完了を 1 行で報告する。`{{output_path}}`、追加した coder 数と reviewer 数、スコープが変わったロスターの coder 数を記す。
