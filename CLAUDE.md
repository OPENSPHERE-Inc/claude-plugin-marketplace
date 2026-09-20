# CLAUDE.md — opensphere-inc Claude Code Plugin Marketplace

## Project Overview

**opensphere-inc** is a Claude Code **plugin marketplace** maintained by **OPENSPHERE Inc.**
under the MIT license. It publishes three first-party plugins:

- **creview** — a multi-agent parallel code review workflow (`start` → `triage` → `respond`
  → `resolve`, plus an automatic multi-round driver `rounds`).
- **cprompt** — create / edit AI-facing prompts and self-check them against
  prompt-discipline rules.
- **cdev** — a team-native multi-agent coding workflow (`coding`: a standing team runs design
  and coding as paired review cells, then a QA gate). Requires background subagents and
  inter-agent messaging.

There is no compiled artifact. The deliverables are Markdown skills / templates / rules,
shell + Python helper scripts, and JSON manifests, consumed by Claude Code's plugin system.

- Repository content: **Markdown (AI-facing prompts)**, Bash, Python ≥ 3.9 (helper scripts)
- Distribution: **Claude Code plugin marketplace** (git-based)
- License: **MIT**

---

## Language Policy

This repo is intentionally bilingual; the rule is **not** "English only":

- **Active plugin files** (everything under `creview/`, `cprompt/`, and `cdev/` except their
  `README_ja.md`) are **English**. This includes SKILL.md, templates, bundled rules, and
  `agents/review-helper.md`.
- **`src/**`** is the **Japanese master** — every file there is Japanese.
- **`README_ja.md`** files are Japanese translations of the sibling `README.md`.
- All other top-level docs (`README.md`, this `CLAUDE.md`, `AGENTS.md`) are English.

---

## Repository Layout

```
claude-plugin-marketplace/
├── .claude-plugin/
│   └── marketplace.json          # Marketplace listing: creview, cprompt, cdev
├── README.md / README_ja.md      # Top README (EN) + Japanese translation, cross-linked
├── LICENSE                       # MIT
├── AGENTS.md / CLAUDE.md         # This documentation set
│
├── creview/                      # Plugin: parallel code review workflow (active, English)
│   ├── .claude-plugin/plugin.json
│   ├── README.md / README_ja.md
│   ├── skills/
│   │   ├── start/                # /creview:start   (from parallel-review)
│   │   ├── triage/               # /creview:triage  (review-respond: triage + estimate)
│   │   ├── respond/              # /creview:respond (review-respond: fix)
│   │   ├── resolve/              # /creview:resolve (from review-resolve)
│   │   └── rounds/               # /creview:rounds  (from review-rounds)
│   │       └── <skill>/SKILL.md + templates/*.md (+ scripts/compile-review.py for triage/respond/resolve)
│   ├── agents/                   # review-helper.md, comment-sensei.md, review-leader.md
│   ├── rules/                    # comment.md, document.md, review.md, wontfix.md, sub-agent.md, agents-detection.md, build-format-detection.md
│   └── scripts/                  # fetch-diff.sh, render-review.py, del-tmp.sh, check-jsonl.py, lib/scratch-guard.py
│
├── cprompt/                      # Plugin: prompt authoring (active, English)
│   ├── .claude-plugin/plugin.json
│   ├── README.md / README_ja.md
│   ├── skills/edit/              # /cprompt:edit (from prompt-editor) + templates/
│   └── rules/                    # prompt.md, document.md
│
├── cdev/                         # Plugin: multi-agent coding workflow (active, English)
│   ├── .claude-plugin/plugin.json
│   ├── README.md / README_ja.md
│   ├── skills/coding/            # /cdev:coding (SKILL.md + templates/: team-analysis, design, design-review, code, code-review, comment-review, qa)
│   ├── agents/                   # comment-sensei.md, dev-helper.md
│   ├── rules/                    # teammate.md, agents-detection.md, build-format-detection.md, comment.md, review.md, document.md, divergence.md
│   └── scripts/                  # fetch-diff.sh, del-tmp.sh, check-jsonl.py, lib/scratch-guard.py
│
├── src/                          # Japanese master, mirrors each plugin's tree 1:1 (minus .claude-plugin/README)
│   ├── creview/...               # src/creview/<same tree as creview/>
│   ├── cprompt/...               # src/cprompt/<same tree as cprompt/>
│   └── cdev/...                  # src/cdev/<same tree as cdev/>
│
├── tests/                        # scratch-guard-test.sh — repo-level self-tests (not shipped)
│
└── .claude/rules/                # Discipline rules for editing THIS repo
    ├── comment.md  commit.md  development.md
    ├── document.md  prompt.md  review.md
```

