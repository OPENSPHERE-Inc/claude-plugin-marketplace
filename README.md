# opensphere-inc — Claude Code Plugin Marketplace

*[日本語版 README](README_ja.md)*

A Claude Code plugin marketplace maintained by OPENSPHERE Inc.

## Plugins

| Plugin | Description |
|--------|-------------|
| `creview` | Multi-agent parallel code review workflow: start → triage → respond → resolve, plus an automatic multi-round driver. |
| `cprompt` | Create and edit AI-facing prompts and self-check them against prompt-discipline rules. |
| `cdev` | Team-native multi-agent coding workflow: a standing team runs design and coding as paired review cells, then a QA gate. |
| `agent-sequencer` | External plugin ([OPENSPHERE-Inc/agent-sequencer](https://github.com/OPENSPHERE-Inc/agent-sequencer)). Required to run `creview`'s `review_rounds.py` sequencer program. |

## Installation

Add this marketplace, then install the plugins:

```
/plugin marketplace add OPENSPHERE-Inc/claude-plugin-marketplace
/plugin install creview@opensphere-inc
/plugin install cprompt@opensphere-inc
/plugin install cdev@opensphere-inc
```

`creview`, `cprompt`, and `cdev` are self-contained. The optional `agent-sequencer`
entry is resolved from its own GitHub repository and is only needed for the
sequencer-driven variant of the multi-round review (see
[creview/README.md](creview/README.md)).

## Skill commands

| Command | Purpose |
|---------|---------|
| `/creview:start` | Run a parallel code review and produce a review document. |
| `/creview:triage` | Triage and estimate the findings; persist `triage` / `estimate` into the document. |
| `/creview:respond` | Fix the Will-Fix / Maintain / Alternative findings; persist `status`. |
| `/creview:resolve` | Verify fixes against the source; persist `verification`. |
| `/creview:rounds` | Automatically iterate the four phases across multiple rounds. |
| `/cprompt:edit` | Create or edit an AI-facing prompt and self-check it. |
| `/cdev:coding` | Implement a coding task end to end: design and coding as paired review cells, then a QA gate. |

## Reviewer / fixer agents

`creview` does **not** bundle specialist reviewer agents. It enumerates agents
recursively (`**/*.md`, so subdirectories are included) from the **destination
project** (`.claude/agents/`) → **user** (`~/.claude/agents/`) → **plugin
bundle**, reads each agent's `description`, and selects the most relevant agents
per finding. When no suitable agent exists, it falls back to
`general-purpose`. The `review-helper` aggregation agent is bundled with the
`creview` plugin.

## Source of truth and localization

The repository-root `src/` directory holds the **Japanese master** of every
plugin, mirroring each plugin's own tree: `src/<plugin>/...` matches
`<plugin>/...` (e.g. `src/creview/skills/start/SKILL.md` corresponds to
`creview/skills/start/SKILL.md`). It contains the skills, rules, scripts,
agents, and (for `creview`) the sequencer program.

The active plugin files (the English files at the plugin roots) are the
Japanese `src/` master translated into English with the plugin transformations
applied. When updating a plugin, edit the Japanese master under
`src/<plugin>/`, then re-translate and re-apply the transformations to the
active English files (skill rename, `${CLAUDE_PLUGIN_ROOT}` / `{{plugin_root}}`
path rewrites, `review-respond` → `triage` + `respond` split, agent-dispatch
generalization).
