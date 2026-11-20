---
name: commit-plan
description: Prompt for the commit-plan task (dev-helper) in cdev /coding Step 5, which splits the working tree's changes into commits by logical change and writes the plan to pass to commit-plan.py
template_id: 24c5ea40-4550-47e6-bd21-9026658866f3
---

Read `{{plugin_root}}/rules/commit-plan.md` and, following it, write to `{{output_path}}` a plan that splits the working tree's changes into commits by logical change and passes `commit-plan.py check`.

Base and target: B is `HEAD`, and T is the working tree of `{{target_dir}}`. Run `paths` and `check` of `commit-plan.py` with `--worktree` and an `--exclude` option for each path of `{{exclude}}`.

Inputs: the task `{{task}}`, the design documents in `{{design_paths}}`, and the files `paths` lists with their diffs. A new untracked file does not appear in `git diff`; Read it.

When `{{rejection}}` is not `(none)`, it states the `errors` of `check` for which your previous plan was not accepted; revise the plan to clear them.

Write only `{{output_path}}`, and change neither the shared index, a ref, nor the working tree. The plan file is the record file of the rule's § Plan file; the rule of `{{plugin_root}}/rules/teammate.md` § Tools that a `.jsonl` file is written as one object on one line does not apply to it.

Report completion to the leader (SendMessage with `to: "main"`) as one line naming `{{output_path}}` and the number of commits in the plan, adding the `error` of any failure with no `errors`.