`src/<plugin>/X` corresponds 1:1 to `<plugin>/X` (e.g.
`src/creview/skills/start/SKILL.md` ↔ `creview/skills/start/SKILL.md`).

---

## Source-of-truth & Localization Workflow

The **Japanese `src/` tree is the editing master.** The active (English) plugin files are
produced from it by translation + the plugin transformations below.

When changing a plugin:

1. Edit the Japanese master under `src/<plugin>/...`.
2. Re-translate to English and re-apply the transformations to the active
   `<plugin>/...` file (or vice-versa for an English-first fix, then back-port to `src/`).
3. Keep `src/<plugin>/X` and `<plugin>/X` structurally 1:1 (same headings, steps,
   `template_id`, JSON schemas, emoji, tokens). Only natural-language prose differs by
   language.

### The plugin transformations (master → active)

- **Skill rename**: `parallel-review`→`start`, `review-respond`→`triage`+`respond`,
  `review-resolve`→`resolve`, `review-rounds`→`rounds`, `prompt-editor`→`edit`. The
  SKILL.md `name:` frontmatter is the bare skill-dir name.
- **`review-respond` split**: `/creview:triage` runs triage + estimate and **persists**
  `triage` / `estimate` into the review document (its own compile step). `/creview:respond`
  reads those back from the document, selects fix targets, fixes, build-verifies, and
  persists `status`. The two-skill boundary **is** the review gate; there is no
  `--no-confirm`. `/creview:respond` keeps `--commit`.
- **Path tokens** (see Important Warnings for the invariant):
  - SKILL.md bodies / `allowed-tools` and bundled agent definitions use
    `${CLAUDE_PLUGIN_ROOT}/...`.
  - `templates/*.md` and bundled rules (read by sub-agents) use the `{{plugin_root}}/...`
    launch variable.
- **Agent-dispatch generalization**: skills do **not** bundle specialist reviewers. The
  single-best-match resolution mechanics (enumerate agents recursively `**/*.md` across
  **destination project** → **user** → **plugin bundle** scopes, higher-priority scope wins
  on duplicate `name`, fall back to `general-purpose`) live in the shared bundled rule
  `rules/agents-detection.md`. The triage / analyze / format-build-verify / divergence-check sub-agents read it
  and supply only their match target + result field. `scope-analysis` keeps its own inline
  multi-select variant (it picks *all* relevant reviewers, not one). Only the mechanical
  helpers (`review-helper`, `comment-sensei`, `review-leader`) are bundled.

---

## Build / Run / Validation

There is **no build step**. Validation is consistency-checking + a manual install smoke test.

### Local consistency checks

```bash
# JSON manifests parse
python3 -c "import json; [json.load(open(f,encoding='utf-8')) for f in \
  ['.claude-plugin/marketplace.json'] + \
  [p+'/.claude-plugin/plugin.json' for p in ('creview','cprompt','cdev')]]; print('json ok')"

# Token-placement invariant: no ${CLAUDE_PLUGIN_ROOT} in templates / bundled rules,
# no {{plugin_root}} in SKILLs
grep -rl 'CLAUDE_PLUGIN_ROOT' {creview,cprompt,cdev}/skills/*/templates \
  {creview,cprompt,cdev}/rules && echo BAD || echo ok
grep -rl '{{plugin_root}}'   {creview,cprompt,cdev}/skills/*/SKILL.md   && echo BAD || echo ok

# src ↔ active file-set parity (per plugin, excluding .claude-plugin/README)
for p in creview cprompt cdev; do
  diff <(cd $p && find . -type f -not -path './.claude-plugin/*' -not -name 'README*.md' \
           -not -path '*/__pycache__/*' | sort) \
       <(cd src/$p && find . -type f -not -path '*/__pycache__/*' | sort) \
    && echo "$p parity ok"
done

# Scratch-guard self-test: containment behavior + byte-parity of the shared
# lib/del-tmp copies across creview/cdev and their src/ mirrors
bash tests/scratch-guard-test.sh
```

