# Teammate Common Rules

Common rules that teammates of the cdev `coding` skill (architect, coder, reviewer, comment-sensei, dev-helper) observe.

## Prohibitions

- **No nesting**: A teammate must not create a team or spawn further agents (the leader is the sole orchestrator).
- **Output scope / source editing**: A teammate writes only to the target its task assigns:
  - Architect: the design-document section file the task assigns (markdown). No source-code edits.
  - Coder: source code (implementation, plus fixes for QA / review / comment feedback) within its assigned scope.
  - Comment-review teammate (comment-sensei): comment-only edits in source files; no logic changes.
  - QA teammate (dev-helper): format / build / test commands and formatter auto-fixes only; no manual source edits.
  - Reviewers: Read-only on sources and design; they do not edit.

## Tools

Use the Write tool for file output. Bash cat heredoc is unusable because apostrophes inside values (e.g., `Won't`) break the outer quoting. Communicate with the leader and other teammates via `SendMessage`, and mark each assigned task done via `TaskUpdate`.

## Coding Conventions

When editing source code, follow `comment.md` in the same directory as this file. When writing or editing human-facing documentation (including design documents), follow `document.md` in the same directory as this file. Resolve these siblings relative to the absolute path you Read this file from.

## Team conventions

- **Spawn once, persist.** A teammate is spawned once and keeps its context across phases. Each task arrives as a message that names the template to Read for that task plus its variables; Read that template and follow it for that task.
- **Report to the leader = counts / paths / one-line summary only.** Never send finding bodies, design bodies, or source to the leader.
- **Route detailed findings peer-to-peer.** A reviewer sends its actionable (Critical / Major) findings — `file:line` plus the recommended fix direction — by `SendMessage` directly to the owning `architect-{slug}` / `coder-{slug}`, identified from the task's `scope_map`.
- **Mark tasks done with `TaskUpdate`** as each task completes.
- **Idle is not done.** A teammate goes idle between turns; a new message wakes it.
- **Shutdown.** On a `shutdown_request` message, reply with a `shutdown_response`.
