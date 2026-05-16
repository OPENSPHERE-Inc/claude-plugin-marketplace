---
name: estimate
description: /creview:triage ステップ 2 で担当指摘のコスト見積を一括実施する見積サブエージェント向けプロンプト
template_id: 8b2d5f1c-7a93-4e64-b8d1-2c5e9a3f7b48
---

担当指摘 `{{ids}}` のコスト見積を一括実施する（調査と判定のみ、修正はしない）。`{{plugin_root}}/rules/sub-agent.md` を Read し共通禁止事項を遵守する。

入力（id == "{finding-id}" で引く）:

- レビュードキュメント `{{document_path}}` — METADATA マーカー前後から description / location / severity を取得
- `{{tmp_dir}}/triage.json` — items 配列から id 一致で verdict / reason を取得

各 id について:

1. 関連ソースを読み、具体的な修正プランを作成する。各編集を `{file:line} — {変更内容}` の形式で書き出す。コメント追加（FIXME / TODO 含む）が含まれる場合は、想定するコメント文言と挿入箇所も含める。以降の cost / future / 判定は、このプランに基づいて行う。
2. 拡散シグナル該当判定（複数選択可、none も可）:
   a. 新概念の導入（未使用のライブラリ / API / 言語機能）
   b. 修正範囲の拡大（現ブランチ未修正のファイル / モジュール）
   c. 非同期実行タイミング干渉（UI スレッドブロッキング、コールバック順序、Qt 接続タイプ変更等）
   d. 将来コスト（暫定対処 / FIXME 押し出し / 抽象化漏れ）
   e. FIXME 起源の Will Fix（元々 FIXME/TODO 由来、または FIXME 化提案がトリアージで Will Fix に倒れた）
   f. ターゲット変更（ビルド / 実行ターゲットのバージョン変更等）
3. cost（S/M/L）と future（S/M/L）を算出。算出根拠は 1〜2 文。
4. 一次判定（重要度問わず Downgrade / Alternative 選択可）:
   - Maintain — コスト妥当、修正進行。
   - Downgrade — 判定を覆して修正しない。代替手段なし。必要に応じて「別 PR 推奨」を理由に含める。
   - Alternative — 判定を覆して FIXME 付与等の軽量対処。FIXME 文言の方向性を簡潔に示す。必要に応じて「別 PR 推奨」。

   cost == L は Downgrade（理由に「別 PR 推奨」を含める）。L 規模は /creview:respond の自動修正対象外でユーザー判断が必要なため（修正不要の意味ではない）。

   cost が S/M の場合: 重要度が高い指摘ほど Downgrade の根拠は厳しく問われる。Critical / Major は通常 Alternative または「Downgrade + 別 PR 推奨」が望ましい。Minor / Info は Downgrade 許容されやすい。

5. コメント追加の必要性チェック（修正方針にコメント追加が含まれる場合のみ実施）。コメント追加はコード自体の問題を解決しないため、cost が低くても（数行追加程度の軽微な変更でも）必要性を独立して厳しく判定する。コストの低さは採用理由にならない。下記の各基準に該当するコメントは原則として除外する。除外後の修正内容に応じて一次判定を確定させる:
   - 除外後もコード変更が残る → Maintain（コメント抜きの修正方針に更新）
   - 除外後に何も残らない → Downgrade（理由に「別 PR 推奨」を含めるかは指摘の重要度で判断）

   却下基準（該当コメントは除外）:
   a. `{{plugin_root}}/rules/comment.md` 違反（多段落の正当化、変更履歴・チャット文脈に依存した記述、自明な what の説明等）。
   b. 特定読者（チャットユーザー、レビュアー、特定の同僚等）への伝達を目的としたコメント。コメントは将来の第三者読者向けの情報源であり連絡媒体ではない。

   降格基準（コメントの情報価値が薄い、該当コメントは除外）:
   c. 同一ファイル内のソースを読めば把握できる内容のコメント（命名・構造・直近の式から自明な what / how の言い換え）。
   d. 関数内コメントが呼び出し側（caller）の挙動・利用前提を説明している場合。呼び出し側に関する説明は呼び出し側に書く。

   FIXME / TODO 個別判定（Alternative 検討時）:
   e. 後続 PR 推奨として最終レポートに記録すれば足りる事項は、ソースに FIXME を残さず Alternative → Downgrade（理由に「別 PR 推奨」）に切り替える。FIXME を残すのは、当該箇所を将来編集する人が編集時に必ず気付く必要がある場合に限る（編集時に踏みやすい落とし穴、ロジックの暫定実装、特定条件の未対応等）。

6. `{{tmp_dir}}/estimates/{finding-id}.json` に Write。

`{{tmp_dir}}/estimates/{finding-id}.json` 形式: `{id, specialist, verdict（Maintain | Downgrade | Alternative）, cost（S|M|L）, future（S|M|L）, signals（["a","b",...] または []）, fix_plan, rationale, memo_value}`

fix_plan 形式: 文字列配列。各要素は `"{file:line} — {変更内容}"` 形式。コメント追加の場合はコメント文言を含める。ステップ 5 で確定したプランを反映する:

- Maintain: コード変更編集（ステップ 5 のコメント必要性チェックでの除外後）
- Alternative: FIXME / TODO 付与のみ
- Downgrade: 見積対象となった却下プラン（そのまま記録）

memo_value 形式:

- Maintain: `▶️ Maintain — Cost: {cost}, Future: {future}, Signals: {a,b,... または none}`
- Downgrade: `🔻 Downgrade — Cost: ..., Future: ..., Signals: ... — {格下げ理由}`
- Alternative: `🚧 Alternative — Cost: ..., Future: ..., Signals: ... — FIXME 付与: {方向性}`

戻り値: `{items: [{id, verdict}, ...], template_id}`（items は担当 ids 全件分）。`template_id` は本テンプレートの frontmatter から Read した値をそのまま含める。
