# opensphere-inc — Claude Code Plugin Marketplace

*[日本語版 README](README_ja.md)*

A Claude Code plugin marketplace maintained by OPENSPHERE Inc.

## Plugins

| Plugin | Description |
|--------|-------------|
| `creview` | Multi-agent parallel code review workflow: start → triage → respond → resolve, plus an automatic multi-round driver. |
| `cdev` | Team-native multi-agent coding workflow: a standing team runs design and coding as paired review cells, then a QA gate. AI-facing prompts also get a prompt-discipline self-check, compression, and an interpretation test. |
| `cgh` | GitHub pull request workflow on top of `creview`: post a triaged review, run a merge gate, answer posted reviews, and verify the fixes of your own review. |

## Installation

Add this marketplace, then install the plugins:

```
/plugin marketplace add OPENSPHERE-Inc/claude-plugin-marketplace
/plugin install creview@opensphere-inc
/plugin install cdev@opensphere-inc
/plugin install cgh@opensphere-inc
```

`creview` and `cdev` are self-contained. `cgh` depends on `creview`, which Claude Code
installs with it.

## Skill commands

| Command | Purpose |
|---------|---------|
| `/creview:start` | Run a parallel code review of local changes or a GitHub pull request and produce a review document. |
| `/creview:triage` | Triage and estimate the findings of a review document or of a GitHub pull request's comments; persist `triage` / `estimate` into the document. |
| `/creview:respond` | Fix the Will-Fix / Maintain / Alternative findings, reviewing and interpretation-testing the AI-facing prompt files the fixes create or change; persist `status`. |
| `/creview:resolve` | Verify the findings of a review document or of a GitHub pull request's comments against the source; persist `verification`. |
| `/creview:rounds` | Automatically iterate the four phases across multiple rounds. |
| `/cdev:coding` | Implement a coding task end to end, AI-facing prompts included: design and coding as paired review cells, then a QA gate. |
| `/cgh:review` | Review a pull request and, on your instruction, post the findings as a Request Changes or Comment review. |
| `/cgh:gate` | Judge whether a self-reviewed pull request can merge as it stands and, on your instruction, post PASS or BLOCK. Run it again until it passes. |
| `/cgh:respond` | Triage a pull request's reviews, fix them on your confirmation (`--no-confirm` skips it) and, after you push and instruct it, reply with what was done and the commit. |
| `/cgh:resolve` | Verify the findings you raised, posted by `/cgh:review` or written by hand, and, on your instruction, reply with the result and the commit. |

## Reviewer / fixer agents

Apart from the bundled agents described below, `creview` does **not** bundle
specialist reviewer agents. It enumerates agents recursively (`**/*.md`, so
subdirectories are included) from the **destination project**
(`.claude/agents/`) → **user** (`~/.claude/agents/`) → **plugin bundle**, reads
each agent's `description`, and selects the most relevant agents per finding.
When no suitable agent exists, it falls back to `general-purpose`.
From the plugin bundle, the selection candidates are the comment-discipline
reviewer `comment-sensei` and the prompt-discipline reviewer `prompt-sensei`,
which `/creview:respond` also runs on the AI-facing prompt files its fixes create
or change. The skills launch the other bundled agents by name: workflow helper
agents such as the `review-helper` aggregation agent, the fixed-role reviewer
`pr-description-reviewer`, the extractor `pr-comment-compiler`, and the
interpretation tester `prompt-tester`.

- `pr-description-reviewer` checks a pull request's description and CI results
  when `/creview:start` reviews a pull request.
- `pr-comment-compiler` extracts findings from a pull request's comments when
  `/creview:triage` or `/creview:resolve` is given a pull request URL.
- `prompt-tester` has Read, Glob, and Grep only and tests how the prompt files
  `/creview:respond`'s fixes create or change are interpreted.

## Source of truth and localization

The repository-root `src/` directory holds the **Japanese master** of every
plugin, mirroring each plugin's own tree: `src/<plugin>/...` matches
`<plugin>/...` (e.g. `src/creview/skills/start/SKILL.md` corresponds to
`creview/skills/start/SKILL.md`). It contains the skills, rules, scripts, and
agents.

The active plugin files (the English files at the plugin roots) are the
Japanese `src/` master translated into English with the plugin transformations
applied. When updating a plugin, edit the Japanese master under
`src/<plugin>/`, then re-translate and re-apply the transformations to the
active English files (skill rename, `${CLAUDE_PLUGIN_ROOT}` / `{{plugin_root}}`
path rewrites, `review-respond` → `triage` + `respond` split, agent-dispatch
generalization).