### Install smoke test

```
/plugin marketplace add <path-or-OPENSPHERE-Inc/claude-plugin-marketplace>
/plugin install creview@opensphere-inc
/plugin install cprompt@opensphere-inc
/plugin install cdev@opensphere-inc
```

Then exercise `/creview:start`, `/creview:triage`, `/creview:respond`, `/creview:resolve`
in a project that has its own `.claude/agents/` (or none, to test the `general-purpose`
fallback), `/cprompt:edit`, and `/cdev:coding` (in a runtime with background subagents and
inter-agent messaging).

---

## Architecture & Key Concepts

### Marketplace

`.claude-plugin/marketplace.json` (`name: opensphere-inc`) lists three plugins. `creview`,
`cprompt`, and `cdev` use `"source": "./<dir>"` (relative to the repo root). The `src/`
tree is **outside** the plugin source dirs, so it is not shipped with the installed plugins.

### Plugin skills

Plugin skills are namespaced `/<plugin>:<skill>` (`/creview:start`, `/cprompt:edit`). The
skill folder name == the `name:` in SKILL.md frontmatter (bare, not namespaced).

### The creview review pipeline (state lives in the review document)

```
/creview:start   → review doc with <!-- METADATA(id) --> markers (no decisions yet)
/creview:triage  → triage Sub + per-assignee estimate Subs → compile → persist
                    triage / estimate metadata into the doc
/creview:respond → select-fix-targets Sub reads doc metadata → fix Subs →
                    format&build-verify ⇄ build-fix loop → compile → persist status
/creview:resolve → analyze + verify Subs → compile → persist verification
/creview:rounds  → launches one review-leader Sub per phase per round (each Sub invokes
                    the phase's skill and runs it whole) + divergence gate after triage
                    (Round 2 on: detect → investigate → pause with the report) +
                    feedback re-fix inner loop
```

Each skill's `skills/<skill>/scripts/compile-review.py` (run directly by the leader, not a
sub-agent) aggregates the intermediate JSON (triage + estimate / status / verification) into
`events.jsonl`, invokes `render-review.py`, and prints a result JSON (summary line + counts);
the resolve variant also writes `resolve-summary.md`. `render-review.py` (bundled script)
inserts metadata before each `<!-- /METADATA(id) -->` marker from a one-pass `events.jsonl`.
Each `(id, field)` is written at most once per phase, so the split phases never produce
duplicate metadata lines. `render-review.py` is also kept for ad-hoc metadata edits (e.g.
adjusting a status / verification later in a chat).

### Sub-agent launch contract

Leaders pass a launch prompt that tells the sub-agent to `Read` an external
`templates/*.md` (each has a `template_id` UUID in frontmatter) and follow it. The leader
verifies the returned `template_id` against the per-step hard-coded UUID and relaunches on
mismatch. The leader resolves `${CLAUDE_PLUGIN_ROOT}` (plugin context) and passes it into
the launch prompt as the `plugin_root` variable so the template's `{{plugin_root}}/...`
references resolve for the sub-agent. See `creview/rules/sub-agent.md`.

---

## Code Style & Formatting

- **Markdown skills / templates / rules are AI-facing prompts.** Follow
  [.claude/rules/prompt.md](.claude/rules/prompt.md): imperative, minimal headings, no
  decorative Markdown, no meta-commentary, no chat-context dependence.
- **READMEs and this doc set are human-facing.** Follow
  [.claude/rules/document.md](.claude/rules/document.md) (audience-independent, escape `\|`
  in table cells, wrap ~100 cols).
- **Code comments** (scripts) follow
  [.claude/rules/comment.md](.claude/rules/comment.md): fix the code, defer with a short
  `FIXME:`/`TODO:`, no change-history narration.
- **Python** (helper scripts): PEP 8, runs on Python ≥ 3.9.
- **Preserve verbatim across translation/transformation**: every `{{...}}` placeholder,
  `${CLAUDE_PLUGIN_ROOT}`, `.claude/...` paths, `template_id` UUIDs, `allowed-tools`
  lines, JSON/JSONL field names, emoji (🔧 🚫 ▶️ 🔻 🚧 🟢 ✅ 💬), skill names, severity
  labels, and Markdown structure. Only translate prose.
