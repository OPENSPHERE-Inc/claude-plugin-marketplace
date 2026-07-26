# AGENTS.md — opensphere-inc Claude Code Plugin Marketplace

For detailed project documentation, architecture, localization workflow, and guidelines,
see **[CLAUDE.md](CLAUDE.md)**.

## Quick Reference

- **Content**: Markdown (AI-facing prompts), Bash, Python ≥ 3.11 (one sequencer program)
- **Distribution**: Claude Code plugin marketplace (git-based), `name: opensphere-inc`
- **Plugins**: `creview` (code review workflow), `cprompt` (prompt authoring), `cdev`
  (team-native coding workflow); external `agent-sequencer` referenced for `creview`'s sequencer program
- **License**: MIT
- **Maintainer**: OPENSPHERE Inc.
- **No build step. No CI yet.** Validation = consistency checks +
  `bash tests/scratch-guard-test.sh` + manual install.

## Key Files

- `.claude-plugin/marketplace.json` — Marketplace listing (creview, cprompt, external agent-sequencer).
- `creview/.claude-plugin/plugin.json` / `cprompt/.claude-plugin/plugin.json` — Plugin manifests.
- `creview/skills/{start,triage,respond,resolve,rounds}/SKILL.md` — The 5 creview skills.
- `creview/skills/*/templates/*.md` — Sub-agent prompt templates (each has a `template_id`).
- `creview/agents/` — bundled mechanical agents: `review-helper.md`,
  `comment-sensei.md`, `review-leader.md` (the `/creview:rounds` phase leader).
- `creview/rules/` — comment / document / review / sub-agent rules referenced by skills.
- `creview/scripts/` — `fetch-diff.sh`, `render-review.py`, `rm-tmp.sh`, `lib/scratch-guard.py`.
- `creview/skills/{triage,respond,resolve}/scripts/compile-review.py` — per-skill leader-run compile (aggregates intermediate JSON → `events.jsonl` → `render-review.py`).
- `creview/sequencer/programs/review_rounds.py` (+ `review_rounds/`) — agent-sequencer program (English).
- `cprompt/skills/edit/SKILL.md` (+ `templates/`) — The `/cprompt:edit` skill.
- `cprompt/rules/` — `prompt.md`, `document.md`.
- `cdev/skills/coding/SKILL.md` (+ `templates/`) — The `/cdev:coding` team-native skill (7 teammate task templates, each with a `template_id`).
- `cdev/agents/` — `comment-sensei.md`, `dev-helper.md` (bundled). `cdev/rules/` — `teammate.md`, `agents-detection.md`, `build-format-detection.md`, `comment.md`, `review.md`, `document.md`. `cdev/scripts/` — `fetch-diff.sh`, `rm-tmp.sh`, `lib/scratch-guard.py`.
- `src/<plugin>/...` — **Japanese master**, mirrors each plugin's tree 1:1.
- `tests/scratch-guard-test.sh` — repo-level self-test: containment + byte-parity of the
  shared `lib/scratch-guard.py` / `rm-tmp.sh` copies (not shipped).
- `README.md` / `README_ja.md` (top + per-plugin) — cross-linked EN / JA docs.
- `.claude/rules/*.md` — Discipline rules for editing this repo (prompt/document/comment/…).

## Essential Rules

1. **Language policy is not "English only".** Active plugin files = English;
   `src/**` = Japanese master; `*_ja.md` = Japanese. Top-level docs = English.
2. **`src/` is the editing master.** Edit `src/<plugin>/X` and active `<plugin>/X` as a
   translation-paired change; keep them structurally 1:1. Exception:
   `scripts/lib/scratch-guard.py` / `scripts/rm-tmp.sh` are byte-identical across all four
   copies (`creview/`, `cdev/`, and their `src/` mirrors) — the `src/` copies stay English;
   see CLAUDE.md.
3. **Token-placement invariant.** `${CLAUDE_PLUGIN_ROOT}` only in SKILL.md
   bodies/`allowed-tools`; `{{plugin_root}}` only inside `templates/*.md` (passed as a
   launch variable). Never cross them.
4. **`template_id` must match** the per-step UUID hard-coded in the SKILL that launches it.
5. **No bundled specialist reviewers.** Skills resolve reviewers/fixers from the
   destination project's `.claude/agents/`, falling back to `general-purpose`. Only
   the mechanical helpers (`review-helper`, `comment-sensei`, `review-leader`) are
   bundled.
6. **review-respond split**: `/creview:triage` persists `triage`+`estimate` into the
   review doc; `/creview:respond` reads them back from the doc. The split is the review
   gate — no `--no-confirm`. The handoff is the document, not a shared temp dir.
7. **Preserve verbatim** across translation/transformation: `{{...}}` placeholders,
   `${CLAUDE_PLUGIN_ROOT}`, `.claude/...` paths, `template_id` UUIDs, `allowed-tools`,
   JSON field names, emoji, skill names, severity labels, Markdown structure.
8. **`review_rounds.py`** (English active + Japanese `src/`) must both pass `ast.parse`;
   keep skill-name constants, UUIDs, schemas, and control flow identical between them.
9. **`src/` is not shipped** — it sits outside plugin `source` dirs; never reference it
   from active skills.
10. **Keep README EN ↔ JA in sync**, including the H1 cross-link line.
11. **CRLF** in skill/template files is inherited from upstream; avoid global reflow churn.
12. **Agent frontmatter uses `tools:`**, not `allowed-tools:` (that key is for skills /
    commands and is ignored in `agents/*.md`, leaving the agent unrestricted).

For architecture, the localization workflow, common tasks, and warnings, refer to
**[CLAUDE.md](CLAUDE.md)**.
