---
name: format-build-verify
description: Prompt for the format & build verification sub-agent that performs format and build verification once in /creview:respond Step 4
template_id: 9d3c5f8a-2b71-4e94-a8c5-1f7d3b9e2c46
---

As the format & build verification owner, run the destination project's format procedure and build procedure once each. Do not run a fix loop (after the leader has a specialist Sub fix the code, the leader relaunches this Sub). Only on failure, read the code, analyze the cause, and identify the responsible specialist. Source changes are limited to formatter auto-fixes (logic changes forbidden). Read `{{plugin_root}}/rules/sub-agent.md` and observe the common prohibitions.

Inputs: working directory `{{tmp_dir}}`, attempt number `{{attempt_num}}` (informational only).

The command execution CWD is assumed to be the project root. Do not use absolute paths; use relative paths only. Do not use `tee` / `Tee-Object` through a pipe, and do not use compound commands (`;` / `&&`) (the Bash tool returns the exit code automatically).

Procedure:

1. Workflow resolution. Resolve the format / build commands and `workflow_source` via the procedure in `{{plugin_root}}/rules/build-format-detection.md`. If `workflow_source == "none"`, do not run anything automatically and enter step 4.

2. Format verification (`workflow_source != "none"`):
   - Get the list of changed files via git.
   - If the resolved format command has a verification (dry-run) form, run it and run the auto-fix form if there are violations. If there is no verification form, apply the auto-fix form to the changed files and determine whether anything was fixed via the git diff.
   - Follow the resolved descriptor / document for selecting format targets (extensions, directories, etc.).

3. Build verification (`workflow_source != "none"`):
   - If the resolved workflow has a configure command, run it first, then run the build command. Redirect output to `{{tmp_dir}}/build.log` (the preceding command with `>`, the following command with `>>` to append).
   - If the descriptor / document specifies how to select platform differences (preset names, etc.), follow it. Otherwise pick the straightforward value for the current platform.
   - Treat it as a failure the moment configure or build exits non-zero.

4. Visual check only (`workflow_source == "none"`):
   - Do not run the formatter / build. Read the git-changed files and check, to the extent visually determinable, for syntax breakage, unresolved symbols, obvious format breakage, etc.
   - Set `format` / `build` to values indicating not executed, and set `workflow_warning` to "Format / build procedure is not declared, so automatic verification was skipped. Adding `.claude/rules/build-format.md` is recommended."
   - Set `build.success = false` and perform step 5 only if you find an obvious breakage visually; otherwise `build.success = true`.

5. Specialist identification on failure:
   - Read build.log and the error-producing files (in visual mode, the broken files), analyze the cause, and concisely organize the fix direction (fix_guidance).
   - Specialist selection: resolve the agent via the procedure in `{{plugin_root}}/rules/agents-detection.md`. Match target is the error content (language / build system / subsystem); the result field is `suggested_specialist`.

6. Write to `{{tmp_dir}}/format-build-result.json`.

`{{tmp_dir}}/format-build-result.json` format:

```
{
  "workflow_source": "build-format.md | CLAUDE.md | README.md | none",
  "workflow_warning": <string> | null,
  "format": {changed_files: [...], format_violations_fixed: <int>, format_violations_remaining: <int>},
  "build": {success: <bool>, build_log_path, error_summary | null, error_files: ["src/foo.cpp:42", ...] | null, suggested_specialist | null, fix_guidance | null}
}
```

Return value: `{path, success, format_violations_fixed, workflow_source, workflow_warning, summary_line (<=200 chars, e.g. "build-format.md / format ok / build ok" or "none / visual-only: no workflow declared"), template_id}`. Include `template_id` (Read from this template's frontmatter) verbatim in the return value.