- **Line endings**: existing skill/template files use CRLF (inherited from upstream).
  Do not bulk-reflow; keep diffs minimal.

---

## Coding Guidelines

### Editing an active skill or template

1. Make the change in the Japanese `src/<plugin>/...` master and in the active
   `<plugin>/...` file together (translation-paired).
2. Keep the structural 1:1 mapping (Source-of-truth section). Run the token-placement
   invariant check.
3. If you add a sub-agent template, give it a fresh `template_id` UUID and reference that
   exact UUID in the SKILL.md step that launches it.
4. Update the relevant `README.md` **and** `README_ja.md`.

### Adding a skill to a plugin

1. Create `<plugin>/skills/<name>/SKILL.md` (`name: <name>` frontmatter) and
   `templates/*.md` as needed; mirror it under `src/<plugin>/skills/<name>/` in Japanese.
2. Use `${CLAUDE_PLUGIN_ROOT}/...` in the SKILL body / `allowed-tools`; use
   `{{plugin_root}}/...` inside templates and the bundled rules they point to, and pass
   `plugin_root` in every launch prompt.
3. Resolve reviewers/fixers via the destination project's `.claude/agents/` with a
   `general-purpose` fallback — do not hardcode specialist agent names.
4. Add the command to the marketplace `README.md`/`README_ja.md` and the plugin
   `README.md`/`README_ja.md`.

### Adding / changing a marketplace entry

- First-party plugin: `"source": "./<dir>"`. External: `{"source":"github","repo":"…"}`.
- `name` in `.claude-plugin/plugin.json` must equal the marketplace entry `name` and the
  install target (`/plugin install <name>@opensphere-inc`).

### Naming conventions

- Skill dirs / `name:` — kebab/lower (`start`, `triage`, `select-fix-targets`).
- Template files — kebab-case `.md` with a `template_id` UUID in frontmatter.

---

## Testing & Validation

There is no automated test suite. Before considering a change done:

- Run the consistency checks in **Build / Run / Validation**.
- Confirm `src/` ↔ active parity (file set + `template_id` set identical per plugin).
- Confirm no stale upstream skill paths remain in active files
  (`parallel-review` / `review-respond` / `review-resolve` / `review-rounds` /
  `prompt-editor` as `.claude/skills/...` references).
- For prompt edits, re-check against [.claude/rules/prompt.md](.claude/rules/prompt.md);
  for doc edits, [.claude/rules/document.md](.claude/rules/document.md).
- Manually install all three plugins and exercise each command (see install smoke test).

---

## CI / CD

There is currently **no CI workflow** in this repository. Validation is manual /
local (the checks above). Adding a lightweight GitHub Action that runs the JSON /
invariant checks is a reasonable future task.

Release/versioning: each plugin's `.claude-plugin/plugin.json` carries its own semver
(`0.X.Y` pre-1.0).

---

## Common Tasks for AI Agents

### Re-syncing src ↔ active after an edit

Edit the Japanese master and the English active file as a pair. Verify: same file set,
same `template_id` set, token-placement invariant holds, READMEs (EN+JA) updated.

### Modifying the triage/respond split

The handoff is the **review document metadata**, not a temp dir. `/creview:triage` must
persist `triage`+`estimate` (its compile step); `/creview:respond` must read them from the
doc (`select-fix-targets.md`) — never assume a shared `tmp_dir` across the two skills.

### Updating documentation

Any change to `README.md` requires the matching `README_ja.md` update (and vice-versa);
keep the H1 cross-link line (`*[日本語版 README](README_ja.md)*` /
`*[English README](README.md)*`) intact.

---

## Important Warnings

- **Token-placement invariant.** The token follows who opens the file. Files Claude Code
  loads itself — SKILL.md bodies / `allowed-tools` and bundled agent definitions
  (`agents/*.md`) — use `${CLAUDE_PLUGIN_ROOT}`, which Claude Code expands. Files a sub-agent
  opens with Read — `templates/*.md` and the bundled rules it is pointed to
  (`rules/sub-agent.md`, `rules/teammate.md`, `rules/agents-detection.md`,
  `rules/build-format-detection.md`) — use `{{plugin_root}}`: Read returns them raw, so
  `${CLAUDE_PLUGIN_ROOT}` would stay unexpanded there, while `plugin_root` is already in the
  sub-agent's scope (the leader resolves it and passes it in the launch prompt; in cdev, the
  spawn contract). Never put `${CLAUDE_PLUGIN_ROOT}` in a template or a bundled rule; never
  put `{{plugin_root}}` in a SKILL. (`agents/review-helper.md` / `agents/review-leader.md`
  mention `{{plugin_root}}` only to name that template variable.)
  `rules/wontfix.md` carries `{{previous_round_doc_paths}}` on the same basis: every
  template that references it receives that launch variable.
