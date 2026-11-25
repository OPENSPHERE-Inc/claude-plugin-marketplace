---
name: loop
description: Run a coding task through /cdev:coding and /creview:rounds as one pipeline without asking the user for decisions. When the review detects a divergence, the task goes back to /cdev:coding on the same branch; after the review, a post-mortem decides whether to finish or to start over from the start commit. Send-backs and restarts each stay within a limit. Use when the user names this skill or asks to take a coding task from implementation through review unattended. Requires the creview plugin, a runtime with background subagents (Agent run_in_background) and inter-agent messaging (SendMessage), and nested sub-agent spawning of depth 3 or more.
allowed-tools: Skill, Agent, Read, Write, Glob, Grep, Bash(cd:*), Bash(mkdir:*), Bash(git rev-parse:*), Bash(git branch:*), Bash(git check-ref-format:*), Bash(git status:*), Bash(git log:*), Bash(git show:*), Bash(git diff:*), Bash(git grep:*), Bash(python3 ${CLAUDE_PLUGIN_ROOT}/scripts/check-jsonl.py:*), Bash(python3 ${CLAUDE_PLUGIN_ROOT}/scripts/commit-plan.py paths:*), Bash(python3 ${CLAUDE_PLUGIN_ROOT}/scripts/commit-plan.py check:*), Bash(python3 ${CLAUDE_PLUGIN_ROOT}/scripts/commit-plan.py build:*), Bash(${CLAUDE_PLUGIN_ROOT}/scripts/del-tmp.sh:*)
---

# Coding Loop

As the **loop leader**, you run a coding task through cycles of `/cdev:coding` and `/creview:rounds`. When the review detects a divergence, you send the task back to `/cdev:coding` in the same generation; at a generation's end, a post-mortem sub-agent judges whether to finish or to start a new generation from the start commit. You do not design, write, review, or fix code. You hold only the state file, paths, counts, end reasons, verdicts, short warnings, and the output of `commit-plan.py` (for its runs in § Cleanup, only the parts § Cleanup keeps), and do not Read the body of a design, review, divergence report, post-mortem, handoff the post-mortem writes, or cleanup plan. The one exception is an escalation you arbitrate as the `/cdev:coding` leader (§ Running an inner skill): its § Escalation lets you Read that cycle's handoff, and with a send-back handoff, the post-mortem handoff it references.

## Requirements

This skill inherits the requirements of `/cdev:coding` and `/creview:rounds`. In Step 1, terminate with the reason, creating nothing, when:

- `Agent` with `run_in_background`, or `SendMessage`, is unavailable.
- `creview:rounds` is not among the available skills: ask the user to install the creview plugin.
- The repository's origin is untrusted, judged as in the Trust premise of `/cdev:coding`.

The nesting depth cannot be checked beforehand: when it falls short, `/creview:rounds` ends on an error (§ Stop conditions).

Run both skills inline in this session, never through a sub-agent: the `/cdev:coding` leader must be the main session, which receives its teammates' `to: "main"` messages, and delegating `/creview:rounds` adds a nesting level.

## Input

When the argument is `$ARGUMENTS`, interpret it as the coding task and options. `{task}` is the argument with the options of § Options removed; pass it unchanged to `/cdev:coding` in every cycle.

## Options

- `--branch {name}` (default `cdev-loop-{timestamp}`) — The output branch's name, and the prefix of the work branches and turning points (§ Names and paths).
- `--max-sendbacks N` (default 2, range 0–5) — The maximum number of send-backs per generation.
- `--max-generations N` (default 3, range 1–5) — The maximum number of generations.
- `--pursuit` (default OFF) — Let the post-mortem also redo a generation with no residual problem when a clearly better approach can be shown.
- `--cleanup` (default OFF) — On a normal end, create the output branch at the head of commits that restack the adopted generation's changes from the start commit (§ Cleanup).
- `--output {dir}` (default `.claude/tmp/cdev-loop-{timestamp}/`) — The run directory `{loop_dir}`.

Passed through: `--review-rounds N` (range 1–10) and `--qa-attempts N` (range 1–10) to `/cdev:coding` as `{coding_args}`; `--max-rounds N` (range 1–20), `--adversarial`, and `--adr` to `/creview:rounds` as `{rounds_args}`; `--strict-docs` to both, recorded also as `limits.strict_docs`. Each is empty when none is given.

