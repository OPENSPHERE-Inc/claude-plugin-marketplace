# CLAUDE.md — opensphere-inc Claude Code Plugin Marketplace

## Project Overview

**opensphere-inc** is a Claude Code **plugin marketplace** maintained by **OPENSPHERE Inc.**
under the MIT license. It publishes four first-party plugins:

- **creview** — a multi-agent parallel code review workflow (`start` → `triage` → `respond`
  → `resolve`, plus an automatic multi-round driver `rounds`).
- **cprompt** — create / edit AI-facing prompts and self-check them against
  prompt-discipline rules.
- **cdev** — a team-native multi-agent coding workflow (`coding`: a standing team runs design
  and coding as paired review cells, then a QA gate). Requires background subagents and
  inter-agent messaging.
- **cgh** — a GitHub pull request workflow on top of creview (`review`, `gate`, `respond`,
  `resolve`, each taking a pull request URL). Depends on creview; posts only on the user's
  instruction and never approves or merges.

There is no compiled artifact. The deliverables are Markdown skills / templates / rules,
shell + Python helper scripts, and JSON manifests, consumed by Claude Code's plugin system.

- Repository content: **Markdown (AI-facing prompts)**, Bash, Python ≥ 3.9 (helper scripts)
- Distribution: **Claude Code plugin marketplace** (git-based)
- License: **MIT**

---

## Language Policy

This repo is intentionally bilingual; the rule is **not** "English only":

