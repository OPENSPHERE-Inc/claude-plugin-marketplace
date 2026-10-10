# cprompt

*[日本語版 README](README_ja.md)*

Create and edit AI-facing prompts (agent / skill / rule / command / generic
prompt) for Claude Code, then self-check and fix them against
prompt-discipline rules.

## Skill

| Command | Maps from | Purpose |
|---------|-----------|---------|
| `/cprompt:edit` | `prompt-editor` | Create or edit an AI-facing prompt; self-check against the bundled `prompt.md`, compress, and test. |

Usage: `/cprompt:edit <kind + target path + requirements>` for a new prompt,
or `/cprompt:edit <existing path> <edit requirements>` to edit. When the kind
is not given it is inferred from the target path under the destination
project's `.claude/` (`.claude/agents/{name}.md` → agent, etc.).

Options:

- `--commit` (default off) — commit the files the run created or edited in one commit.
- `--worktree[=branch]` (default off) — work in a separate git worktree under
  `.claude/worktrees/` so the main working tree stays untouched; enables
  `--commit`. The worktree checks out `branch` — an existing local branch as
  is, or a new one created from the current HEAD; without `=branch`, a new
  branch `cprompt-edit-{timestamp}` is created. The branch checked out in the
  main working tree cannot be used. A relative target path resolves inside the
  worktree. At the end the worktree is removed and the branch is kept; a
  worktree left with uncommitted changes is kept and its path is reported.

## Bundled support files

- `skills/edit/templates/` — scaffolds for each prompt kind plus the
  `prompt.md` test checklist.
- `rules/` — `prompt.md` (prompt discipline) and `document.md` (human-facing
  documentation discipline), referenced by the skill via
  `${CLAUDE_PLUGIN_ROOT}/rules/...`.
- `scripts/worktree.sh` — creates and removes the `--worktree` worktree.

## Japanese master (repository-root `src/cprompt/`)

The Japanese master lives at the repository root under `src/cprompt/`,
mirroring this plugin's tree one-to-one (`src/cprompt/skills/edit/SKILL.md`
↔ `cprompt/skills/edit/SKILL.md`, etc.) with the same plugin skill name.
The active English file here is produced by translating and transforming that
master. To update: edit the Japanese master under `src/cprompt/`, then
re-translate and re-apply the transformations (rename, `${CLAUDE_PLUGIN_ROOT}`
path rewrites) to the active skill.
