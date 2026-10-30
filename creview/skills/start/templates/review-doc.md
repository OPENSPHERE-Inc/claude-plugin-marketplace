<!-- Skeleton example. Write the prose and labels (Date / Scope / Reviewers / Summary / counts, etc.) in doc_lang. Do not change the severity headings, finding-id, or METADATA markers. Write the category labels in doc_lang. The Mode bullet is output only for an adversarial run; keep its value `adversarial` untranslated. The PR and Trust bullets are output only for a pull request review, and the Branch bullet only for a review on a branch; keep them verbatim, labels included. The Trust value is `on` or `off`. End each of these three bullets at its value, with nothing after it. -->

# Parallel Code Review Report — Round {N}

- **Date:** YYYY-MM-DD
- **Round:** {N}
- **Mode:** adversarial  <!-- output only for an adversarial run -->
- **PR:** {url} (head {head_sha}, base {merge_base})
- **Branch:** {branch}
- **Trust:** {trust}
- **Scope:** {description of the review target}
- **Reviewers:** {comma-separated list of all reviewers used}

## Critical

### C-1 — `file.cpp:42` [Bug/Maintainability]

- **Reviewers:** cpp-sensei, obs-sensei

**Finding:**

{description of the issue}

<!-- METADATA(C-1) -->
<!-- /METADATA(C-1) -->

---

## Major

### M-1 — `other.cpp:120` [Readability]

- **Reviewers:** qt-sensei

**Finding:**

{description of the issue}

<!-- METADATA(M-1) -->
<!-- /METADATA(M-1) -->

---

## Minor

### mi-1 — `widget.cpp:88` [Style]

- **Reviewers:** qt-sensei

**Finding:**

{description of the issue}

<!-- METADATA(mi-1) -->
<!-- /METADATA(mi-1) -->

---

## Info

No findings

---

## Summary

- **Critical:** N
- **Major:** N
- **Minor:** N
- **Info:** N
- **Total:** N findings from K reviewers (D duplicates merged)