- **Active plugin files** (everything under `creview/`, `cprompt/`, `cdev/`, and `cgh/` except their
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
│   └── marketplace.json          # Marketplace listing: creview, cprompt, cdev, cgh
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
│   ├── agents/                   # review-helper.md, comment-sensei.md, review-leader.md, pr-description-reviewer.md, pr-comment-compiler.md
│   ├── rules/                    # comment.md, document.md, review.md, wontfix.md, sub-agent.md, agents-detection.md, build-format-detection.md, doc-worktree.md, pr-comment-doc.md
│   └── scripts/                  # fetch-diff.sh, render-review.py, del-tmp.sh, check-jsonl.py, worktree.sh, gh-pr.py, compile-pr-comments.py, lib/scratch-guard.py
│
├── cprompt/                      # Plugin: prompt authoring (active, English)
│   ├── .claude-plugin/plugin.json
│   ├── README.md / README_ja.md
│   ├── skills/edit/              # /cprompt:edit (from prompt-editor) + templates/
│   ├── rules/                    # prompt.md, document.md
│   └── scripts/                  # worktree.sh
│
├── cdev/                         # Plugin: multi-agent coding workflow (active, English)
│   ├── .claude-plugin/plugin.json
│   ├── README.md / README_ja.md
│   ├── skills/coding/            # /cdev:coding (SKILL.md + templates/: team-analysis, design, design-review, code, code-review, comment-review, qa)
│   ├── agents/                   # comment-sensei.md, dev-helper.md
│   ├── rules/                    # teammate.md, agents-detection.md, build-format-detection.md, comment.md, review.md, document.md, divergence.md
│   └── scripts/                  # fetch-diff.sh, del-tmp.sh, check-jsonl.py, worktree.sh, lib/scratch-guard.py
│
├── cgh/                          # Plugin: GitHub pull request workflow on top of creview (active, English)
│   ├── .claude-plugin/plugin.json  # declares the dependency on creview
│   ├── README.md / README_ja.md
│   ├── skills/                   # review (+ templates/comment-wording.md), gate, resolve (+ templates/reply-translate.md), respond (+ templates/reply-draft.md)
│   ├── agents/                   # reply-drafter.md, comment-writer.md
│   ├── rules/                    # leader.md, gate-focus.md
│   └── scripts/                  # gh-review.py, del-tmp.sh, lib/scratch-guard.py
│
├── src/                          # Japanese master, mirrors each plugin's tree 1:1 (minus .claude-plugin/README)
│   ├── creview/...               # src/creview/<same tree as creview/>
│   ├── cprompt/...               # src/cprompt/<same tree as cprompt/>
│   ├── cdev/...                  # src/cdev/<same tree as cdev/>
│   └── cgh/...                   # src/cgh/<same tree as cgh/>
│
├── tests/                        # scratch-guard-test.sh, gh-review-test.py — repo-level self-tests (not shipped)
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
  - `templates/*.md` and bundled rules (opened with Read by a sub-agent, or by a leader for
    `rules/doc-worktree.md` / `rules/pr-comment-doc.md` / `cgh/rules/leader.md`) use the
    `{{plugin_root}}/...` launch variable.
- **Agent-dispatch generalization**: skills do **not** bundle specialist reviewers. The
  single-best-match resolution mechanics (enumerate agents recursively `**/*.md` across
  **destination project** → **user** → **plugin bundle** scopes, higher-priority scope wins
  on duplicate `name`, fall back to `general-purpose`) live in the shared bundled rule
  `rules/agents-detection.md`. The triage / analyze / format-build-verify / divergence-check sub-agents read it
  and supply only their match target + result field. `scope-analysis` keeps its own inline
  multi-select variant (it picks *all* relevant reviewers, not one). Only the mechanical
  helpers (`review-helper`, `comment-sensei`, `review-leader`) are bundled, plus
  `pr-description-reviewer`, the fixed-role reviewer of a pull request's description and CI
  results in `/creview:start`'s PR mode, and `pr-comment-compiler`, the fixed-role extractor of
  findings from a pull request's comments in the PR mode of `/creview:triage` / `resolve`,
  bundled so that their `tools:` keep the untrusted pull request text away from a
  shell and the network. Launch a bundled agent by its
  namespaced name (`creview:review-helper`, `cdev:dev-helper`); a bare name resolves only
  to a project or user agent of that name. The detection rules and `scope-analysis.md`
  likewise return the namespaced name for an agent they pick from the plugin bundle.
  In creview, the detection rule and `scope-analysis.md` leave the fixed-role bundled
  agents (`review-helper`, `review-leader`, `pr-description-reviewer`, `pr-comment-compiler`)
  out of the
  candidates, so `comment-sensei` is the only bundled candidate.

---

## Build / Run / Validation

There is **no build step**. Validation is consistency-checking + a manual install smoke test.

### Local consistency checks

```bash
# JSON manifests parse
python3 -c "import json; [json.load(open(f,encoding='utf-8')) for f in \
  ['.claude-plugin/marketplace.json'] + \
  [p+'/.claude-plugin/plugin.json' for p in ('creview','cprompt','cdev','cgh')]]; print('json ok')"

# Token-placement invariant: no ${CLAUDE_PLUGIN_ROOT} in templates / bundled rules,
# no {{plugin_root}} in SKILLs
grep -rl 'CLAUDE_PLUGIN_ROOT' {creview,cprompt,cdev,cgh}/skills/*/templates \
  {creview,cprompt,cdev,cgh}/rules && echo BAD || echo ok
grep -rl '{{plugin_root}}'   {creview,cprompt,cdev,cgh}/skills/*/SKILL.md   && echo BAD || echo ok

# src ↔ active file-set parity (per plugin, excluding .claude-plugin/README)
for p in creview cprompt cdev cgh; do
  diff <(cd $p && find . -type f -not -path './.claude-plugin/*' -not -name 'README*.md' \
           -not -path '*/__pycache__/*' | sort) \
       <(cd src/$p && find . -type f -not -path '*/__pycache__/*' | sort) \
    && echo "$p parity ok"
done

# Every sub-agent launch in a SKILL passes target_dir (prints offending lines)
grep -nF 'plugin_root = ${CLAUDE_PLUGIN_ROOT}' {creview,cdev}/skills/*/SKILL.md \
  src/{creview,cdev}/skills/*/SKILL.md | grep -vF 'target_dir' && echo BAD || echo ok
# Same for the colon-form launch block of /creview:rounds (one target_dir line per block)
pat='- plugin_root: ${CLAUDE_PLUGIN_ROOT}'
for f in creview/skills/rounds/SKILL.md src/creview/skills/rounds/SKILL.md; do
  [ "$(grep -cF -- "$pat" "$f")" = "$(grep -A2 -F -- "$pat" "$f" | grep -cF -- '- target_dir:')" ] \
    && echo "ok $f" || echo "BAD $f"
done

# Scratch-guard self-test: containment behavior, worktree.sh, and byte-parity of the
# shared script copies across creview/cdev/cprompt/cgh and their src/ mirrors
bash tests/scratch-guard-test.sh

# cgh's GitHub script, with GitHub and git faked
python3 tests/gh-review-test.py
```

### Install smoke test

```
/plugin marketplace add <path-or-OPENSPHERE-Inc/claude-plugin-marketplace>
/plugin install creview@opensphere-inc
/plugin install cprompt@opensphere-inc
/plugin install cdev@opensphere-inc
/plugin install cgh@opensphere-inc
```

Then exercise `/creview:start`, `/creview:triage`, `/creview:respond`, `/creview:resolve`
in a project that has its own `.claude/agents/` (or none, to test the `general-purpose`
fallback), `/creview:start` with a pull request URL (both with HEAD at the pull request's
head and elsewhere, which reviews in a worktree; needs an authenticated `gh`), the
`/creview:triage` / `respond` / `resolve` on that review document with HEAD elsewhere
(which work in a worktree of the pull request), `/creview:triage` and `/creview:resolve` with
a pull request URL (which compile a review document from its comments; `/creview:triage`
leaves out threads resolved on GitHub and `/creview:resolve` keeps them; needs an
authenticated `gh`), `/cprompt:edit`, and `/cdev:coding` (in a runtime with background
subagents and inter-agent messaging).
Exercise `/cgh:review`, `/cgh:gate`, `/cgh:respond`, and `/cgh:resolve` on a pull request of a
scratch repository: they post to GitHub under your account.

---

## Architecture & Key Concepts

### Marketplace

`.claude-plugin/marketplace.json` (`name: opensphere-inc`) lists four plugins. `creview`,
`cprompt`, `cdev`, and `cgh` use `"source": "./<dir>"` (relative to the repo root). The `src/`
tree is **outside** the plugin source dirs, so it is not shipped with the installed plugins.

### Plugin skills

Plugin skills are namespaced `/<plugin>:<skill>` (`/creview:start`, `/cprompt:edit`). The
skill folder name == the `name:` in SKILL.md frontmatter (bare, not namespaced).

### The creview review pipeline (state lives in the review document)

```
/creview:start   → review doc with <!-- METADATA(id) --> markers (no decisions yet)
                    PR mode (a pull request URL): gh-pr.py fetch (PR + description /
                    CI / conversation) → review in place when HEAD is the PR head, else
                    gh-pr.py checkout into a detached worktree (hooks disabled, agent
                    files such as CLAUDE.md and .claude/ left out unless --trust) → code
                    reviewers + pr-description-reviewer → doc header carries a
                    `- **PR:**` bullet → gh-pr.py remove (hooks disabled); the header
                    also carries a `- **Branch:**` bullet when the review ran on a branch,
                    and in PR mode a `- **Trust:** on|off` bullet (whether the reviewed
                    tree had the agent files)
/creview:triage  → triage Sub + per-assignee estimate Subs → compile → persist
                    triage / estimate metadata into the doc
                    PR mode (a pull request URL, triage and resolve): rules/pr-comment-doc.md:
                    gh-pr.py fetch (every comment, in batches; triage passes --skip-resolved
                    to leave out threads resolved on GitHub) → one pr-comment-compiler Sub
                    per batch writes findings to a .jsonl → compile-pr-comments.py builds
                    the doc, with PR / Branch / Trust bullets and `- **Source:** pr-comments`
                    → the skill runs on that doc; resolve verifies each finding with no
                    metadata against the code
/creview:respond → select-fix-targets Sub reads doc metadata → fix Subs →
                    format&build-verify ⇄ build-fix loop → compile → persist status
/creview:resolve → analyze + verify Subs → compile → persist verification
                    (triage / respond / resolve invoked directly follow
                    rules/doc-worktree.md: gh-pr.py doc-checkout reads the doc's PR /
                    Branch / Trust bullets and, when that code is not checked out here,
                    adds a worktree — a PR worktree with the agent files only when Trust
                    is on; respond passes --fix-branch, so a PR doc with no Branch
                    bullet records the branch its fixes go to: creview-pr-{number}
                    when HEAD lacks the PR head, else the current branch, if any)
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

### The cgh workflow (state lives on the pull request)

cgh skills run creview skills inline with the Skill tool, so a creview skill sees a direct
invocation and handles its own worktree. `/cgh:gate` shapes them through Round-specific
overrides that point at `rules/gate-focus.md`, so creview itself stays unaware of cgh. Every
read and write on GitHub goes through `scripts/gh-review.py`, which also computes the event,
the verdict, and where each finding goes. A bundled `comment-writer` or `reply-drafter`, which
have Read and Write only, summarize recommendations and translate what goes out into the language
of the pull request's description; the preview stays in the user's language. Each posted finding carries a hidden marker
(`<!-- cgh:finding {id} {kind} {location} -->`), a verification carries
`<!-- cgh:verified {ids} -->`, a waiver `<!-- cgh:waived {ids} -->`, and a reply
`<!-- cgh:reply {kind} {id} -->`, read back only from the authenticated user's own comments.
`gh-review.py prior` rebuilds a review document from them, with the IDs kept, for
`/creview:resolve` to verify, and writes the comment targets to `{tmp_dir}/prior.json`, which
`gh-review.py replies` reads. Posted findings number on from the earlier ones, so
an ID stays unique on a pull request.

### Sub-agent launch contract

Leaders pass a launch prompt that tells the sub-agent to `Read` an external
`templates/*.md` (each has a `template_id` UUID in frontmatter) and follow it. The leader
verifies the returned `template_id` against the per-step hard-coded UUID and relaunches on
mismatch. The leader resolves `${CLAUDE_PLUGIN_ROOT}` (plugin context) and passes it into
the launch prompt as the `plugin_root` variable so the template's `{{plugin_root}}/...`
references resolve for the sub-agent. See `creview/rules/sub-agent.md`.

The leader also passes `main_root` in every launch prompt: the main working tree's root
when the run works in a worktree — under `--worktree`, in a `/creview:start` pull
request review that checks the pull request out in one, or in a directly invoked
`/creview:triage` / `respond` / `resolve` whose review document's code is checked out in
one — and `(none)` otherwise.
`/creview:rounds` passes it in every launch prompt it issues; `review-leader` forwards the
value it received, `(none)` included, to every sub-agent it launches; the `/creview:start`
/ `triage` / `respond` / `resolve` leaders pass the value an upper flow gave them, or
`(none)` when invoked directly, except that a leader working in a worktree of its own
passes its own; cdev passes it through the spawn contract. The detection rules
(`agents-detection.md` / `build-format-detection.md`) and `scope-analysis.md` resolve the
project's `.claude/agents/` / `.claude/rules/` against it when it is other than `(none)`,
and against `target_dir` otherwise. Launches nested
inside a template (the challenge / adjudication sub-agents `triage.md` spawns) do not
receive it, so the templates they run must not depend on it.

Every launch prompt — nested launches included — also passes `target_dir`, the work target:
the worktree when the run works in one (under `--worktree`, in a `/creview:start`
worktree review, or in a `/creview:triage` / `respond` / `resolve` worktree), otherwise the
repository root (`git rev-parse --show-toplevel`). Every
creview and cdev entry point rejects a session started in a subdirectory of the repository
(non-empty `git rev-parse --show-prefix`) with an error, with or without `--worktree`, so
every sub-agent's current working directory is
`target_dir`, the single base for relative paths, for where commands run, and for the
write scope. The write-scope bullet in `rules/sub-agent.md` / `rules/teammate.md` confines
every sub-agent's writes to `{{target_dir}}`, its working directory (`tmp_dir`), and the
output paths it is given, judged by prefix with no `..`, where `\` and `/` count as the
same separator and a drive letter's case is ignored; paths in a task are passed as given,
never re-rooted by a leader.

The launches of cgh's `reply-drafter` and `comment-writer` are the exception: they pass only
the variables their templates name, as absolute paths, with no `plugin_root`, `main_root`,
`target_dir`, or Round-specific overrides, since those templates read no bundled rule and the
agents have Read and Write only. A cgh launch that goes beyond that passes all three.

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
   `plugin_root`, `main_root`, and `target_dir` in every launch prompt (cgh's `reply-drafter`
   and `comment-writer` excepted; see Sub-agent launch contract) — `main_root` is the
   main working tree's root under `--worktree` or the value an upper flow passed, and
   `(none)` otherwise; `target_dir` is the work target (see Sub-agent launch contract).
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
- Manually install all four plugins and exercise each command (see install smoke test).

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
  put `{{plugin_root}}` in a SKILL. (`agents/review-helper.md` / `agents/review-leader.md` /
  `agents/pr-description-reviewer.md` / `agents/pr-comment-compiler.md` mention
  `{{plugin_root}}` only to name that template variable.)
  `rules/sub-agent.md`, `rules/teammate.md`, and the detection rules carry
  `{{target_dir}}` on the same basis: every launch passes `target_dir`.
  `rules/wontfix.md` carries `{{previous_round_doc_paths}}` on the same basis: every
  template that references it receives that launch variable.
  `rules/pr-comment-doc.md` is opened with Read by the `/creview:triage` / `resolve` leaders in
  PR mode, on the same basis as the next rule.
  `rules/doc-worktree.md` is opened with Read by the `/creview:triage` / `respond` /
  `resolve` leaders, so it uses `{{plugin_root}}` as well, and those SKILLs name its
  `plugin_root` variable without writing the `{{...}}` token.
  `cgh/rules/leader.md` is opened with Read by the `/cgh:*` leaders on the same basis, and
  their SKILLs name its `plugin_root` variable the same way.
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
- **`scripts/lib/scratch-guard.py` and `scripts/del-tmp.sh` are byte-identical across all six
  copies** (`creview/`, `cdev/`, `cgh/`, and their `src/` mirrors), and `scripts/check-jsonl.py`
  across all four (`creview/`, `cdev/`, and their mirrors); each plugin ships its own copy
  because plugins install independently. Edit one copy and replicate to the others;
  `tests/scratch-guard-test.sh` fails on any drift. `scripts/worktree.sh` is likewise
  byte-identical across all six copies (`creview/`, `cdev/`, `cprompt/`, and their `src/`
  mirrors). `scripts/fetch-diff.sh` (in `creview/` and `cdev/`), `creview/scripts/gh-pr.py`, and
  `creview/scripts/compile-pr-comments.py`, and `cgh/scripts/gh-review.py` are likewise each
  byte-identical with its own `src/` mirror.
- **A sub-agent's Write is rejected when the `.md` basename starts with `REPORT`,
  `SUMMARY`, `FINDINGS`, or `ANALYSIS`** (case-insensitive, basename only). Claude Code's
  Write tool blocks it and tells the sub-agent to return the content as text instead. Output
  paths whose basename comes from a runtime value therefore carry a fixed prefix — creview's
  `{tmp_dir}/reviews/{scope_id}/review-{reviewer-name}.md` (the aggregator recovers the
  reviewer name by stripping it; the `:` of a namespaced agent name is written as `__`,
  since a Windows file name cannot hold `:`) and cdev's `{design_dir}/design-{slug}.md`. Keep those
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
