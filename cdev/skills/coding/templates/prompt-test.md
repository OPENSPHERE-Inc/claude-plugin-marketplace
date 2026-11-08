---
name: prompt-test
description: Prompt for the interpretation-test task (prompt-sensei) in cdev /coding Step 4, which has a context-free sub-agent read each AI-facing prompt file changed in the run and records the checklist items it cannot answer from the prompt
template_id: a443d213-c166-48e2-b48e-0d08337bf6b5
---

Test whether each AI-facing prompt file changed in this run is interpreted without missing or misleading information. Edit no prompt; write only `{{output_path}}`.

Inputs: task `{{task}}`, design sections `{{design_paths}}`, working-tree diff `{{diff_path}}` (`fetch-diff.sh` output), attempt number `{{attempt_num}}` (informational).

Steps:

1. From `{{diff_path}}`, list the files created or modified in this run that are AI-facing prompts per `{{plugin_root}}/rules/prompt.md`. If there are none, write `{"pass": true, "files": []}` to `{{output_path}}` and report.
2. For each file, build a checklist from the file and the design sections. Each item is a question of the form "what should an agent reading this prompt do in situation X?" (e.g. how it decides a value the input omits, the fallback when a step fails, the input / output flow between steps, the threshold of each branch). Cover the prompt's input spec, each step, each branch condition, and its output spec.
3. For each file, launch a tester with the Agent tool (`general-purpose`, in the foreground, without a name; launch the testers of several files in parallel). The tester must carry no context of this run, so launch a new one per file and per attempt, never a teammate. Its prompt:

```
Prompt-interpretation tester. Read {prompt_path} and answer each checklist item below in 1-2 sentences, using only what is readable from that prompt and the files it tells its reader to Read — no external knowledge, no guessing. Resolve the path placeholders those files use with these values: {placeholder_values}. Report an item as unclear with a one-sentence reason when the prompt leaves it unanswerable, ambiguous, or contradictory. Do not propose fixes or edit anything.

Checklist:
1. {item 1}
2. {item 2}
...

Return value: {pass, unclear_items: [{item, reason}]} (pass: true if unclear_items is an empty array)
```

   `{prompt_path}` is `{{target_dir}}` joined with the file's path. `{placeholder_values}` maps each path placeholder the file and the files it names use to the path it stands for in `{{target_dir}}`; a plugin root stands for the directory of the plugin the file belongs to, the one holding its `.claude-plugin/plugin.json`. Leave out a placeholder whose path you cannot determine, and write `(none)` when no placeholder is left.

4. Write `{{output_path}}`; `pass` at the top is true when every file passes, and `item` / `reason` are in {{doc_lang}}:

```
{"pass": <bool>, "files": [{"path": <string>, "pass": <bool>, "unclear_items": [{"item": <string>, "reason": <string>}]}]}
```

Report completion to the leader (SendMessage with `to: "main"`) as one line: the number of files tested and of files with unclear items.
