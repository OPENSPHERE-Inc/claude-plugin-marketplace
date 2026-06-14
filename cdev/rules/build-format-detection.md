# Build / format workflow detection shared rule

Common procedure for detecting the destination project's format and build procedures. The caller receives the resolved commands and `workflow_source`.

## Resolution order

Resolve in the following priority order, stopping at the first stage that resolves.

1. Structured descriptor `build-format.md` (see "Descriptor format" below). Search the scopes below in priority order, recursively within each (`**/build-format.md`, so subdirectories like `.claude/rules/local/build-format.md` are included). Adopt the descriptor from the first scope where one is found and use its format / build (and test, if `## Test` is present) commands verbatim. `workflow_source = "build-format.md"`. `{{plugin_root}}` is the launch variable from the prompt that had you Read this rule (same value the calling template uses).
   1. Project scope (highest): `.claude/rules/**/build-format.md` (relative to the working directory)
   2. User scope: `~/.claude/rules/**/build-format.md`
   3. Plugin-bundled: `{{plugin_root}}/rules/**/build-format.md`
   If a scope contains more than one match, prefer the one directly under the scope root (e.g. `.claude/rules/build-format.md`); otherwise take the shallowest path, breaking ties by ascending path string.
2. If no scope has a descriptor, derive from the destination project root documentation.
   - Read `CLAUDE.md` and interpret its build-procedure, format, and (if present) test sections to derive the commands. `workflow_source = "CLAUDE.md"`.
   - Otherwise Read `README.md` and derive similarly. `workflow_source = "README.md"`.
3. If no commands can be determined from any of them, `workflow_source = "none"`.

## Descriptor format (`build-format.md`)

Written under Markdown headings (commands relative to the project root as CWD):

- `## Format` — the format-apply command. Optionally a verification (dry-run) command and target-file selection rules.
- `## Build` — the build command. Optionally a preceding configure command and per-platform selection rules.
- `## Test` — the test command (optional).

Each command is assumed to be written in a directly executable form; execute it literally without interpretation. The test command is optional in every source (a descriptor `## Test` section, or a test section in `CLAUDE.md` / `README.md`); test verification runs only when one is resolved.
