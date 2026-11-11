---
name: prompt-fix
description: Prompt for prompt-sensei to fix the AI-facing prompt files that failed the interpretation test, so that every unclear item becomes answerable from the prompt, in /creview:respond Step 4
template_id: cbbd9597-ca26-4308-a6d1-67cb18498aff
---

For each file in `{{result_path}}` whose `pass` is false and whose `untested` is null, make every one of its `unclear_items` answerable from the prompt, keeping the prompt contract-style as `{{plugin_root}}/rules/prompt.md` § Contract-style prompts defines it. Read `{{plugin_root}}/rules/sub-agent.md` and observe the common prohibitions.

- For an item about a goal or a contract the prompt sets, state the result or the contract it concerns.
- For an item about a method that an AI knowing the goal and the contracts would carry out correctly, state the goal so that the method is visibly left to the reader. Add no step, case, or wording that no contract calls for.
- Keep what each fix established for its finding, a FIXME an 🚧 Alternative estimate directed included: read in `{{document_path}}` the findings whose fixes changed the file, which `{{tmp_dir}}/statuses/*.jsonl` names.

Edit only those files. Then re-check the parts you changed against `{{plugin_root}}/rules/prompt.md` and fix any violation you introduced.

Return value: `{files: [path], template_id}`. `files` are the files you edited, repository-relative. Include `template_id` (Read from this template's frontmatter) verbatim in the return value.