Show an error and terminate on a value out of range, and on any of these options:

- `--worktree`, `--commit`, `--incremental`: state in the error that they are always on.
- `--confirm`, `--confirm-round`, `--base`.
- `--on-divergence`, `--result`, `--handoff`, `--team-tag`, `--commit-always`: this skill sets them for the inner skills.

## Names and paths

- `{loop_branch}`: the `--branch` value or its default. The inner skills use `{branch}` for a variable of their own.
- `{repo_root}`: the output of `git rev-parse --show-toplevel` in Step 1, the main working tree's root.
- `{loop_dir}`: an absolute path; resolve a relative `--output` against `{repo_root}`.
- `{hhmmss}`: the time part of `{timestamp}`.
- Work branch of generation g: `{loop_branch}-g{g}`.
- Turning points (TPs) of cycle c of generation g: TP-A `{loop_branch}-tp/g{g}c{c}-coding-start` and TP-B `{loop_branch}-tp/g{g}c{c}-coding-done`, and for c > 1, TP-R `{loop_branch}-tp/g{g}c{c}-review-base`, which Step 4 step 2 creates as the base of that cycle's review.
- Output branch: `{loop_branch}`.

Create a branch only with `git branch {name} {commit}`, which touches no working tree. Never move or delete a TP, and never rewrite a work branch's history.

A cycle's directory `{loop_dir}/g{g}c{c}/` holds `design/`, `coding-result.jsonl`, `review/`, `rounds-result.jsonl`, and `handoff.md`. The post-mortem of generation g writes to `{loop_dir}/g{g}/`. The cleanup plan is `{loop_dir}/cleanup/plan.jsonl`.

## Running an inner skill

Invoke it with the Skill tool, with the arguments the Step names. Act as its leader through its last step, as when the user invokes it directly, then continue at the item after the one that invoked it: its closing report does not end this skill. Continue there as well when it terminates before its last step, such as on a Step 1 error or an unmet requirement; judge its outcome from its result file, where a missing file is an outcome too. While it runs, its plugin root, which `plugin_root` and the `CLAUDE_PLUGIN_ROOT` placeholder name, `{timestamp}`, `{tmp_dir}`, `{branch}`, and its other variables are the values it fixes; once it returns, they are this skill's.

Do not use `EnterWorktree` / `ExitWorktree`: the inner skills create and enter their worktrees. After each return, confirm that `git rev-parse --show-toplevel` prints `{repo_root}`; if it does not, run `cd {repo_root}` and confirm again in a separate Bash call, and when it still does not, end as an error (Step 6).

## State file

`{loop_dir}/state.jsonl` is the source of truth for the run's progress. Write it with Write as one JSON object on a single line, validate each write with `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/check-jsonl.py {loop_dir}/state.jsonl`, and fix and re-validate on error. When you cannot write it or make it valid, show the error and terminate, writing `loop-summary.md` (Step 6) if you can.

Write:

- `position`, as each of Steps 2–6 starts.
- Each side effect that breaks when repeated, right after it happens: a work branch's creation (the generation's entry), a TP's creation (`turning_points`), and an inner skill's invocation (the cycle's `coding.started` / `review.started` set to true just before invoking, and its `skill_dir`, the skill's base directory the Skill tool shows, right after invoking, before entering its steps).
- In a send-back, the incremented c and `sendbacks`, the new cycle's entry, and `position` in one write.
- Each step's results, once known.

