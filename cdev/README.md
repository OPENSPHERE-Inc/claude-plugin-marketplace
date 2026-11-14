# cdev

*[日本語版 README](README_ja.md)*

A team-native multi-agent coding workflow for Claude Code. `/cdev:coding` stands up an
agent team and drives a task from design to verified, reviewed code. `/cdev:loop` runs
`/cdev:coding` and creview's `/creview:rounds` as one unattended pipeline from
implementation to review.

## Skills

| Command | Purpose |
|---------|---------|
| `/cdev:coding` | Implement a coding task end to end: form a standing team, then run design → design review → coding → QA → code review with feedback loops. AI-facing prompt files also get a self-check, compression, and an interpretation test. |
| `/cdev:loop` | Take a coding task through `/cdev:coding` and `/creview:rounds` without asking for decisions: send the work back to `/cdev:coding` when the review diverges, and decide in a post-mortem whether to finish or start over, each within a limit. See [Loop](#loop-cdevloop). |

Invoke either with a task description, e.g. `/cdev:coding add a rate limiter to the
upload endpoint` or `/cdev:loop --max-generations 2 add a rate limiter to the upload
endpoint`.

## Lifecycle role

`cdev` is the **implementation stage** of the marketplace lifecycle: it gets a working,
self-checked first cut built quickly. Its in-loop reviews are **quality gates**, not an
authoritative review — run `creview` afterward for the bias-controlled, auditable review
(`/creview:start` → `triage` → `respond` → `resolve`). Because the authoritative review
lives in `creview`, `cdev` optimizes for speed and coherence instead.

`/cdev:loop` joins the two stages into one pipeline: it runs `/creview:rounds` after
`/cdev:coding`, and feeds the review back into the implementation stage by sending the work
back to `/cdev:coding` on a divergence and by starting over after a post-mortem.

## How it works

In `/cdev:coding`, the leader (team lead) spawns each selected specialist once as a named,
persistent background teammate (`Agent` with `run_in_background`), pairs each producer with a
reviewer, and drives two cell steps, with a team re-formation between them, and a final QA
gate, reporting progress to the console:

1. **Design cells** — each architect writes a design for its area, then its **paired
   reviewer** reviews it; the architect **triages** each finding (fix, or reject with a
   reason) and the reviewer **resolves** and closes the cell. Both follow
   `rules/divergence.md`: the design must not carry a source that makes later reviews
   diverge (a fix producing the next finding without end) — an undecided specification or
   invariant, a problem class the approach cannot close, an unadjudicated conflict between
   requirements, a mismatch with the existing design, or an AI-facing prompt that specifies
   its procedure in more detail than its goal and contracts need — and the reviewer raises
   any it finds as Major or higher.
2. **Team re-formation** — once every design cell has closed, `dev-helper` reads the designs
   and the roster, and re-forms the coders so that each file the designs add or change lies in
   the scope of exactly one coder, paired with a reviewer matching the file's domain. As in
   team formation, prompt files go only to coders whose scope holds no other source. A test the
   design adds goes to the coder that holds the file it tests, unless that file is a prompt
   file or no coder holds it. A file under the scope of a coder that may not hold it moves out
   of that scope, and a file no existing coder can hold goes to a new coder. The leader starts
   the coders and reviewers the updated roster adds. If the updated roster is still unusable
   after one retry, coding starts with the original roster, and the final report says so.
3. **Code cells** — each coder implements its scope (test-first when the project has a test
   suite); `comment-sensei` fixes comment violations when comments are present, and
   `prompt-sensei` self-checks and compresses AI-facing prompt files (see
   [AI-facing prompts](#ai-facing-prompts)); the **paired reviewer** reviews, the coder triages,
   the reviewer resolves and closes the cell.
4. **QA gate** — the build / format / test workflow runs once, together with an interpretation
   test of the changed AI-facing prompt files when the task has any; on failure the responsible
   coder fixes it, the fix goes through a review cell, and QA re-runs (bounded loop).

A cell runs autonomously: the producer (architect / coder) and its paired reviewer loop
review ⇄ triage ⇄ resolve until the reviewer closes the cell. The leader sets up the cells,
enforces the step gates (all design cells close and the team is re-formed before coding; all
code cells close before QA), runs the QA gate, and arbitrates escalations. When a reviewer and
a producer deadlock on a `Critical` finding, the reviewer escalates to the leader; if the
leader cannot decide either, it asks the user and leaves a `FIXME:`. Judgment priority is the
user's original task first, then the design intent. The authoritative review is `creview`, so
unresolved items are left as `FIXME:`s rather than blocking.

Teammates persist across steps, so they keep their own context and revise incrementally.
Feedback flows **peer to peer**; the leader holds only the roster, pairings, each cell's
status, severity counts, paths, and the QA and interpretation-test results, never the bodies.

## Requirements

`/cdev:coding` uses background subagents (`Agent` with `run_in_background`) and `SendMessage`
between named teammates. The session has a single implicit team — no explicit team creation
or deletion, and no shared task list; the leader tracks each cell's status itself. When the
run ends, the leader stops the teammates with `TaskStop`. It runs only in a runtime where
these are available — a deliberate trade-off favoring efficiency over the broad portability
of a one-shot, stateless agent design. The interpretation test of AI-facing prompt files has a
teammate, `prompt-sensei`, launch sub-agents with the `Agent` tool; where a teammate cannot,
the test reports those files as untested.

Claude Code v2.1.217 or later caps the sub-agents running at once in a session
(`CLAUDE_CODE_MAX_CONCURRENT_SUBAGENTS`, default 20) and refuses a launch past it with
`Concurrent subagent limit reached`. Teammates at work and the sub-agents of the interpretation
test can count toward the cap. The leader spawns a refused teammate again the next time a
teammate's report or completion notice wakes it; when no teammate is left to wake it, the run
ends with the error. In that case, wait for other agents in the session to finish, or raise the
cap, and run again. The run commits nothing, unless `--commit-always` is on and the refusal
came during the QA gate, after every code cell had closed: the run then commits as that option
describes, and what follows about uncommitted changes and a kept worktree does not apply.
Without `--worktree`, changes made before the error stay uncommitted in the working tree, and
the files the run created stay untracked. The next run's clean-working-tree check counts
untracked files as well and ignores `.claude/tmp/`, `.claude/worktrees/`, the `--output`
destination, and the `--handoff` and `--result` files, so commit, stash, or discard the changes
outside those places first. Under `--worktree`, those changes stay in the worktree, which is
kept and its path reported.

`prompt-sensei` launches a refused test sub-agent again after one it launched returns; when
none of the test sub-agents it launches at once starts and none it launched is still running,
the files of the refused sub-agents are reported as untested.

The skill requires a session started at the repository root, with or without `--worktree`;
started from a subdirectory of the repository, it stops with an error.

The bundled `fetch-diff.sh` / `del-tmp.sh` scripts also require `python3` (3.9 or later) on
the `PATH`: their shared `.claude/tmp/` containment check is implemented in
`scripts/lib/scratch-guard.py`.

`.claude`, `.claude/tmp`, and `.claude/worktrees` in the project must not be symbolic links, even
ones pointing inside the project: the bundled scripts refuse them with an error. To share
configuration across working
trees, keep it in `~/.claude/` instead.

`/cdev:loop` has the requirements of both `/cdev:coding` and `/creview:rounds`; see
[Requirements and cost](#requirements-and-cost).

## Options

Options of `/cdev:coding`; for those of `/cdev:loop`, see [Loop](#loop-cdevloop).

- `--review-rounds N` (default 5, max 10) — max review ⇄ triage iterations per cell.
- `--qa-attempts N` (default 5, max 10) — max QA verify ⇄ fix attempts.
- `--commit` (default off) — commit the verified implementation in one commit.
- `--worktree[=branch]` (default off) — run the task in a separate git worktree on `branch`;
  enables `--commit` (see below).
- `--output {dir}` — directory for the design documents (default
  `.claude/tmp/cdev-coding-{timestamp}-design/`).
- `--handoff {path}` (default none) — a Markdown handoff that team formation, the design
  cells, and the design review read.
  - Judgment priority becomes the user's task, then the handoff, then the design intent.
  - When the handoff names turning points — branches given with their commits — to return
    to, an architect can choose to restore files of its area to a turning point's content.
    Only the file contents are restored: the branch and HEAD stay where they are, and the
    restored content counts as a change of this run.
  - The run does not commit when the branch or HEAD has moved since the start.
- `--team-tag {tag}` (default none) — appends `-{tag}` to every teammate name, e.g.
  `coder-backend-g1c2`, so that a second or later run in the same session does not reuse the
  names of an earlier run's teammates. The tag is 1 to 16 letters, digits, and hyphens,
  starting with a letter or a digit; keeping it unused in the session is up to the caller.
- `--commit-always` (default off; implies `--commit`) — commit once every code cell has
  closed, even when QA or the interpretation test has not passed. The result file and the
  final report say what did not pass.
- `--result {path}` (default none) — write a JSON result at the end: whether the run committed
  and the commit, the branch, the design document paths, the turning points restored from,
  the QA and interpretation-test results, the numbers of `FIXME:`s left and of escalations,
  whether team re-formation fell back to the original roster, the step and reason when the
  run stopped early, and the worktree kept, if any. It is written as well when the run ends
  before the commit step, such as on an invalid option or an unmet requirement.

The design documents (`design-{slug}.md`, one per architect) are kept after the run; every
other intermediate file is deleted. `--commit` never stages them, nor the `--handoff` and
`--result` files. The clean-working-tree check at start ignores `.claude/tmp/`,
`.claude/worktrees/`, the `--output` destination, and the `--handoff` and `--result` files,
so design documents left by earlier runs and the worktrees of `--worktree` runs do not block a
new run.

With `--worktree`, the team works in a separate git worktree under `.claude/worktrees/`, so the
main working tree's sources stay untouched and it does not need to be clean. The worktree
checks out `branch` — an existing local branch as is, or a new one created from the current
HEAD; without `=branch`, a new branch `cdev-coding-{timestamp}` is created. The branch checked
out in the main working tree cannot be used, because git does not check out one branch in two
worktrees. The worktree starts from committed state — the current HEAD for a new branch, the
tip of an existing one — so uncommitted changes in the main working tree are not part of the
task. Every teammate receives the worktree as its work target
(`target_dir`) and writes only under it, to the run's working directory, and to the output paths
its task names; paths in the task are passed as given, repository-relative paths resolve against
the worktree, and an absolute path into the main working tree is a read-only reference. Gitignored dependencies, virtual environments, build directories, and `.env` are
absent from the worktree as well, and so are the contents of submodules, which
`git worktree add` does not initialize; the build and tests must therefore pass in a fresh
checkout. Dependency installation and similar setup can go in the configure command of
`build-format.md`, but configure runs only at the start of the build stage — after the format
command, and not at all when the build is skipped or no Build is declared — so the format
command and tests that run without a build cannot rely on it. A build or test failure caused
by such a missing prerequisite is not fixed in the source: the QA gate ends without a QA-fix
cell and reports the failure as environmental. The working directory and the
default design-document destination are in the main working tree's `.claude/tmp/`, a relative
`--output`, `--handoff`, or `--result` resolves against the main working tree's root, and the
destination project's `.claude/agents/` and `.claude/rules/` are read from the main working
tree. At the end the
worktree is removed and the branch is kept; a worktree left with uncommitted changes — for
example after an unfixed QA failure — is kept and its path is reported. Git also refuses to
remove a worktree in which submodules were initialized (for example by the configure command),
so such a worktree is kept and reported as well; check its contents and remove it with
`git worktree remove --force <path>`, since a rerun on the same `--worktree=branch` fails while
it remains.

## AI-facing prompts

A file an AI agent reads as its instructions — an agent definition, a skill (`SKILL.md`), a
slash command, a rule, or a prompt template a skill has an agent read — is an AI-facing prompt
(`rules/prompt.md`); project memory files such as `CLAUDE.md` and Markdown output templates are
not. The skill changes only prompt files in the repository: those under `~/.claude/` or
elsewhere outside it are out of reach, since a teammate writes only inside its work target.
Like any other run, a run that edits prompt files needs a clean working tree unless it uses
`--worktree`. A task that creates or edits a prompt file goes through the same design cells,
code cells, and QA gate as any other task, with these additions:

- Team formation gives the prompt files to coders whose scope holds no other source, and pairs
  each of them with a reviewer for prompts, picked like any other reviewer as the best match in
  the agent pool, which includes the bundled `prompt-sensei`.
- Coders follow `rules/prompt.md` when they write a prompt. In the code cell, before the
  review, the `prompt-sensei` teammate self-checks what the coder created or changed in its
  prompt files against it, fixes the violations in up to two passes, and compresses that part
  without changing what it asks of the agent; the rest of an existing file is left as it is
  unless the design covers the whole file. The coder hands any violation left over to the
  reviewer with the change.
- The design cells and the code cells keep prompt files from over-specification
  (`rules/divergence.md`):
  - A procedure specified in more detail than the prompt's goal and contracts need draws new
    findings at every review, and each fix that adds detail gives the next review more to
    find.
  - Whether a prompt is over-specified, and what its goal and contracts are, is judged by
    `rules/prompt.md`.
  - Constraints and premises the AI needs for judgment, such as a write scope or an instruction
    to treat untrusted input as data, are not procedure and stay in the prompt.
  - A detail finding is a finding whose fix only adds to or refines a method that an AI knowing
    the goal and the contracts would already carry out correctly.
  - Reviewers raise over-specification in what the design or the run creates or changes in a
    prompt file, or in the whole file when the design covers all of it. They recommend a
    rewrite that states the goal and the contracts and leaves the method to the AI, raise no
    detail finding, and judge a missing edge case by the same test.
  - Coders reject a detail finding citing the rule, unless the prompt does not yet state the
    goal or contract the method rests on; then they state it instead.
  - Coders settle a gap or ambiguity in a prompt's procedure, including an item the QA gate's
    interpretation test finds unclear, by stating the goal or contract it concerns rather than
    by adding steps.
  - Architects write down in the design the goal and the contracts of the part of each prompt
    file the design creates or edits, or of the whole file when the task covers all of it. They
    settle a gap or ambiguity in its method the same way, leaving to the AI what concerns
    neither.
  - A procedure the user's task explicitly asks for, and in the code cells also one the design
    specifies, is not over-specification: the prompt must satisfy it, and a missing one is
    added.
- In the QA gate, `prompt-sensei` also runs an interpretation test on each prompt file changed
  in the run:
  - It writes a checklist of questions about what the run created or changed in the file, such
    as how an agent should decide a value the input omits.
  - A newly launched sub-agent answers the checklist from the prompt and the files the prompt
    tells its reader to read; it has no context of the run and can only read files.
  - A file with an item the sub-agent cannot answer fails the test and goes through a QA-fix
    cell, a coder's fix reviewed by a paired reviewer, before QA runs again.
  - A retry tests again the files that failed, were left untested, or were covered by a QA-fix
    cell, and any prompt file not in the previous result; it reuses each file's checklist and
    adds items only for what changed since the previous attempt.
  - A file the test could not be run on, for example because the sub-agent could not be
    launched, is reported as untested; it goes through no QA-fix cell, and the run does not pass
    the test.
  - The test runs in the same QA attempts as the build and tests, bounded by `--qa-attempts`.

## Loop (/cdev:loop)

`/cdev:loop` takes the same coding task as `/cdev:coding` and carries it through implementation
and review without asking for decisions. It runs `/cdev:coding` and `/creview:rounds` inline in
the session, acting as their leader, and does no design, coding, or review itself. When the
review diverges, it sends the work back to `/cdev:coding`, up to a limit; otherwise a
post-mortem decides whether to finish or to start over from the starting commit. Both are
bounded, so the run always ends. It never pushes or opens a pull request.

### Flow

- A **cycle** is one `/cdev:coding` run followed by one `/creview:rounds` run. A
  **generation** is a series of cycles on one work branch, starting from the **starting
  commit**: the main working tree's `HEAD` when the loop starts.
- In each cycle, `/cdev:coding` runs in a worktree on the generation's work branch and commits
  its result even when QA or the interpretation test did not pass. `/creview:rounds` then runs
  on the same branch with `--incremental`, and stops instead of pausing when it detects a
  divergence (`--on-divergence stop`).
- Round 1 of every cycle's review covers the whole generation, as the diff from the starting
  commit; later rounds review only the previous round's fixes. A send-back can touch fixes
  across earlier rounds, so the review after it looks at the whole generation again.
- **Send-back**: when the review stops on a divergence, the loop writes a handoff that has
  `/cdev:coding` follow the sources and fix proposals of the divergence investigation report,
  and starts the next cycle on the same branch.
  - From the second generation on, the handoff also carries over the policy of the
    post-mortem's handoff that started the generation, and what that handoff says to avoid.
  - By default, the new work goes on top of the branch's tip, keeping the earlier review
    fixes, most of which have nothing to do with the divergence.
  - The design may instead restore files to the content of a turning point of the same
    generation, which the design review checks. The restored content is committed on top of
    the branch; history is never rewritten.
  - `--max-sendbacks` limits the send-backs per generation. A divergence past the limit goes
    to the post-mortem as unresolved.
- **Post-mortem**: once a generation's review has converged, reached its maximum rounds, or
  diverged past the send-back limit, a post-mortem sub-agent reads the generation's design
  documents, review documents, final reports, and divergence reports, and returns `finish` or
  `redo`.
  - By default, it returns `redo` only when all of these hold:
    - A problem that affects the result's quality remains: an unresolved Critical or Major
      finding, a `FIXME:` on one, a failed QA, or an unresolved divergence.
    - The review documents show that its root cause lies in a design choice.
    - A different approach that avoids that cause can be given concretely.
  - With `--pursuit`, it also returns `redo`, even with no such problem left, when all of these
    hold:
    - A different approach can be given concretely.
    - That approach is expected to clearly beat the generation in an observable way, such as
      making a class of repeated findings impossible, removing a constraint or residual risk
      the design accepted, having clearly fewer components, interfaces, or special cases, or
      better meeting a goal the task sets.
    - The design documents, review documents, and code back that expectation.
  - An improvement that ordinary fixes could reach, or a matter of taste, is never a reason
    for `redo`.
  - `redo` starts a **grand reset**: a new generation from the starting commit on a new work
    branch, with a handoff the post-mortem writes, up to `--max-generations`. With no
    generation left, the verdict is `finish`.
- **Adopted generation**: on `finish`, the post-mortem picks the generation to deliver: the
  last one, unless an earlier one surpasses it, being no worse in each of unresolved Critical
  and Major findings, `FIXME:`s, QA, and unresolved divergence, and better in at least one.
  When several earlier ones do, it picks the latest of those that no other of them surpasses.
  The loop creates the output branch at the tip of that generation's work branch.

### Options

- `--branch {name}` (default `cdev-loop-{timestamp}`) — the output branch's name, also the
  prefix of the work branches and turning points.
- `--max-sendbacks N` (default 2, 0 to 5) — max send-backs per generation.
- `--max-generations N` (default 3, 1 to 5) — max generations; 1 means no grand reset.
- `--pursuit` (default off) — widen the post-mortem's `redo` condition as described above.
- `--output {dir}` (default `.claude/tmp/cdev-loop-{timestamp}/`) — the run directory.
- Passed through to `/cdev:coding`: `--review-rounds N` and `--qa-attempts N`. Passed through
  to `/creview:rounds`: `--max-rounds N`, `--adversarial`, and `--adr`.
- Rejected with an error: `--worktree`, `--commit`, and `--incremental`, which are always on;
  `--confirm` and `--confirm-round`, which wait for you; `--base`, which the loop sets; and the
  options the loop passes to the inner skills itself (`--on-divergence`, `--result`,
  `--handoff`, `--team-tag`, and `--commit-always`).

### Branches and turning points

In the names below, `{branch}` is the `--branch` value, `g` the generation, and `c` the cycle.

| Kind | Name | Created |
|------|------|---------|
| Output branch | `{branch}` | At the end, at the tip of the adopted generation's work branch |
| Work branch | `{branch}-g{g}` | At the start of generation g, at the starting commit |
| Turning point A | `{branch}-tp/g{g}c{c}-coding-start` | Right before cycle c's `/cdev:coding` |
| Turning point B | `{branch}-tp/g{g}c{c}-coding-done` | Right after cycle c's `/cdev:coding` |

- A turning point is a branch that marks the code at that moment. Turning point A of a
  generation's first cycle is the starting commit, and that of a later cycle is the work
  branch's tip after the previous review. Turning point B is the tip after `/cdev:coding`'s
  commit, the same commit as A when it committed nothing. The work branch's tip holds the
  state after the last review.
- The loop creates branches without touching any working tree, never moves or deletes a
  turning point, and never rewrites a work branch's history. A grand reset leaves the earlier
  generations' work branches and turning points in place. Cleaning them up is yours; to delete
  every turning point of a run:

  ```
  git for-each-ref --format='%(refname:short)' 'refs/heads/{branch}-tp/' | xargs git branch -D
  ```

- To continue by hand from a turning point, branch from it, e.g.
  `git switch -c retry {branch}-tp/g1c1-coding-done`.
- The run stops at the start when a branch named `{branch}` or `{branch}-tp`, or a branch
  under `{branch}/` or `{branch}-tp/`, or one matching `{branch}-g*`, already exists. Turning
  points live under `{branch}-tp/` rather than `{branch}/` because git cannot hold a branch
  `{branch}` alongside branches under `{branch}/`.

### Run directory

```
{output}/                    (default .claude/tmp/cdev-loop-{timestamp}/)
├── state.json               progress state
├── g1c1/
│   ├── design/              /cdev:coding design documents
│   ├── coding-result.json   /cdev:coding result
│   ├── review/              /creview:rounds review documents and final report
│   └── rounds-result.json   /creview:rounds result
├── g1c2/
│   ├── handoff.md           send-back handoff
│   └── ...
├── g1/
│   ├── postmortem.md        post-mortem analysis
│   └── postmortem.json      post-mortem verdict
├── g2c1/
│   ├── handoff.md           grand-reset handoff
│   └── ...
└── loop-summary.md          run summary
```

- The directory is in the main working tree; a relative `--output` resolves against the
  repository root. It must be absent or empty at the start, and it is kept after the run.
- `state.json` records the position, each cycle's results, the turning points, and the
  send-backs. The loop updates it at every step and reads it back to recover its position after
  the session's context is compacted. It does not resume a run in another session.
- `loop-summary.md`, written at the end, lists each cycle's end reasons, the send-backs, the
  post-mortem verdicts and the adopted generation, the turning points and how to delete them,
  the warnings, and any worktree left behind. The warnings include, for example, those of QA,
  the build, and the interpretation test, and a failure to create the output branch.

### When it stops

The loop stops and reports to you only when:

- A starting check fails, such as a session not started at the repository root, an unmet
  requirement, a branch name already taken, or a run directory that is not empty. The run then
  ends without a summary.
- `/cdev:coding` ends abnormally: it writes no result, stops early, or keeps its worktree.
- `/creview:rounds` ends on an error.
- `/creview:rounds` keeps its worktree, for example one left with uncommitted changes or
  initialized submodules, so the next phase cannot check out the work branch.
- A work branch or turning point cannot be created, the session cannot return to the
  repository root after an inner skill, or `state.json` cannot be written or made valid.

Otherwise it decides and goes on without asking. An error stop creates no output branch; the
turning points and work branches made so far remain, and the report names the step that
stopped, the error, the last work branch, and `loop-summary.md`. When creating the output
branch at the end fails, the run still ends normally, with a warning: the adopted generation's
work branch `{branch}-g{g}` holds the same commit, and `loop-summary.md` records the failure.

### Requirements and cost

- The loop needs what `/cdev:coding` and `/creview:rounds` need: background subagents and
  `SendMessage`, nested sub-agent spawning of depth 3 or more
  (`CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH`), a repository you trust, and a session started at
  the repository root. It also needs the creview plugin, version 0.22.0 or later, which Claude
  Code installs with cdev as a dependency.
- The project's configure, build, and test steps must leave in the worktree neither initialized
  submodules nor untracked files that `.gitignore` does not cover. Git refuses to remove such a
  worktree, the inner skill keeps it, and the loop stops after that phase, typically the first
  coding phase.
- A run makes at most `(1 + max_sendbacks) × max_generations` cycles, 9 with the defaults.
  Each cycle runs `/cdev:coding` from team formation to QA and up to `--max-rounds` review
  rounds, and every send-back has the next review's Round 1 cover the whole generation again.
  `--pursuit` tends to run up to the generation limit. For the caps on sub-agents launched in a
  session and running at once, see the [creview README](../creview/README.md).
- A run makes two turning points per cycle, up to 18 with the defaults.
- The main working tree's sources are never changed. Its uncommitted changes are not part of
  the starting commit and are left out of the run; the loop says so at the start.

## Architect / coder / reviewer agents

Apart from the comment and prompt specialists listed under Bundled agents, this plugin does not
bundle specialist reviewers. The `team-analysis`
task enumerates agents recursively (`**/*.md`, including subdirectories) from the
**destination project** (`.claude/agents/`) → **user** (`~/.claude/agents/`) → **plugin
bundle**, reads each agent's frontmatter `name` / `description`, and assigns the best-matching
specialists to the **reviewer** role — each reviewer covers a producer's domain, and an
out-of-domain specialty is never bundled onto one reviewer. **Architects and coders always run
as `general-purpose`**: some specialist agents emit malformed tool calls and stall, and a
producer works to its assigned scope and the project conventions while the specialist reviewers
enforce domain correctness. When no specialist matches a domain, the reviewer falls back to
`general-purpose`. Team re-formation after the design cells picks the reviewers it adds from the
same agent pool by the same rules.

## Bundled agents and support files

- `agents/dev-helper.md` — mechanical teammate: team formation (scoping + agent selection),
  team re-formation after the design (assigning the files the design adds or changes to coders
  and selecting any coders / reviewers needed), and QA (running the project's format / build /
  test, identifying the fix specialist on failure).
- `agents/comment-sensei.md` — code-comment specialist teammate; reviews and fixes comments
  added or modified during coding, against `rules/comment.md`.
- `agents/prompt-sensei.md` — AI-facing prompt specialist teammate; self-checks, fixes, and
  compresses the prompt files a coder changed, against `rules/prompt.md`, and runs their
  interpretation test in the QA gate. Team formation can also pick it as the reviewer of prompt
  files.
- `agents/prompt-tester.md` — context-free interpretation tester that `prompt-sensei` launches
  in the QA gate; it has Read, Glob, and Grep only and is never a team-formation candidate.
- `rules/` — `teammate.md` (teammate common rules), `agents-detection.md`,
  `build-format-detection.md`, `comment.md`, `review.md`, `document.md`, `prompt.md` (prompt
  discipline), `divergence.md` (divergence patterns the design must not introduce, and how
  code cells keep prompt files from over-specification).
- `scripts/` — `fetch-diff.sh` (snapshots the pre-coding tree, then captures the QA diff since
  coding start), `del-tmp.sh` (deletes the run's working directory under `.claude/tmp/`; with
  `--dry`, it only runs the containment check, which the skill does before creating that
  directory), `check-jsonl.py` (teammates validate the `.jsonl` they wrote with it), and
  `lib/scratch-guard.py` (the shared `.claude/tmp/` containment check used by both; requires
  `python3` — see Requirements), and `worktree.sh` (creates and removes the `--worktree`
  worktree). The skill invokes them via
  `${CLAUDE_PLUGIN_ROOT}/scripts/...`; teammates receive the resolved path through the
  `{{plugin_root}}` variable.

## Build / test detection

QA resolves the project's format / build / test commands via
`rules/build-format-detection.md`: a `build-format.md` descriptor
(`.claude/rules/**/build-format.md`) takes priority, else `CLAUDE.md`, else `README.md`. When
none declares a workflow, QA performs a visual check only and returns a warning recommending a
`build-format.md` descriptor.

## Japanese master (repository-root `src/cdev/`)

The Japanese master lives at the repository root under `src/cdev/`, mirroring this plugin's
tree one-to-one (`src/cdev/skills/coding/SKILL.md` ↔ `cdev/skills/coding/SKILL.md`, etc.) with
the same skill name. The active English files here are produced by translating that master. To
update: edit the Japanese master under `src/cdev/`, then re-translate and re-apply the path
rewrites (`${CLAUDE_PLUGIN_ROOT}` / `{{plugin_root}}`) to the active files.
