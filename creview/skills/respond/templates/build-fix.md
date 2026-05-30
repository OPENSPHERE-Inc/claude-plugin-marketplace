---
name: build-fix
description: Prompt for the build/test-fix specialist sub-agent that fixes build or test errors in /creview:respond Step 4
template_id: 6e2a9f5c-1d83-4b74-9c2e-5a8d3f1b7e29
---

Fix the build or test errors. Read `{{plugin_root}}/rules/sub-agent.md` and observe the common prohibitions.

Inputs (Read the `failure` section of `{{tmp_dir}}/format-build-result.json`):

- stage (`build` / `test` / `visual`) / error_summary / error_files / fix_guidance / log_path
- For the full build / test log, Read `log_path` (usually `{{tmp_dir}}/build.log`) (only when needed). When `stage` is `visual` (visual check only), no log exists; treat error_files and fix_guidance as the primary information.

Procedure:

1. Read the sources listed in error_files plus the surrounding code to identify the cause of the error.
2. Implement the fix (conform to the coding conventions in CLAUDE.md).
3. Self-review: Re-read the changed locations and confirm both that the error is resolved and that no new issues were introduced.

Return value: `{description, template_id}`. Include `template_id` (Read from this template's frontmatter) verbatim in the return value.