- **`template_id` must match.** The SKILL step's hard-coded UUID and the template's
  frontmatter `template_id` must be identical, or the leader will loop relaunching.
- **src ↔ active parity is a contract.** Do not edit one side only. A structural
  divergence breaks the documented localization workflow.
- **`src/` is not shipped.** It sits outside the plugin `source` dirs on purpose. Do not
  move plugin runtime files under `src/` or reference `src/...` from active skills.
- **Destination-project agents, not bundled ones.** Active skills must resolve reviewers/
  fixers from the consuming project's `.claude/agents/` with a `general-purpose` fallback.
  Re-introducing hardcoded `*-sensei` names breaks portability.
- **CRLF line endings** in skill/template files are inherited from upstream. Avoid global
  reflow/`autocrlf` churn so diffs stay reviewable.
- **Bundled rule cross-references resolve relative to the file.** `creview/rules/sub-agent.md`
  points at sibling `comment.md`/`document.md` "in the same directory". Keep this relative
  form — absolute `.claude/...` paths would not resolve in the consuming project. (The
  detection rules
  `agents-detection.md` / `build-format-detection.md` instead express their plugin-bundled
  scope with the `{{plugin_root}}/...` launch variable; see the Token-placement invariant.)
- **`scripts/lib/scratch-guard.py`, `scripts/del-tmp.sh` and `scripts/check-jsonl.py` are
  byte-identical across all four copies** (`creview/`, `cdev/`, and their `src/` mirrors); each plugin ships its own copy
  because plugins install independently. Edit one copy and replicate to the other three;
  `tests/scratch-guard-test.sh` fails on any drift.
- **A sub-agent's Write is rejected when the `.md` basename starts with `REPORT`,
  `SUMMARY`, `FINDINGS`, or `ANALYSIS`** (case-insensitive, basename only). Claude Code's
  Write tool blocks it and tells the sub-agent to return the content as text instead. Output
  paths whose basename comes from a runtime value therefore carry a fixed prefix — creview's
  `{tmp_dir}/reviews/{scope_id}/review-{reviewer-name}.md` (the aggregator recovers the
  reviewer name by stripping it) and cdev's `{design_dir}/design-{slug}.md`. Keep those
  prefixes: a destination-project agent name or a team-analysis slug can begin with any of
  the four words.
- **Agent definitions use `tools:`; skills / commands use `allowed-tools:`.** `allowed-tools`
  is not a supported sub-agent frontmatter field, so a tool list written under that key in
  `<plugin>/agents/*.md` is ignored and the agent runs with every tool.

---

## Agent Teams

### Communication language

- Respond to the user in the language they use (Japanese ↔ English).
- Content written into the repo follows the **Language Policy** section (active = English,
  `src/**` = Japanese, `*_ja.md` = Japanese).

### Team leader policy

- The team leader focuses exclusively on orchestrating teammates and does not edit files
  itself.

### Team creation policy

- Team size 3–5, chosen by task; each teammate works on different files (no edit
  conflicts).
- Research / review first, then dispatch for parallel execution.
- Do not use sub-agents for work that fits a team. **Exception**: parallel reviews and
  **bulk translation** (the src ↔ active localization is a canonical bulk-translation use
  case) may use sub-agents.

### Recommended specialists

- **translation-sensei** — src ↔ active localization, README_ja sync (token-preserving
  translation).
- **prompt-sensei / prompt-editor** — SKILL.md / template prompt structure vs
  `.claude/rules/prompt.md`.
- **devops-sensei** — marketplace.json / plugin.json manifests, future CI.
- **python-sensei** — helper script (`scripts/*.py`, `compile-review.py`) correctness.

For full per-skill detail, see each plugin's `README.md` and the skill `SKILL.md` files.
