<!-- 骨組み例。散文とラベル（日付 / 範囲 / レビュアー / サマリー / 件 等）は doc_lang で記述する。重要度見出し・finding-id・METADATA マーカーは変更しない。カテゴリラベルは doc_lang で記述する。Mode の箇条書きは adversarial 実行時のみ出力する。値 `adversarial` は訳さない。PR と Trust の箇条書きはプルリクエストのレビュー時のみ、Branch の箇条書きはブランチ上のレビュー時のみ出力し、いずれもラベルも含めてそのまま出力する。 -->

# 並列コードレビューレポート — Round {N}

- **日付:** YYYY-MM-DD
- **ラウンド:** {N}
- **モード:** adversarial  <!-- adversarial 実行時のみ出力 -->
- **PR:** {url} (head {head_sha}, base {merge_base})  <!-- プルリクエストのレビュー時のみ出力 -->
- **Branch:** {branch}  <!-- ブランチ上のレビュー時のみ出力 -->
- **Trust:** {trust}  <!-- プルリクエストのレビュー時のみ出力。値は on または off -->
- **範囲:** {レビュー対象の説明}
- **レビュアー:** {使用した全レビュアーのカンマ区切りリスト}

## Critical

### C-1 — `file.cpp:42` [バグ/保守性]

- **レビュアー:** cpp-sensei, obs-sensei

**指摘:**

{問題の説明}

<!-- METADATA(C-1) -->
<!-- /METADATA(C-1) -->

---

## Major

### M-1 — `other.cpp:120` [可読性]

- **レビュアー:** qt-sensei

**指摘:**

{問題の説明}

<!-- METADATA(M-1) -->
<!-- /METADATA(M-1) -->

---

## Minor

### mi-1 — `widget.cpp:88` [スタイル]

- **レビュアー:** qt-sensei

**指摘:**

{問題の説明}

<!-- METADATA(mi-1) -->
<!-- /METADATA(mi-1) -->

---

## Info

指摘無し

---

## サマリー

- **Critical:** N 件
- **Major:** N 件
- **Minor:** N 件
- **Info:** N 件
- **合計:** K 人のレビュアーから N 件の指摘（D 件の重複を統合）