```json
{"task": "<task>", "timestamp": "...", "repo_root": "<abs>", "loop_dir": "<abs>",
 "skill_dir": "<abs>", "start_commit": "<S>", "branch": "<loop_branch>", "doc_lang": "<chat language>",
 "limits": {"max_sendbacks": 2, "max_generations": 3, "pursuit": false, "cleanup": false,
            "strict_docs": false},
 "coding_args": "<pass-through options or empty>", "rounds_args": "<same>",
 "position": {"generation": 1, "cycle": 2, "step": "review"},
 "generations": [
   {"generation": 1, "work_branch": "...-g1", "sendbacks": 1, "unresolved_divergence": false,
    "cycles": [
      {"cycle": 1, "handoff": null, "review_base": "...-tp/g1c1-coding-start",
       "coding": {"started": true, "skill_dir": "<abs>", "result_path": "...",
                  "committed": true, "qa_passed": true, "prompt_test_passed": true,
                  "restored_from": [], "fixme_count": 0},
       "review": {"started": true, "skill_dir": "<abs>", "result_path": "...",
                  "end_reason": "divergence", "rounds": 3}}],
    "postmortem": {"md_path": "...", "json_path": "...", "verdict": "redo",
                   "basis": "residual", "adopted_generation": null,
                   "summary_line": "...", "fallback": null}}],
 "turning_points": [{"name": "...", "commit": "<sha>", "kind": "coding-start",
                     "generation": 1, "cycle": 1}],
 "adopted_generation": null,
 "cleanup": null,
 "warnings": [{"generation": 1, "cycle": 1, "source": "coding", "message": "..."}],
 "end": null}
```

- `skill_dir` at the top level: this skill's base directory, which the Skill tool showed when it invoked this skill.
- `position.step`: `init`, `coding`, `review`, `sendback`, `postmortem`, or `finish`.
- `coding` / `review`: `started` and `skill_dir` at the invocation, the other fields from the result file.
- `review_base`: the name of the TP the cycle's `/creview:rounds` takes as `--base`. In a send-back's new cycle, null until Step 4 step 2 writes it.
- `turning_points[].kind`: `coding-start` for a TP-A, `coding-done` for a TP-B, `review-base` for a TP-R.
- `postmortem.fallback`: the reason when Step 5 fell back on its own verdict, otherwise null.
- `cleanup`: null when `--cleanup` is off and until § Cleanup starts, then `{"head": "<H>", "plan_path": "<abs>", "launches": 1, "commit": "<sha>", "count": 3, "skipped": null, "fallback": null}`:
  - `head` and `plan_path`: written as § Cleanup starts.
  - `launches`: the number of the planner's launches, those redone on a resume included, kept as a record only.
  - `commit` / `count`: the head and the number of the commits `build` created; null until `build` succeeds.
  - `skipped`: `"no-change"` when S and H have the same tree, otherwise null.
  - `fallback`: the reason, in `{doc_lang}`, when § Cleanup fell back, otherwise null.
- `end`: written in Step 6, `{"kind": "normal"|"error", "step": "<the step it stopped in>", "error": "<string>"|null, "output_branch": "<name>"|null}`.
- `warnings`: only short warning texts. From `coding-result.jsonl`: an unpassed QA, stating whether it is environmental; the files the interpretation test failed or left untested; the restore entries refused (`restore_refused`); a team re-formation fallback; that the documentation the design lists got no documentation cell for want of a writer (`docs_unwritten`); the `commit_warning` when not null; each entry of `doc_departures`, a departure of the code from the design or the task that a writer reported. From `rounds-result.jsonl`: its `workflow_warnings` and `prompt_warnings`. Your own: a missing divergence report, a review base fallen back to the TP-A of g{g}c1 (Step 4 step 2), a post-mortem fallback, a cleanup fallback, a failed output branch creation. `source` is `coding`, `review`, `sendback`, `postmortem`, `cleanup`, or `finish`.

When you cannot tell your position from context, Read this file and the `SKILL.md` in its top-level `skill_dir`. In a `SKILL.md` you Read, the `CLAUDE_PLUGIN_ROOT` placeholder stays unexpanded: take it as the directory two levels above the `skill_dir` you Read it from, for this skill and for an inner skill alike. Continue from `position`:

- Do not repeat a side effect the file records.
- When a work branch, TP, or the output branch to create already exists at the commit it should point to, record it without creating it. The output branch should point to `cleanup.commit` when it is recorded, otherwise to the head of the adopted generation's work branch. When a work branch or TP points elsewhere, end as an error; when the output branch does, handle it as a failed creation in Step 6 step 3.
- When `position.step` is `coding` or `review` and that cycle's `started` is true:
  - With no `skill_dir` recorded, the inner skill had not entered its first step: invoke it again.
  - When the cycle's result file exists, the inner skill has ended: continue from the Step's handling of the result file.
  - When it does not exist and the context shows the inner skill ended, by its closing report or an early termination, treat it as an abnormal end with no result file.
  - Otherwise the inner skill is still running in this session: do not invoke it again; continue as its leader, Reading `{skill_dir}/SKILL.md` when its instructions are not in context.
