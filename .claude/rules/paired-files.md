# Paired Files

No change in this repository may leave an edit in one file of a pair without the same edit in its counterparts, including an edit a skill's procedure confines to the files it names.

## Pairs

A file's counterparts are all the files paired with it, directly or through another pair: the four copies of `rules/prompt.md` are counterparts of one another.

- **Plugin file and `src/` master.** Every file under `creview/`, `cdev/`, and `cgh/`, except those under `.claude-plugin/` and the `README*.md` files, is paired with the file at the same relative path under `src/` (`creview/X` ↔ `src/creview/X`).
  - Markdown files (SKILL.md, templates, rules, agent definitions): the shipped plugin file is English and the `src/` file is its Japanese master. They are structurally 1:1 as `CLAUDE.md` § Source-of-truth & Localization Workflow defines and keep identical what § Code Style & Formatting preserves verbatim.
  - Other files (scripts): the `src/` file is a byte-identical copy and stays English.
- **README pair.** Each `README.md` is paired with the `README_ja.md` in the same directory, its Japanese translation, which keeps the H1 cross-link line.
- **Byte-identical copies.** Each file is paired with the files `CLAUDE.md` § Important Warnings declares byte-identical with it, such as the copies of a shared script across plugins, `creview/rules/prompt.md` with `cdev/rules/prompt.md`, and their `src/` mirrors with each other.
- **No counterpart.** Every other file has none, such as the files under `.claude/` and `tests/`, `CLAUDE.md`, `AGENTS.md`, `LICENSE`, and the manifests.

Counterparts settle only which files take the same edit; every other consistency duty stays as `CLAUDE.md` states it.

## Contracts

- **Closure.** When you create, modify, delete, or rename a file, make the same edit to its counterparts in the same task. When you decide which files to edit — a design's file list, the files assigned to an agent or a cell, the fix targets, the files a request names — include each file's counterparts.
- **Precedence.** When a skill, a template, a plugin rule, or an agent definition limits your edits to the files it or your task names, treat the counterparts of those files as named too, and widen the scope to nothing else. This applies, for example, to the fixes, the prompt review's violation fixes and compression, and the prompt-fix of `/creview:respond`, and to the coders, the prompt teammate, and the QA-fix cells of `/cdev:coding`.
- **Same change.** Derive each counterpart's edit from the edit you made: translate it between an English and a Japanese file, copy it between byte-identical copies. After the task, an English and a Japanese counterpart differ only in the language of their prose, and byte-identical copies not at all, even when a step edits each file by its own judgment, such as a compression run on each file's own range. This covers only the differences the task's edit leaves; a difference that predates the task is fixed only when fixing it is the task.
- **One owner.** When you split files among agents, give all the files of a pair to the same agent.
- **Reporting.** Include the counterparts you edited in every list of edited files you report — a returned `files`, a status's `files`, a changed-file list — so that the steps that run on the edited files, such as the prompt review, the interpretation test and its retest, and the commit, cover them too.
- **Cannot edit.** When you cannot edit a counterpart — your role is read-only, or it is outside your write scope — do not report the pair's edit as complete; report to whoever assigned the task which counterparts need the same edit.
