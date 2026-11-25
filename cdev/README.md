# cdev

*[日本語版 README](README_ja.md)*

A team-native multi-agent coding workflow for Claude Code. `/cdev:coding` stands up an
agent team and drives a task from design to verified, reviewed code. `/cdev:loop` runs
`/cdev:coding` and creview's `/creview:rounds` as one unattended pipeline from
implementation to review.

## Skills

| Command | Purpose |
|---------|---------|
| `/cdev:coding` | Implement a coding task end to end: form a standing team, then run design cells → code cells → documentation cells → a QA gate, each cell a producer paired with a reviewer, with feedback loops. AI-facing prompt files also get a self-check, compression, and an interpretation test. |
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
reviewer, and drives the design cells, a team re-formation, the code cells, the documentation
cells, a final QA gate, and the commit, reporting progress to the console:

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
   and the roster, and re-forms the coders and writers so that each file the designs add or
   change lies in the scope of exactly one of them, paired with a reviewer matching the file's
   domain.
   - Documentation files go only to writers, whose scope holds no other file (see
     [Documentation](#documentation)).
   - As in team formation, prompt files go only to coders whose scope holds no other source.
   - A test the design adds goes to the coder that holds the file it tests, unless that file is
     a prompt file or a documentation file, or no coder holds it.
   - A file under the scope of a coder or writer that may not hold it moves out of that scope,
     and a file no existing coder or writer can hold goes to a new one.
   - The leader starts the coders, writers, and reviewers the updated roster adds.
   - If the updated roster is still unusable after one retry, coding starts with the original
     roster, and the final report says so.
3. **Code cells** — each coder implements its scope (test-first when the project has a test
   suite).
   - `comment-sensei` fixes comment violations when comments are present, and `prompt-sensei`
     self-checks and compresses AI-facing prompt files (see
     [AI-facing prompts](#ai-facing-prompts)).
   - The **paired reviewer** reviews, the coder triages, the reviewer resolves and closes the
     cell.
   - When the designs list no file other than documentation files, no code cell runs.
4. **Documentation cells** — when the designs list documentation files, once every code cell
   has closed, each writer writes the documentation files of its scope from the designs and the
   code as it now stands, this run's changes included; the **paired reviewer** reviews them,
   checking that they agree with the code, the writer triages, the reviewer resolves and closes
   the cell.
5. **QA gate** — the build / format / test workflow runs once, together with an interpretation
   test of the changed AI-facing prompt files when the task has any.
   - On failure the responsible coder fixes it, the fix goes through a review cell, and QA
     re-runs (bounded loop).
   - A failure in a documentation file of a writer's scope goes to that writer instead, who
     fixes it in a documentation cell before QA re-runs.
   - When the designs list documentation files, every writer brings its documentation in line
     with the code after the coders' fixes have changed it, in a documentation cell before QA
     re-runs.
6. **Commit** — under `--commit`, `dev-helper` writes a plan that splits the run's changes
   into commits, one per logical change, and `scripts/commit-plan.py` checks the plan and makes
   the commits. When no plan can be accepted, the run commits the changes in one commit
   instead.

A cell runs autonomously: the producer (architect / coder / writer) and its paired reviewer
loop review ⇄ triage ⇄ resolve until the reviewer closes the cell. The leader sets up the
cells, enforces the step gates (all design cells close and the team is re-formed before coding;
all code cells close before the documentation cells; all code and documentation cells close
before QA), runs the QA gate, and arbitrates escalations. When a reviewer and a producer
deadlock on a `Critical` finding, the reviewer escalates to the leader; if the leader cannot
decide either, it asks the user and leaves a `FIXME:`. Judgment priority is the user's original
task first, then the handoff when `--handoff` is given, then the design intent; in a
documentation cell, a statement of what the code does matches the code, which takes precedence
over all three (see [Documentation](#documentation)). The authoritative review is `creview`, so
unresolved items are left as `FIXME:`s rather than blocking.

Teammates persist across steps, so they keep their own context and revise incrementally.
Feedback flows **peer to peer**; the leader holds only the roster, pairings, each cell's
status, severity counts, paths, the QA and interpretation-test results, and the departures of
the code from the design or task that writers report, never the bodies.

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
came during the QA gate, after every code and documentation cell had closed: the run then
commits as that option describes, and what follows about uncommitted changes and a kept
worktree does not apply.
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
`scripts/lib/scratch-guard.py`. `scripts/commit-plan.py`, which the commit step and
`/cdev:loop --cleanup` run, requires it as well. The commit step splits its commits only with
Git 2.25 or later; with an older Git, it commits in one commit and reports why.

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
- `--strict-docs` (default off) — have a cell's reviewer raise new findings on documentation
  files in every round, not only in its first review of the cell (see
  [Documentation](#documentation)). Severity is the same with or without it.
- `--commit` (default off) — commit the verified implementation, split into commits by logical
  change, with messages that follow the repository's commit history and conventions.
  - Each changed file goes into exactly one commit: the change of one file is never split
    across commits.
  - When no plan can be accepted, or committing fails partway, the run commits the rest in one
    commit and reports why.
  - The commits before the last are not built or tested; QA verified only the final state.
- `--worktree[=branch]` (default off) — run the task in a separate git worktree on `branch`;
  enables `--commit` (see below).
- `--output {dir}` — directory for the design documents (default
  `.claude/tmp/cdev-coding-{timestamp}-design/`).
- `--handoff {path}` (default none) — a Markdown handoff that team formation, the design
  cells, and the design review read.
  - Judgment priority becomes the user's task, then the handoff, then the design intent.
  - When the handoff names turning points — branches given with their commits — to return
    to, an architect can choose to restore files of its area to a turning point's content.
    - Only a run with `--worktree` restores, so that a restore cannot overwrite ignored files
      of the main working tree, such as `.env`. Without it, the design builds on the current
      code even when the handoff names turning points.
    - Only the file contents are restored: the branch and HEAD stay where they are, and the
      restored content counts as a change of this run.
    - A restore that would do either of the following is refused, and the path it would
      restore is left as it is: overwrite or delete an untracked file or a tracked file with
      local changes, or change a path outside the path it restores. The run goes on, and the
      final report and the result file list each refused path with its reason.
    - The restore list does not name documentation files. A design that returns one to a
      turning point's content lists it as a documentation change instead. Its writer takes that
      content with the same restore, refused on the same conditions, then brings the statements
      about the code in line with the code (see [Documentation](#documentation)).
  - The run does not commit when the branch or HEAD has moved since the start.
- `--team-tag {tag}` (default none) — appends `-{tag}` to every teammate name, e.g.
  `coder-backend-g1c2`, so that a second or later run in the same session does not reuse the
  names of an earlier run's teammates. The tag is 1 to 16 letters, digits, and hyphens,
  starting with a letter or a digit; keeping it unused in the session is up to the caller.
- `--commit-always` (default off; implies `--commit`) — commit after every code and
  documentation cell has closed, even when QA or the interpretation test has not passed. The
  result file and the final report say what did not pass.
- `--result {path}` (default none) — write a JSON result at the end: whether the run committed,
  the last commit, the number of commits, any warning from the commit step (such as a fallback
  to one commit), the branch, the design document paths, the turning points the designs
  restore from, the refused restores with their reasons, the QA and interpretation-test
  results, the numbers of `FIXME:`s left and of escalations, whether team re-formation fell
  back to the original roster, whether the documentation the designs list got no documentation
  cell for want of a writer, the departures of the code from the design or task that writers
  report, the step and reason when the run stopped early, and the worktree kept, if any. It is
  written as well when the run ends before the commit step, such as on an invalid option or an
  unmet requirement. It is not written when `.claude` or `.claude/tmp` is a symbolic link.
  - When the run writes no file, whether for that reason, on an interruption, or on a failed
    write, a file already at the path stays and can be mistaken for this run's result. Pass a
    path where no file exists, or delete the file before the run, and treat a missing file as
    an error.

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
not. Project memory files are documentation instead (see [Documentation](#documentation)).
The skill changes only prompt files in the repository: those under `~/.claude/` or
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

## Documentation

Documentation is the human-facing documentation that `rules/document.md` governs:

- Files such as a README, an API reference, a guide, or a change log.
- Project memory files such as `CLAUDE.md` and `AGENTS.md`, which `rules/prompt.md` leaves out
  of AI-facing prompts.

The following are not documentation:

- AI-facing prompt files, which go through the code cells (see
  [AI-facing prompts](#ai-facing-prompts)).
- Source code and the comments in it, docstrings included.
- Tests.
- Markdown output templates externalized from a prompt file.
- The design documents the run's design cells write.

`rules/teammate.md` § Documentation files holds this definition. The architect classifies each
file its design lists, as a whole file, and the design review checks the classification. A task
that changes documentation files runs as follows:

- **Writers** — team formation and the team re-formation treat documentation as a domain of its
  own.
  - Documentation files go only to writers (`writer-{slug}`), whose scope holds no other file.
  - Each writer is paired with a reviewer whose domain covers the documentation.
  - An architect's scope can hold code and the documentation that describes it; one design
    covers both.
- **When documentation cells run** — before the QA gate, only when a closed design lists
  documentation files among the files it changes, and only once every code cell has closed.
  - When the designs list no other file, no code cell runs, and the documentation cells run
    alone.
  - When the team re-formation falls back to the original roster and that roster has no writer,
    no documentation cell runs: no writer writes the documentation the designs list and no
    documentation review checks it, though a coder whose scope holds such a file may change it
    in its code cell. The console, the final report, and the result file's `docs_unwritten` say
    that no documentation cell ran, as do, under `/cdev:loop`, the warnings of `state.jsonl` and
    `loop-summary.md`.
- **Matching the code** — the writer writes from the designs and the code as it stands in the
  work target, this run's changes included.
  - A statement of what the code does matches the code, which takes precedence over the task,
    the handoff, and the design: they decide only what to document.
  - Where the code departs from the design or the task, the writer describes the code and
    reports the departure. The run does not fix the code.
  - The departures appear in the final report and the result file's `doc_departures`, and
    under `/cdev:loop` among the warnings of `state.jsonl` and `loop-summary.md`.
- **Review** — the paired reviewer checks the documentation of the writer's scope against the
  code, this run's changes included:
  - whether the behavior, interfaces, options, defaults, paths, requirements, and examples the
    changed files describe agree with the code;
  - whether this run's code changes made wrong a part of the writer's scope that the writer
    left unchanged;
  - whether every documentation change the design asks of the writer's scope is there;
  - whether the changed files contradict each other, and whether they follow the project's
    documentation conventions and `rules/document.md`;
  - whether each departure the writer reports holds, a `Major` when it does not.
- **Severity** — the reviewer sends its `Critical` and `Major` findings to the writer.
  - `Critical`: a statement readers rely on that contradicts the code.
  - `Major`: a documentation change the design asks for that is missing, a departure of the
    code from the design or the task that the writer has not reported, a statement that leads
    readers to use the code wrongly, or notation that breaks rendering.
  - `Minor` or below: wording or presentation that does not mislead.
  - No finding asks to make the documentation match the design or the task against the code.
    An unreported departure is settled by reporting it.
  - A statement the run neither changed nor made wrong is out of scope, `Info` at most.
- **Review rounds** — by default, the reviewer of a documentation cell raises findings only in its
  first review of the cell.
  - In each later round, it judges only whether the writer's fix or rejection settles each
    finding it raised, and sends again each unsettled one with what remains of it. The cell
    closes once they are all settled, or at the `--review-rounds` cap.
  - The reviewer of a code cell does the same for its findings on documentation files, which a
    coder holds when no writer does, and raises findings on other files in every round.
  - With `--strict-docs`, the reviewer raises new findings on documentation files in every
    round.
- **QA gate** — QA runs after the documentation cells, so the project's format, build, and test
  workflow covers the documentation changes when it handles documentation, such as with a
  Markdown linter or a documentation build; the review, not QA, checks that the documentation
  agrees with the code.
  - When the designs list documentation files, in an attempt that runs QA-fix cells, every
    writer runs a documentation cell again once they close, to bring its documentation in line
    with the code, before QA re-runs.
  - When QA reports a failing file in a writer's scope, that writer fixes it in a documentation
    cell, even when the designs list no documentation file.
  - A failing file in no writer's scope goes to a QA-fix cell, even when it is documentation.
  - No cell changes a file after the last QA.
- **Other rules**
  - Test-driven development does not apply to documentation.
  - A `FIXME:` left in a documentation cell is a comment in the file's format, such as
    `<!-- FIXME: ... -->` in Markdown.
  - A design's restore list never names a documentation file. In a run with `--worktree` whose
    handoff names a turning point, a design returns a documentation file to that turning
    point's content by listing it as a documentation change instead.
    - Before any other change, the writer takes that content with the same restore as the
      restore list's: the file gets its content at the turning point's commit, or is deleted
      when that commit lacks it.
    - That restore is refused on the same conditions as the restore list's, and the final report
      and the result file list a refused one with its reason.
      - When that restore is refused, the documentation reviewer does not report the turning
        point's content as a missing documentation change.
    - The writer then brings the statements about the code in line with the code.

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
  its result, split by logical change, even when QA or the interpretation test did not pass.
  `/creview:rounds` then runs on the same branch with `--incremental`, and stops instead of
  pausing when it detects a divergence (`--on-divergence stop`).
  - Unless `--strict-docs` is given, a divergence whose findings are all on documentation files
    does not stop it: the review applies the investigation report's fix proposal for it in the
    same round. A round with only such divergences goes on, and one that also has others stops
    after those fixes.
  - Unless `--strict-docs` is given, a review round whose fixes changed only documentation files
    ends the review.
  - See the [creview README](../creview/README.md).
- Round 1 of a cycle's review covers the diff from the cycle's base; later rounds review only
  the previous round's fixes.
  - In a generation's first cycle, the base is the starting commit.
  - After a send-back, when the previous cycle's review stopped in Round N, the base is the
    commit at the start of that review's Round N-1.
    - Round 1 then reviews the fixes of Round N-1 and the send-back's changes.
    - When the loop cannot get that commit, the review starts from the starting commit, with a
      warning.
  - Lines that a send-back returns to their content at the next review's base do not appear in
    that review.
- **Send-back**: when the review stops on a divergence, the loop writes a handoff that has
  `/cdev:coding` follow the sources and fix proposals of the divergence investigation report,
  and starts the next cycle on the same branch.
  - Unless `--strict-docs` is given, the handoff leaves out the divergences the report marks as
    documentation divergences: the review applied their fix proposals in the round it stopped
    in.
  - From the second generation on, the handoff also carries over the policy of the
    post-mortem's handoff that started the generation, and what that handoff says to avoid.
    These prevail over the investigation report's fix proposals: a source that cannot be
    removed without departing from them stays, and after at most `--max-sendbacks`
    send-backs, it goes to the generation's post-mortem.
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
  - It counts a generation's unresolved Critical and Major findings from the final reports of
    all its cycles.
    - From the report of a cycle before the last, it leaves out the findings left unfixed in
      the round where that cycle's review stopped, which count only when a later cycle's report
      lists them.
    - It counts the other findings the same report lists as unresolved or as fixed only when
      they still hold at the tip of the generation's work branch, since a later send-back can
      undo a fix without any review's diff showing it.
    - A fix by a `FIXME:` counts as a `FIXME:`, not as a fixed finding.
  - It lists in `postmortem.md` the findings it counts for the generation it examines.
    - It marks as reintroduced those that hold again at the tip of the generation's work branch
      after a fix by any of the generation's cycles removed their problem, and gives their
      number in its summary line, which `loop-summary.md` shows.
  - `skills/loop/templates/postmortem.md` holds the full rules for which findings the
    post-mortem counts and marks as reintroduced.
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
  On `finish`, `postmortem.md` shows these values for every generation.
  The loop creates the output branch at the tip of the adopted generation's work branch.
  - With `--cleanup`, the loop instead restacks the generation's changes from the starting
    commit into commits by logical change, and creates the output branch at the last of them.
    The work branch keeps the original history.

### Options

- `--branch {name}` (default `cdev-loop-{timestamp}`) — the output branch's name, also the
  prefix of the work branches and turning points.
- `--max-sendbacks N` (default 2, 0 to 5) — max send-backs per generation.
- `--max-generations N` (default 3, 1 to 5) — max generations; 1 means no grand reset.
- `--pursuit` (default off) — widen the post-mortem's `redo` condition as described above.
- `--cleanup` (default off) — on a normal end, create the output branch at the tip of a restack
  of the adopted generation's changes, as described above.
  - A planner sub-agent splits the changes into commits by the same rules as the commit step of
    `/cdev:coding`, and `scripts/commit-plan.py` checks the plan and makes the commits without
    touching any ref, index, or working tree.
  - The restack's last commit has the same tree as the work branch's tip, so the results of QA
    and the review still hold for it. The commits before it are not built or tested.
  - The commits are made with `git commit-tree`, so no hook runs on them. They are signed when
    `commit.gpgSign` is true; where signing needs interaction, the restack fails and falls back
    as described under [When it stops](#when-it-stops).
  - Their author and committer are the current git identity, at the current time.
  - When the starting commit and the generation's tip have the same tree, nothing is
    restacked.
- `--output {dir}` (default `.claude/tmp/cdev-loop-{timestamp}/`) — the run directory.
- Passed through to `/cdev:coding`: `--review-rounds N` and `--qa-attempts N`. Passed through
  to `/creview:rounds`: `--max-rounds N`, `--adversarial`, and `--adr`. Passed through to both:
  `--strict-docs`.
- Rejected with an error: `--worktree`, `--commit`, and `--incremental`, which are always on;
  `--confirm` and `--confirm-round`, which wait for you; `--base`, which the loop sets; and the
  options the loop passes to the inner skills itself (`--on-divergence`, `--result`,
  `--handoff`, `--team-tag`, and `--commit-always`).

### Branches and turning points

In the names below, `{branch}` is the `--branch` value, `g` the generation, and `c` the cycle.

| Kind | Name | Created |
|------|------|---------|
| Output branch | `{branch}` | At the end, at the tip of the adopted generation's work branch; with `--cleanup`, at the tip of the restacked commits |
| Work branch | `{branch}-g{g}` | At the start of generation g, at the starting commit |
| Turning point A | `{branch}-tp/g{g}c{c}-coding-start` | Right before cycle c's `/cdev:coding` |
| Turning point B | `{branch}-tp/g{g}c{c}-coding-done` | Right after cycle c's `/cdev:coding` |
| Turning point R | `{branch}-tp/g{g}c{c}-review-base` | At the send-back that starts cycle c, on the commit at the start of Round N-1 when the previous cycle's review stopped in Round N |

- A turning point is a branch that marks the code at a commit in the work branch's history.
  - Turning point A of a generation's first cycle is the starting commit, and that of a later
    cycle is the work branch's tip after the previous review.
  - Turning point B is the tip after `/cdev:coding`'s commits, the same commit as A when it
    committed nothing.
  - Turning point R of cycle c is the base of cycle c's review, and exists only when the loop
    can get the commit at the start of Round N-1.
  - The work branch's tip holds the state after the last review.
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
├── state.jsonl              progress state
├── g1c1/
│   ├── design/              /cdev:coding design documents
│   ├── coding-result.jsonl  /cdev:coding result
│   ├── review/              /creview:rounds review documents and final report
│   └── rounds-result.jsonl  /creview:rounds result
├── g1c2/
│   ├── handoff.md           send-back handoff
│   └── ...
├── g1/
│   ├── postmortem.md        post-mortem analysis
│   └── postmortem.jsonl     post-mortem verdict
├── g2c1/
│   ├── handoff.md           grand-reset handoff
│   └── ...
├── cleanup/
│   └── plan.jsonl           --cleanup restack plan
└── loop-summary.md          run summary
```

- The directory is in the main working tree; a relative `--output` resolves against the
  repository root. It must be absent or empty at the start, and it is kept after the run.
- `state.jsonl` records the position, each cycle's results, the turning points, the
  send-backs, and the result of `--cleanup`. The loop updates it at every step and reads it
  back to recover its position after the session's context is compacted. It does not resume a
  run in another session.
- `loop-summary.md`, written at the end, lists each cycle's end reasons, the send-backs, the
  post-mortem verdicts and the adopted generation, the turning points and how to delete them,
  the warnings, and any worktree left behind. The warnings include, for example, those of QA,
  the build, and the interpretation test, the departures of the code from the design or task
  that `/cdev:coding`'s writers report, and a failure to create the output branch.
  - With `--cleanup`, it also lists the restack's commits and their subjects, or why nothing
    was restacked, and states that the original history stays on the work branch and that the
    commits before the last were not built or tested.

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
  repository root after an inner skill, or `state.jsonl` cannot be written or made valid.

Otherwise it decides and goes on without asking. An error stop creates no output branch; the
turning points and work branches made so far remain, and the report names the step that
stopped, the error, the last work branch, and `loop-summary.md`.

Two failures at the end do not stop the run; it still ends normally, with a warning that
`loop-summary.md` records:

- A restack under `--cleanup` fails: no plan from the planner can be accepted, with at most one
  relaunch, or `commit-plan.py` fails to make the commits. The output branch is then created at
  the tip of the adopted generation's work branch, as without `--cleanup`.
- Creating the output branch fails. Without a restack, the adopted generation's work branch
  `{branch}-g{g}` holds the same commit. After one, the report shows the SHA of the restack's
  last commit, which has the same tree as the work branch but a different history.

### Requirements and cost

- The loop needs what `/cdev:coding` and `/creview:rounds` need: background subagents and
  `SendMessage`, nested sub-agent spawning of depth 3 or more
  (`CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH`), a repository you trust, and a session started at
  the repository root. It also needs the creview plugin, version 0.24.0 or later, which Claude
  Code installs with cdev as a dependency.
- The project's configure, build, and test steps must leave in the worktree neither initialized
  submodules nor untracked files that `.gitignore` does not cover. Git refuses to remove such a
  worktree, the inner skill keeps it, and the loop stops after that phase, typically the first
  coding phase.
- A run makes at most `(1 + max_sendbacks) × max_generations` cycles, 9 with the defaults.
  Each cycle runs `/cdev:coding` from team formation to QA and up to `--max-rounds` review
  rounds. `--pursuit` tends to run up to the generation limit. For the caps on sub-agents
  launched in a session and running at once, see the [creview README](../creview/README.md).
- A run makes two turning points per cycle and at most one more per send-back, up to
  `(2 + 3 × max_sendbacks) × max_generations`, 24 with the defaults.
- `--cleanup` adds one or two launches of the planner sub-agent at the end.
- The main working tree's sources are never changed. Its uncommitted changes are not part of
  the starting commit and are left out of the run; the loop says so at the start.

## Architect / coder / writer / reviewer agents

Apart from the comment and prompt specialists listed under Bundled agents, this plugin does not
bundle specialist reviewers. The `team-analysis`
task enumerates agents recursively (`**/*.md`, including subdirectories) from the
**destination project** (`.claude/agents/`) → **user** (`~/.claude/agents/`) → **plugin
bundle**, reads each agent's frontmatter `name` / `description`, and assigns the best-matching
specialists to the **reviewer** role — each reviewer covers a producer's domain, and an
out-of-domain specialty is never bundled onto one reviewer. **Architects, coders, and writers
always run as `general-purpose`**: some specialist agents emit malformed tool calls and stall,
and a producer works to its assigned scope and the project conventions while the specialist
reviewers enforce domain correctness. When no specialist matches a domain, the reviewer falls
back to `general-purpose`. Team re-formation after the design cells picks the reviewers it adds
from the same agent pool by the same rules. When team formation, the team re-formation, or QA's
choice of a fix specialist returns a bundled agent by its bare name, such as `prompt-sensei`,
and no agent of that name is available, the skill spawns `cdev:{name}`.

## Bundled agents and support files

- `agents/dev-helper.md` — mechanical teammate: team formation (scoping + selecting the
  architects, coders, writers, and reviewers), team re-formation after the design (assigning
  the files the design adds or changes to coders and writers and selecting any coders /
  writers / reviewers needed), QA (running the project's format / build / test, identifying
  the fix specialist on failure), and the commit plan (splitting the changed files into
  commits by logical change).
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
  code cells keep prompt files from over-specification), `commit-plan.md` (how the planners of
  the commit step and `/cdev:loop --cleanup` split changes into commits, the commit messages,
  and the plan file format).
- `scripts/` — `fetch-diff.sh` (snapshots the pre-coding tree, then captures the diff since
  coding start for the documentation cells and QA), `del-tmp.sh` (deletes the run's working
  directory under `.claude/tmp/`; with `--dry`, it only runs the containment check, which the
  skill does before creating that directory), `check-jsonl.py` (teammates check with it that
  each line of a `.jsonl` they wrote is one JSON object), and
  `lib/scratch-guard.py` (the shared `.claude/tmp/` containment check used by both; requires
  `python3` — see Requirements), `worktree.sh` (creates and removes the `--worktree`
  worktree), `restore.sh` (restores an entry of a design's restore list, or a documentation
  file a writer returns to a turning point's content, from its turning point commit into the
  working tree, refusing an entry whose restore would overwrite or
  delete an untracked file or a tracked file with local changes, or would change a path
  outside the entry; it may overwrite ignored files, as a git checkout does, so it is used
  only in the worktree of a `--worktree` run), and `commit-plan.py` (lists the changed paths,
  checks a commit plan against them, makes the planned commits from the working tree with
  `commit`, and with `build` restacks the changes between two commits as new commits without
  touching any ref, index, or working tree). The skills invoke them via
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
