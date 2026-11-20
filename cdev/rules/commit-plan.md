# Commit plan rule

Write a plan that assigns each path changed from the base B to the target T to one commit of a series stacked in order on B. B and T, the arguments to pass to `commit-plan.py`, and the values of `{{plugin_root}}`, `{{main_root}}`, and `{{target_dir}}` are given by the template or skill that had you Read this rule.

## Splitting

- Make each commit one logical change, a unit that can be reviewed and reverted on its own.
- Put code and its tests in the same commit.
- Put files the project requires to change together in the same commit. Example: the translation pairs or byte-identical copies the project's conventions define.
- Put what review fixed into the commit of the change it fixed.
- A small change with one purpose may be one commit. Do not make one commit per file.
- Order the commits by dependency, putting what is referenced in the same commit as what references it or in an earlier one. The intermediate commits are neither built nor tested.
- A path takes its content in T in the commit it goes into. The script cannot split the change of one file, so put a file that serves several logical changes into one of their commits.
- Put each group of `together` in the output of `paths` into one commit.

## Messages

- Match the language and format of the `git log` up to B.
- Follow the project's commit conventions, if any, such as those in `CLAUDE.md`, `AGENTS.md`, or `.claude/rules/`. Resolve `.claude/rules/` against `{{main_root}}` when it is other than `(none)`, otherwise against `{{target_dir}}`.
- Without conventions, write one concise line stating what the code now does.
- Include no finding IDs, no workflow step names (e.g. review response, send-back), and no trailers the conventions do not require.

## Plan file

- A record file: one line per commit, in the order the commits are stacked. The rule of `{{plugin_root}}/rules/teammate.md` § Tools that a `.jsonl` file is written as one object on one line does not apply to this file.
- Each line is a JSON object with exactly two keys, `message` and `paths`.
- `message`: a string whose first line (the subject) holds a character other than whitespace. Write a multi-line message with `\n` inside the JSON string; no value spans several lines.
- `paths`: a non-empty array, each element a repository-relative path exactly as `commit-plan.py paths` prints it.
- Across the plan, each path the output of `paths` lists appears exactly once, and no other path appears.

```
{"message": "Validate the input of the parser", "paths": ["src/parser.py", "tests/test_parser.py"]}
{"message": "Document the parser options", "paths": ["README.md"]}
```

## Tools

- `python3 {{plugin_root}}/scripts/commit-plan.py paths {the B and T arguments}` gives the paths to assign with their `status`, and `together`, the groups of paths that go into one commit.
- Revise the plan until `python3 {{plugin_root}}/scripts/commit-plan.py check {the same arguments} --plan {plan file}` passes (exit code 0 and `ok` true). The `errors` of a failure name the line numbers and paths at fault.
- Exit code 2 is a usage error of the command line. Fix the command.
- Any other failure with no `errors` is not caused by the plan; do not retry. When `check` failed, keep the plan file as you wrote it; when `paths` failed, write no plan file. Either way, include that `error` in your report.
- You need not read every diff body. When the path list, the design documents, and the existing commit messages settle the split, plan from them.
- As the planner, do not stage, commit, or change a ref, and do not run `build` or `commit` of `commit-plan.py`.
