<!-- ADR skeleton: replace {...} placeholders; keep every heading.
File name: {review-doc basename}-adr-{finding-id}.md, in the review document's directory
({review-doc basename} is the review document filename without .md;
e.g. review-round1.md + M-1 → review-round1-adr-M-1.md).
Prose language: same as the review document's Finding descriptions. Headings, the
Source / Status keys, and the Status values stay fixed.
Status lifecycle: Proposed (created at estimate; the user may edit the file before the
fix phase) → Accepted (the fix implemented the decision) → Superseded by {adr-filename}
/ Reverted (a later decision replaced or rolled back this one).
Append a History entry for every status transition or content update; never delete
existing History entries. -->

# ADR: {finding-id} — {decision title}

- **Source:** {review document filename} / {finding-id}
- **Status:** {Proposed | Accepted | Superseded by {adr-filename} | Reverted}

## Context

{The problem the finding raises and the constraints on the solution — 1-3 sentences}

## Decision

{The chosen approach and the decisive reason — 1-3 sentences}

## Alternatives

- {rejected approach} — {rejection reason}

## Consequences

{Accepted trade-offs, deferred work (FIXME), impact on future changes}

## History

- {YYYY-MM-DD} {review document filename} / {finding-id} — Created (Proposed)
- {YYYY-MM-DD} {review document filename} / {finding-id} — {update summary}
