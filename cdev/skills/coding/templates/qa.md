---
name: qa
description: Prompt for the QA task (dev-helper) that runs the destination project's format, build, and test once and identifies the fix specialist on failure in cdev /coding Step 4
template_id: 6a711cba-0da8-4177-a41f-ddb4cf2a6e1f
---

Run the destination project's format, build, and test once each (test only when a test procedure is resolved), and on failure identify the responsible specialist. Do not run a fix loop; the leader relaunches you after a coder fixes. Source changes are limited to formatter auto-fixes (no logic changes).

Inputs: working directory `{{tmp_dir}}`, working-tree diff `{{diff_path}}` (`fetch-diff.sh` output), attempt number `{{attempt_num}}` (informational).

The command CWD is the project root. Use relative paths only. Do not pipe through `tee` / `Tee-Object`, and do not use compound commands (`;` / `&&`); the Bash tool returns the exit code automatically.

Procedure:

1. Resolve the format / build / test commands and `workflow_source` via `{{plugin_root}}/rules/build-format-detection.md`. If `workflow_source == "none"`, run nothing and go to step 5.
2. Read `{{diff_path}}` and classify the changes. If a stage's outcome cannot be affected by them (comments / docs / non-source only), mark that stage skip-eligible (`ran = false`, note the skip in `summary_line`). When in doubt, run it.
3. Format (only when a format command resolved): if it has a verification (dry-run) form, run it and apply the auto-fix form on violations; otherwise apply the auto-fix form to the changed files. Follow the resolved descriptor for target selection.
4. Build, then test:
   - Build (when a build command resolved and the stage is not skip-eligible; `build_ran = true`): run any configure command first, then the build, redirecting output to `{{tmp_dir}}/build.log`. The moment configure or build exits non-zero, set `failure.stage = "build"` and go to step 6.
   - Test (when a test command resolved, the build did not fail, and the stage is not skip-eligible; `test_ran = true`): run the test, appending output to `{{tmp_dir}}/build.log`. On non-zero exit, set `failure.stage = "test"` and go to step 6.
5. Visual check only (`workflow_source == "none"`): run nothing (`build_ran` / `test_ran` false). Read the changed files and check for visually obvious breakage (syntax, unresolved symbols). Set `workflow_warning` to "Format / build / test procedure is not declared, so automatic verification was skipped. Adding `.claude/rules/build-format.md` is recommended." Set `failure.stage = "visual"` only on an obvious break.
6. On failure (`failure != null`): Read the log (`{{tmp_dir}}/build.log`; absent in visual mode) and the error-producing files, analyze the cause, and set `error_summary` / `error_files` / `fix_guidance`. Resolve the fix specialist via `{{plugin_root}}/rules/agents-detection.md` (match target: the error content — language / build system / subsystem / test framework) into `suggested_specialist`.
7. Write `{{tmp_dir}}/qa-result.json`.

`{{tmp_dir}}/qa-result.json` format:

```
{"workflow_source": "build-format.md | CLAUDE.md | README.md | none", "workflow_warning": <string|null>, "format": {"format_violations_fixed": <int>}, "build": {"ran": <bool>, "success": <bool>}, "test": {"ran": <bool>, "success": <bool>}, "failure": {"stage": "build|test|visual", "error_summary": <string|null>, "error_files": ["src/foo:42", ...]|null, "suggested_specialist": <string|null>, "fix_guidance": <string|null>, "log_path": "{{tmp_dir}}/build.log"}|null}
```

Report to the leader (via SendMessage): `{success, format_violations_fixed, workflow_source, workflow_warning, build_ran, test_ran, suggested_specialist, error_summary, summary_line}`. `success` is `failure == null`; a stage with `ran = false` counts as passing. `summary_line` is <=200 chars (e.g. "build-format.md / format ok / build ok / test ok"). Mark the task done via TaskUpdate.