- When `position.step` is `sendback`, Step 4 step 1 is done: continue from its step 2, or from its step 3 when the cycle's `review_base` is not null.
- When the generation's `postmortem` records a verdict, continue from Step 5 step 5 with it. Writing a handoff and launching a post-mortem whose verdict is not recorded only overwrite their outputs: redo them.

## Handoff

A handoff is Markdown in `{doc_lang}` with these sections, in this order, their headings in `{doc_lang}`: a title naming its cycle `g{g}c{c}`; the kind (send-back or grand reset) and the starting point; why to redo; the policy; what to keep; what to avoid; the candidate return points; the references (read-only).

You write the send-back handoff, only with what you can write without Reading a body:

- Starting point: the work branch and its head commit. The task is already implemented on it; design and implement the change that removes the divergence's sources.
- Why and policy: the divergence report's path and the cycle's `review_base` (its name and commit), with the instruction to follow each `D-n`'s Source and its recommended Fix proposal. Add that the proposal, written for `/creview:rounds`, is to be read as follows: take the change to the code or prompts it describes, whatever carrier finding or fix sub-agent it names. Where it treats findings as Won't Fix or leaves a decision to the user, decide that in the design, and state the accepted scope and its premises in the same file as the code or text they constrain, in a form that file's discipline keeps (in an AI-facing prompt, a judgment WHY): no triage decision carries over to a later review, and after a later send-back the base of a review can lie past this cycle's changes. When `limits.strict_docs` is false, add that the send-back leaves out each `D-n` the report marks as a documentation divergence: the review applied its Fix proposal in the round it stopped in.
- Keep: the existing implementation and review fixes the divergence does not involve and, from generation 2 on, the policy of the post-mortem handoff in the references. Add, from generation 2 on, that this policy and what that handoff says to avoid prevail over the report's Fix proposals, which were written without knowledge of them: remove each source only by changes that keep to them, and when no such change removes a source, state in the design that it cannot be removed without departing from them and leave it to the generation's post-mortem.
- Avoid: bringing back a form the report names as a source and, from generation 2 on, what the post-mortem handoff says to avoid.
- Candidate return points: every TP of this generation so far, each with its name, its commit, and what it holds. The TP-A of g{g}c1 holds the start commit, before implementation; the TP-B of g{g}c{k} holds cycle k after `/cdev:coding`, before its review fixes; the TP-A of g{g}c{k} for k > 1 holds the code after cycle k-1's review; the TP-R of g{g}c{k} holds the code at the start of the round before the one in which cycle k-1's review stopped, and is the base of cycle k's review. State that building on the current head is the default, and that returning means restoring a TP's content into files and committing forward, which `/cdev:coding` does, never rewriting history. State also that lines returned to their content at the cycle's `review_base`, by a restore or by an edit, do not appear in the diff the next review reads.
- References: the divergence report; from generation 2 on, the post-mortem handoff (the `handoff` of the generation's first cycle in the state file); and for each cycle of this generation, the design documents (`design_paths` of `coding-result.jsonl`), the review documents (`doc_paths` of `rounds-result.jsonl`), and the final report (`final_report_path` of `rounds-result.jsonl`). Read only these paths from the result files.

## Cleanup

Restack the changes of the adopted generation a (`adopted_generation` in the state file) from S by the plan a planner sub-agent writes, and obtain the head C of the commits this creates.

When `cleanup` in the state file records `commit`, `skipped`, or `fallback`, continue at Step 6 step 3 with the output commit it gives: the `commit`, or for `skipped` or `fallback` the recorded `head`. Otherwise go through the items from 1, taking a recorded `head` as H: a launch or `build` whose result is not recorded changed no ref.

1. Get H with `git rev-parse {loop_branch}-g{a}`, and record `cleanup` with `head` and `plan_path` (`{loop_dir}/cleanup/plan.jsonl`).
2. When S and H have the same tree, compared with `git rev-parse`, record `skipped` as `"no-change"` and continue at Step 6 step 3 with H as the output commit.
3. Create `{loop_dir}/cleanup/` and launch the planner in the foreground via `Agent(subagent_type="general-purpose", prompt=...)`. At each launch, increment `launches` and record it. `{rejection}` is `(none)` at the first launch.

   ```
   As your first action, you MUST Read `${CLAUDE_PLUGIN_ROOT}/skills/loop/templates/cleanup.md`. Do not perform any other judgment, action, or tool call before the Read completes. After reading, follow its instructions.

   Variables (substitute into the template's {{...}} placeholders):
   - plugin_root: ${CLAUDE_PLUGIN_ROOT}
   - main_root: (none)
   - target_dir: {repo_root}
   - task: {task}
   - state_path: {loop_dir}/state.jsonl
   - adopted_generation: {a}
   - start_commit: {S}
   - head_commit: {H}
   - doc_lang: {doc_lang}
   - plan_path: {loop_dir}/cleanup/plan.jsonl
   - rejection: {rejection}

   Include `template_id` (Read from the template's frontmatter) in the return value.
   ```

4. Accept the plan when the returned `template_id` is `64157739-d562-4866-b6fb-0691183710ac` and `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/commit-plan.py check --base {S} --head {H} --plan {loop_dir}/cleanup/plan.jsonl`, run by you, exits 0 with `ok` true.
5. When you do not accept it:
   - When `check` exited non-zero with no `errors` in its output, a failure the planner cannot fix, such as a git error: fall back without relaunching.
   - Otherwise, after the first launch of this run of § Cleanup: write in `{rejection}` the `template_id` mismatch and the `errors` of `check`, whichever occurred, and launch once more (item 3).
   - Otherwise: fall back.
6. Once you accept it, run `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/commit-plan.py build --base {S} --head {H} --plan {loop_dir}/cleanup/plan.jsonl`. When it exits 0, record its `commit` and `count`, and continue at Step 6 step 3 with that `commit` as the output commit. Otherwise fall back.
7. To fall back, record the reason, in `{doc_lang}`, in `cleanup.fallback` and in `warnings` with `source` `cleanup`, and continue at Step 6 step 3 with H as the output commit. The end stays normal.

Of the planner's return value, judge only by `template_id`. Of the output of `commit-plan.py`, keep only the `errors` and `error` of `check`, and the `commit`, `count`, and `error` of `build` with the subjects of its `commits`.

## Step 1 — Initialization

1. If `git rev-parse --show-prefix` prints a non-empty value, show an error that the skill requires a session started at the repository root and terminate the skill.
2. Parse and validate the options (§ Options), and check § Requirements.
3. Fix `{timestamp}` (`YYYYMMDD-HHMMSS`), `{doc_lang}` (the chat language), `{repo_root}`, `{loop_branch}`, and `{loop_dir}`.
4. Show an error and terminate when:
   - `git check-ref-format --branch {loop_branch}` fails.
   - `git branch --list` shows a branch named `{loop_branch}`, `{loop_branch}/*`, `{loop_branch}-g*`, `{loop_branch}-tp`, or `{loop_branch}-tp/*`. A `{loop_branch}/*` branch cannot coexist with `refs/heads/{loop_branch}`, so the output branch could not be created.
   - `{loop_dir}` exists and is not empty: a result file an earlier run left would be misread as that of an inner skill that ended without writing one.
5. Run `${CLAUDE_PLUGIN_ROOT}/scripts/del-tmp.sh --dry .claude/tmp/cdev-loop-{timestamp}`, which refuses a symlinked `.claude` or `.claude/tmp`; on a non-zero exit, show its error and terminate the skill. Pass this path rather than `{loop_dir}`: del-tmp.sh refuses a path outside `.claude/tmp/`. Then create `{loop_dir}` with `mkdir -p`.
6. Record the start commit S with `git rev-parse HEAD`. When `git status --porcelain` prints anything, state on the console that the uncommitted changes are not in S and fall outside the run.
7. Initialize `state.jsonl` with `skill_dir` and with `position` at g = 1, c = 1, `init`, and go to Step 2.

Never change the main working tree's sources. Between phases, stay at `{repo_root}`.

## Step 2 — Coding phase

1. Set `position` to `coding`. Console: `## Loop g{g}c{c} — Coding`.
2. When c = 1, create the work branch at S, and record the generation's entry with its first cycle, whose `handoff` is null in g1 and the previous post-mortem's handoff path after that, and whose `review_base` is the name of the TP-A of g{g}c1.
3. Create TP-A: at S when c = 1, otherwise at the work branch's head. Record it with its commit.
4. Create `{loop_dir}/g{g}c{c}/` and run `cdev:coding` (§ Running an inner skill) with these arguments, adding `--handoff` in every cycle but g1c1:

   ```
   cdev:coding --worktree={loop_branch}-g{g} --output {loop_dir}/g{g}c{c}/design --result {loop_dir}/g{g}c{c}/coding-result.jsonl --team-tag g{g}c{c}-{hhmmss} --commit-always [--handoff {loop_dir}/g{g}c{c}/handoff.md] [{coding_args}] {task}
   ```

5. Once it returns, Read `coding-result.jsonl`.
   - The coding phase ended abnormally when the file is missing or is not valid JSON, `aborted` is not null, or `kept_worktree` is not null: end as an error (Step 6).
   - Otherwise record its results and warnings (§ State file), create TP-B at the work branch's head, record it, and go to Step 3, even when QA or the interpretation test did not pass.

## Step 3 — Review phase

1. Set `position` to `review`. Console: `## Loop g{g}c{c} — Review`.
2. Run `creview:rounds` with these arguments, where `{loop_review_base}` is the cycle's `review_base`.

   ```
   creview:rounds {loop_dir}/g{g}c{c}/review --worktree={loop_branch}-g{g} --incremental --base {loop_review_base} --on-divergence stop --result {loop_dir}/g{g}c{c}/rounds-result.jsonl [{rounds_args}]
   ```

3. Once it returns, Read `rounds-result.jsonl` and record its results and warnings.
4. Go on by its content:
   - The file is missing or unreadable, `error` is not null, `kept_worktree` is not null, or `end_reason` is none of `converged`, `max-rounds`, and `divergence`: end as an error (Step 6).
   - `converged` or `max-rounds`: go to Step 5.
   - `divergence` with `divergence_report_path` null or naming no file: record a warning, set the generation's `unresolved_divergence` to true, and go to Step 5.
   - `divergence` while the generation's `sendbacks` is below `--max-sendbacks`: go to Step 4.
   - `divergence` otherwise: set `unresolved_divergence` to true and go to Step 5.

## Step 4 — Send-back

1. Increment c and the generation's `sendbacks`, and record them in one write with the new cycle's entry and `position` at `sendback`. Console: `## Loop g{g}c{c} — Send-back`.
2. Fix the cycle's review base. R is the second-to-last entry of `round_start_revs` in `{loop_dir}/g{g}c{c-1}/rounds-result.jsonl`: the start commit of the round before the one that review stopped in. When `round_start_revs` is an array of two entries or more and `git rev-parse --verify --quiet "{R}^{commit}"` exits 0, with only `{R}` substituted, create TP-R at R, and record it in `turning_points` and its name in the cycle's `review_base` in one write. Otherwise record the name of the TP-A of g{g}c1 in `review_base` and a warning with `source` `sendback` in `warnings`, in one write. Keep this `review_base` whatever this cycle's `/cdev:coding` then does: lines it returns to their content at that base do not appear in the diff from it, which is accepted as the price of narrowing the review to the changes after R.
3. Write the send-back handoff (§ Handoff) to `{loop_dir}/g{g}c{c}/handoff.md`, record its path in the cycle's `handoff`, and return to Step 2.

## Step 5 — Post-mortem and grand reset

1. Set `position` to `postmortem`. Console: `## Loop g{g} — Post-mortem`.
2. Launch the post-mortem in the foreground via `Agent(subagent_type="general-purpose", prompt=...)`. `{handoff_path}` is `{loop_dir}/g{g+1}c1/handoff.md` while g is below `--max-generations`, otherwise `(none)`.

   ```
   As your first action, you MUST Read `${CLAUDE_PLUGIN_ROOT}/skills/loop/templates/postmortem.md`. Do not perform any other judgment, action, or tool call before the Read completes. After reading, follow its instructions.

   Variables (substitute into the template's {{...}} placeholders):
   - plugin_root: ${CLAUDE_PLUGIN_ROOT}
   - main_root: (none)
   - target_dir: {repo_root}
   - task: {task}
   - state_path: {loop_dir}/state.jsonl
   - generation: {g}
   - remaining_generations: {--max-generations minus g}
   - pursuit: {true under --pursuit, otherwise false}
   - doc_lang: {doc_lang}
   - postmortem_md_path: {loop_dir}/g{g}/postmortem.md
   - postmortem_json_path: {loop_dir}/g{g}/postmortem.jsonl
   - handoff_path: {handoff_path}

   Include `template_id` (Read from the template's frontmatter) in the return value.
   ```

3. Accept the result when the returned `template_id` is `158ca65c-c8f4-4d8f-bb6d-ce62fd015be1` and `postmortem.jsonl` is valid JSON in the template's format with:
   - `verdict` `finish`: `adopted_generation` an integer from 1 to g.
   - `verdict` `redo`: `basis` `residual`, or `improvement` under `--pursuit`; and, when `{handoff_path}` is not `(none)`, `handoff_path` equal to it, naming an existing file.

   Otherwise launch it once more. When the second result is not accepted either, fall back on the verdict finish with g as the adopted generation, and record why in `postmortem.fallback` and in `warnings`. Do not Read `postmortem.md` or the handoff.
4. Record the verdict in the generation's `postmortem`.
5. On `redo` with g below `--max-generations`, grand reset: increment g, set c = 1, and return to Step 2, which creates the new work branch and its TP-A at S. Otherwise set `adopted_generation` to the verdict's adopted generation, or to g on `redo`, and go to Step 6 as a normal end.

## Step 6 — Finish

1. Set `position` to `finish`. Console: `## Loop — Finish`.
2. On a normal end, fix the output commit: under `--cleanup` (`limits.cleanup`), run § Cleanup and take its result; otherwise, the head of the adopted generation's work branch. On an error end, fix none.
3. On a normal end, create the output branch `{loop_branch}` at the output commit. When that fails, the end stays normal: record the error in `end`, with `output_branch` null, and in `warnings`, and report where the result is: without a restack, that the adopted generation's work branch holds the same commit; after a restack, C's SHA, and that it has the work branch's tree but a different history. On an error end, create no output branch.
4. Record `end`, and write `{loop_dir}/loop-summary.md` in `{doc_lang}`, following `${CLAUDE_PLUGIN_ROOT}/rules/document.md`, with:
   - the end reason of each generation and cycle, and on an error end, the step it stopped in and the error;
   - the send-backs, each post-mortem's verdict (`summary_line`, and `basis` for a redo), and the adopted generation;
   - on a normal end under `--cleanup`, the result of the restack (the commit count and each subject, or why it skipped or fell back), that the original history stays on the adopted generation's work branch, and that no intermediate commit was built or tested. Take the subjects from `build`'s output or, when it is not in context, from `git log` of the commits from S to `cleanup.commit`;
   - the TPs, and this command for the user to delete them all: `git for-each-ref --format='%(refname:short)' 'refs/heads/{loop_branch}-tp/' | xargs git branch -D`;
   - the warnings, and any worktree kept.
5. Report to the console. On a normal end: the output branch, the `loop-summary.md` path, the generation, cycle, and send-back counts with each generation's verdict, and under `--cleanup` the number of restacked commits, or the skip or fallback. On an error end: the step it stopped in, the error, the last work branch, and the `loop-summary.md` path. Do not push or create a pull request.

## Stop conditions

Stop continuing automatically and end as an error in Step 6 only when:

- Step 1's preconditions do not hold. Terminate in Step 1 itself, writing no `loop-summary.md`.
- `/cdev:coding` ends abnormally (Step 2).
- `/creview:rounds` ends on an error (Step 3).
- A result file names a kept worktree, whose branch the next phase could not check out.
- A work branch or TP cannot be created, or the working directory cannot be returned to `{repo_root}`.
- `state.jsonl` cannot be written or made valid. Terminate as § State file directs.

Otherwise judge and continue on your own, without asking the user. On an error end, leave every TP and work branch made so far.
