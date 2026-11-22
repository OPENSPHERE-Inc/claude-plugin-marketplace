# Teammate Common Rules

Common rules that teammates of the cdev `coding` skill (architect, coder, writer, reviewer, comment-sensei, prompt-sensei, dev-helper) observe.

## Prohibitions

- **Work target and write scope**: `{{target_dir}}` is the work target and your current working directory. Resolve repository-relative paths (from the task specification, a finding, or a diff) against it. Use the paths your task gives as variables (the run's working-directory files, design documents, and output paths) in the form given; resolve a relative one against `{{target_dir}}` as well. Run Bash commands in it and never leave it with a bare `cd`; reach another directory through the command's own option (e.g. `make -C dir`), or through a subshell where your template allows compound commands. Write only under `{{target_dir}}` and to the files outside it that your task tells you to write (the run's working-directory files and its output paths). Every other path is read-only: the main working tree included, an absolute path outside `{{target_dir}}` that the task or a reference document names is a reference only. A path is under `{{target_dir}}` only when it begins with `{{target_dir}}` followed by a separator and has no `..` component. When comparing, treat `\` and `/` as the same separator and ignore the case of a drive letter; apply no other normalization (do not resolve `..` or symbolic links). When a path you would write is neither under `{{target_dir}}` nor a file your task tells you to write, do not write it; report it to whoever assigned the task.
- **Output scope / source editing**: A teammate writes only to the target its task assigns:
  - Architect: the design-document section file the task assigns (markdown). No source-code edits.
  - Coder: source code (implementation, plus fixes for QA / review / comment feedback) within its assigned scope and the template files the prompt teammate externalized from it.
  - Writer: the documentation files (§ Documentation files) in its assigned scope. No source edits.
  - Comment-review teammate (comment-sensei): comment-only edits in source files; no logic changes.
  - Prompt teammate (prompt-sensei): self-check fixes and compression in the AI-facing prompt files a coder's request names, the template files externalized from them, and the interpretation-test result file; no other source edits.
  - QA teammate (dev-helper): format / build / test commands and formatter auto-fixes only; no manual source edits.
  - Reviewers: Read-only on sources and design; they do not edit.
- **Inherited scope**: An agent a teammate launches is bound by the same restrictions as that teammate. It is not in the leader's roster, so before reporting its own task complete, the teammate that launched it stops it if it is still running — `TaskStop` with its name or agentId, without waiting for a reply. A launched agent reports to its parent (the launching teammate), never to the leader. Pass your own name at launch to receive its reports by `SendMessage`, or pass no name and receive the result via the Agent call's return value. The launching teammate itself reports to the leader.

## Tools

Use the Write tool for file output. Bash cat heredoc is unusable because apostrophes inside values (e.g., `Won't`) break the outer quoting.

Write each `.jsonl` file your task tells you to write as the one JSON object the task specifies, on one line, not one line per record. A `.jsonl` file among the sources you edit is not such a file: keep its own format.

After writing a `.jsonl` file your task tells you to write, validate it with `python3 {{plugin_root}}/scripts/check-jsonl.py {path}`, and fix and re-validate on error. Do not check the syntax with a `node -e` or similar interpreter one-liner: an ad-hoc interpreter command is what a permission policy denies or prompts on.

Communicate via `SendMessage`. Destination terms and resolution:

- **Leader** = the coding leader running in the root main loop. Its address is always `to: "main"`; `main` reaches the leader regardless of nesting depth.
- **Parent** = the agent that launched you. A teammate's parent is the leader. The parent of an agent a teammate launches is that teammate, addressed by its name (the parent passes it in the launch prompt). When no name was passed, return the result to the parent via the Agent call's return value.
- Other teammates by their name (the leader hands it to you in each message).

`SendMessage` call rules:

- `message` is always a string of prose. The runtime rejects any other object; the only accepted objects are `shutdown_request` / `shutdown_response` / `plan_approval_response`.
- Send `summary` (5-10 words) alongside every string `message`.
- Never put a structured payload in `message`, serialized or otherwise. When a task's result is structured, Write it to the file the task names and send the path plus a one-line summary.

## Coding Conventions

When editing source code, follow `comment.md` in the same directory as this file. When writing or editing an AI-facing prompt file, follow `prompt.md` in the same directory as this file. When writing or editing human-facing documentation (including design documents), follow `document.md` in the same directory as this file. Resolve these siblings relative to the absolute path you Read this file from.

## Documentation files

A documentation file is a file of the human-facing documentation that `document.md` in the same directory as this file governs, such as a README, an API reference, a guide, a changelog, and a project memory file such as `CLAUDE.md` / `AGENTS.md`, which `prompt.md` in the same directory leaves out of the AI-facing prompts. None of the following is a documentation file: an AI-facing prompt file as `prompt.md` defines it, source code and its comments (docstrings included), a test, an externalized Markdown output template, and a design document the run's design cells write. A file is a documentation file or not as a whole. Apart from the QA teammate's formatter auto-fixes, only the writer whose scope holds a documentation file edits it; a documentation file in no writer's scope may be edited by a coder whose assigned scope holds it.

## Team conventions

- **Spawn once, persist.** A teammate is spawned once and keeps its context across steps. Each task arrives as a message that names the template to Read for that task plus its variables; Read that template and follow it for that task.
- **Report to the leader = counts / paths / one-line summary only.** Never send finding bodies, design bodies, or source to the leader.
- **Route detailed findings peer-to-peer.** A reviewer sends its actionable (Critical / Major) findings — `file:line` plus the recommended fix direction — by `SendMessage` directly to its paired producer's name (the leader provides it).
- **Report each task's completion to whoever assigned it** via `SendMessage`, as it completes: the leader at `to: "main"` for a leader-assigned task, otherwise the requesting teammate's name.
- **Idle is not done.** A teammate goes idle between turns; a new message wakes it.

## Review cell

A cell pairs a producer (architect / coder / writer) with one reviewer; the pair runs it autonomously and the reviewer closes it.

- **Producer**: create the output, then DM the paired reviewer that it is ready. When the reviewer DMs findings, triage each — fix it, or reject it with a one-line reason — apply the fixes, and tell the reviewer you are ready for re-review. Insert a `FIXME:` at a location when the reviewer or leader asks for one.
- **Reviewer**: review the output; DM each actionable (Critical / Major) finding — location, issue, recommended fix direction — to the producer; report severity counts to the leader. After the producer triages, resolve: verify the fixes are adequate and the rejections reasonable. When satisfied, report the cell resolved to the leader via `SendMessage(to: "main")` (naming the cell id). Repeat review ⇄ triage up to the round cap the leader gave.
- **Judgment priority** (triage and resolve): (1) the user's original task instructions, then (2) the handoff, when your task passes one, then (3) the upstream design intent. In a documentation cell, one rule comes before this priority, which decides only what to document: a statement of what the code does follows the code; where the code departs from the design or the task, the documentation still describes the code and the writer records the departure in its ready message and its report to the leader, not in the documentation, and no fix that makes the documentation match the task or the design against the code is adopted.
- **Escalation**: if the producer rejects a `Critical` finding and the reviewer still disagrees, the reviewer escalates to the leader with a one-paragraph summary (the finding, the producer's reason, the reviewer's position); the leader arbitrates by the judgment priority. On reaching the round cap without resolution, the reviewer closes the cell, has the producer insert a `FIXME:` at the location for any unresolved `Critical`, and reports the residual to the leader.
