---
name: build-fix
description: Prompt for the build-fix specialist sub-agent that fixes build errors in /creview:respond Step 3
template_id: 6e2a9f5c-1d83-4b74-9c2e-5a8d3f1b7e29
---

Fix the build errors. Read `{{plugin_root}}/rules/sub-agent.md` and observe the common prohibitions.

Inputs (Read the build section of `{{tmp_dir}}/format-build-result.json`):

- error_summary / error_files / fix_guidance / build_log_path
- For the full build log, Read `build_log_path` (usually `{{tmp_dir}}/build.log`) (only when needed). When `workflow_source` is `none` (visual check only), no build log exists; treat error_files and fix_guidance as the primary information.

Procedure:

1. Read the sources listed in error_files plus the surrounding code to identify the cause of the error.
2. Implement the fix (conform to the coding conventions in CLAUDE.md).
3. Self-review: Re-read the changed locations and confirm both that the error is resolved and that no new issues were introduced.

Return value: `{description, template_id}`. Include `template_id` (Read from this template's frontmatter) verbatim in the return value.
