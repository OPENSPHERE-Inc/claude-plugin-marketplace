# Teammate Common Rules

Common rules that teammates of the cdev `coding` skill (architect, coder, reviewer, comment-sensei, dev-helper) observe.

## Prohibitions

- **Output scope / source editing**: A teammate writes only to the target its task assigns:
  - Architect: the design-document section file the task assigns (markdown). No source-code edits.
  - Coder: source code (implementation, plus fixes for QA / review / comment feedback) within its assigned scope.
  - Comment-review teammate (comment-sensei): comment-only edits in source files; no logic changes.
  - QA teammate (dev-helper): format / build / test commands and formatter auto-fixes only; no manual source edits.
  - Reviewers: Read-only on sources and design; they do not edit.
- **Inherited scope**: An agent a teammate launches is bound by the same restrictions as that teammate. It is not in the leader's roster, so the teammate that launched it shuts it down before reporting its own task complete.

## Tools

Use the Write tool for file output. Bash cat heredoc is unusable because apostrophes inside values (e.g., `Won't`) break the outer quoting.

Communicate via `SendMessage`: the leader at `to: "main"`, other teammates by their agentId (the leader hands it to you in each message; a friendly name stops resolving once the recipient is idle).

`SendMessage` call rules:

- `message` is always a string of prose. The runtime rejects any other object; the only accepted objects are `shutdown_request` / `shutdown_response` / `plan_approval_response`.
- Send `summary` (5-10 words) alongside every string `message`.
- Never put a structured payload in `message`, serialized or otherwise. When a task's result is structured, Write it to the file the task names and send the path plus a one-line summary.

## Coding Conventions

When editing source code, follow `comment.md` in the same directory as this file. When writing or editing human-facing documentation (including design documents), follow `document.md` in the same directory as this file. Resolve these siblings relative to the absolute path you Read this file from.

## Team conventions

- **Spawn once, persist.** A teammate is spawned once and keeps its context across steps. Each task arrives as a message that names the template to Read for that task plus its variables; Read that template and follow it for that task.
- **Report to the leader = counts / paths / one-line summary only.** Never send finding bodies, design bodies, or source to the leader.
- **Route detailed findings peer-to-peer.** A reviewer sends its actionable (Critical / Major) findings — `file:line` plus the recommended fix direction — by `SendMessage` directly to its paired producer's agentId (the leader provides it).
- **Report each task's completion to whoever assigned it** via `SendMessage`, as it completes: the leader at `to: "main"` for a leader-assigned task, otherwise the requesting teammate's agentId.
- **Idle is not done.** A teammate goes idle between turns; a new message wakes it.
- **Shutdown.** On a `shutdown_request` message, reply with a `shutdown_response`.

## Review cell

A cell pairs a producer (architect / coder) with one reviewer; the pair runs it autonomously and the reviewer closes it.

- **Producer**: create the output, then DM the paired reviewer that it is ready. When the reviewer DMs findings, triage each — fix it, or reject it with a one-line reason — apply the fixes, and tell the reviewer you are ready for re-review. Insert a `FIXME:` at a location when the reviewer or leader asks for one.
- **Reviewer**: review the output; DM each actionable (Critical / Major) finding — location, issue, recommended fix direction — to the producer; report severity counts to the leader. After the producer triages, resolve: verify the fixes are adequate and the rejections reasonable. When satisfied, report the cell resolved to the leader via `SendMessage(to: "main")` (naming the cell id). Repeat review ⇄ triage up to the round cap the leader gave.
- **Judgment priority** (triage and resolve): (1) the user's original task instructions, then (2) the upstream design intent.
- **Escalation**: if the producer rejects a `Critical` finding and the reviewer still disagrees, the reviewer escalates to the leader with a one-paragraph summary (the finding, the producer's reason, the reviewer's position); the leader arbitrates by the judgment priority. On reaching the round cap without resolution, the reviewer closes the cell, has the producer insert a `FIXME:` at the location for any unresolved `Critical`, and reports the residual to the leader.
