# Won't Fix Guidelines

Apply these when deciding a review finding's triage verdict. A finding is `Won't Fix` when any of the following applies:

1. Out of scope of the branch diff.
2. Existing-code bug (not introduced by the branch).
3. Hypothesis error / technical mistake.
4. Inferable as acceptable from the project's purpose, use case, or assumed users.
5. Preference-based refactoring (no rationale grounded in correctness, safety, performance, or maintainability).
6. Reproducibility unclear; e2e verification needed.
7. The same finding (same location, same content) was already processed in a past round (only judgable when `{{previous_round_doc_paths}}` is provided). Identity is judged by matching file:line and the finding summary. Applicable patterns:
   - Already `status: 🟢 Fixed` in a past round (an edge case that does not normally occur; since it has been re-detected, explicitly state "already Fixed in a previous round" in the reason field).
   - `triage: 🚫 Won't Fix` in a past round (state "same as previous-round Won't Fix" in the reason field, and concisely transcribe the past decision's reason).
   - `estimate: 🔻 Downgrade` in a past round (state "same as previous-round Downgrade" in the reason field, and concisely transcribe the past decision's reason).

High-severity exception: For Critical / Major Won't Fix, explicitly state "recommend separate PR" in the reason field (e.g. "Won't Fix — Existing-code bug. Recommend fixing in a separate PR.").

Apply guideline 7 only to findings whose `stage` is `pending_triage`. A finding whose `stage` is `feedback` was processed in a past round and then received 💬 Feedback from verification, so having been processed already is its premise; guideline 7 does not apply to it.
