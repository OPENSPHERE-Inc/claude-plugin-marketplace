# AGENTS.md — opensphere-inc Claude Code Plugin Marketplace

For detailed project documentation, architecture, localization workflow, and guidelines,
see **[CLAUDE.md](CLAUDE.md)**.

## Quick Reference

- **Content**: Markdown (AI-facing prompts), Bash, Python ≥ 3.9 (helper scripts)
- **Distribution**: Claude Code plugin marketplace (git-based), `name: opensphere-inc`
- **Plugins**: `creview` (code review workflow), `cprompt` (prompt authoring), `cdev`
  (team-native coding workflow)
- **License**: MIT
- **Maintainer**: OPENSPHERE Inc.
- **No build step. No CI yet.** Validation = consistency checks +
  `bash tests/scratch-guard-test.sh` + manual install.

## Key Files

- `.claude-plugin/marketplace.json` — Marketplace listing (creview, cprompt, cdev).
- `{creview,cprompt,cdev}/.claude-plugin/plugin.json` — Plugin manifests (each carries its
  own semver).
- `creview/skills/{start,triage,respond,resolve,rounds}/SKILL.md` — The 5 creview skills.
- `creview/skills/*/templates/*.md` — Sub-agent prompt templates (each has a `template_id`).
- `creview/agents/` — bundled mechanical agents: `review-helper.md`,
  `comment-sensei.md`, `review-leader.md` (the `/creview:rounds` phase leader).
- `creview/rules/` — `comment.md`, `document.md`, `review.md`, `wontfix.md`, `sub-agent.md`,
  `adr-format.md`, `agents-detection.md`, `build-format-detection.md` (rules referenced by
  skills).
- `creview/scripts/` — `fetch-diff.sh`, `render-review.py`, `del-tmp.sh`, `check-jsonl.py`,
  `lib/scratch-guard.py`.
- `creview/skills/{triage,respond,resolve}/scripts/compile-review.py` — per-skill leader-run compile (aggregates intermediate JSON → `events.jsonl` → `render-review.py`).
- `cprompt/skills/edit/SKILL.md` (+ `templates/`) — The `/cprompt:edit` skill.
- `cprompt/rules/` — `prompt.md`, `document.md`.
- `cdev/skills/coding/SKILL.md` (+ `templates/`) — The `/cdev:coding` team-native skill (7 teammate task templates, each with a `template_id`).
- `cdev/agents/` — `comment-sensei.md`, `dev-helper.md` (bundled). `cdev/rules/` — `teammate.md`, `agents-detection.md`, `build-format-detection.md`, `comment.md`, `review.md`, `document.md`, `divergence.md`. `cdev/scripts/` — `fetch-diff.sh`, `del-tmp.sh`, `check-jsonl.py`, `lib/scratch-guard.py`.
- `src/<plugin>/...` — **Japanese master**, mirrors each plugin's tree 1:1 (minus
  `.claude-plugin/` and the READMEs).
- `tests/scratch-guard-test.sh` — repo-level self-test: containment + byte-parity of the
  shared `lib/scratch-guard.py` / `del-tmp.sh` / `check-jsonl.py` copies (not shipped).
- `README.md` / `README_ja.md` (top + per-plugin) — cross-linked EN / JA docs.
- `.claude/rules/*.md` — Discipline rules for editing this repo (prompt/document/comment/…).

## Essential Rules

1. **Language policy is not "English only".** Active plugin files = English;
   `src/**` = Japanese master; `*_ja.md` = Japanese. Top-level docs = English.
2. **`src/` is the editing master.** Edit `src/<plugin>/X` and active `<plugin>/X` as a
   translation-paired change; keep them structurally 1:1. Exception:
   `scripts/lib/scratch-guard.py` / `scripts/del-tmp.sh` / `scripts/check-jsonl.py` are
   byte-identical across all four copies (`creview/`, `cdev/`, and their `src/` mirrors) —
   the `src/` copies stay English; see CLAUDE.md.
3. **Token-placement invariant.** `${CLAUDE_PLUGIN_ROOT}` only in files Claude Code loads
   itself (SKILL.md bodies/`allowed-tools`, bundled `agents/*.md`); `{{plugin_root}}` only
   in files a sub-agent opens with Read (`templates/*.md` and the bundled `rules/*.md` it is
   pointed to), passed as a launch variable. Never cross them.
4. **`template_id` must match** the per-step UUID hard-coded in the SKILL that launches it.
5. **No bundled specialist reviewers.** Skills resolve reviewers/fixers from the
   destination project's `.claude/agents/`, falling back to `general-purpose`. Only
   the mechanical helpers are bundled (`creview`: `review-helper`, `comment-sensei`,
   `review-leader`; `cdev`: `dev-helper`, `comment-sensei`).
6. **review-respond split**: `/creview:triage` persists `triage`+`estimate` into the
   review doc; `/creview:respond` reads them back from the doc. The split is the review
   gate — no `--no-confirm`. The handoff is the document, not a shared temp dir.
7. **Preserve verbatim** across translation/transformation: `{{...}}` placeholders,
   `${CLAUDE_PLUGIN_ROOT}`, `.claude/...` paths, `template_id` UUIDs, `allowed-tools`,
   JSON field names, emoji, skill names, severity labels, Markdown structure.
8. **`src/` is not shipped** — it sits outside plugin `source` dirs; never reference it
   from active skills.
9. **Keep README EN ↔ JA in sync**, including the H1 cross-link line.
10. **CRLF** in skill/template files is inherited from upstream; avoid global reflow churn.
11. **Agent frontmatter uses `tools:`**, not `allowed-tools:` (that key is for skills /
    commands and is ignored in `agents/*.md`, leaving the agent unrestricted).

For architecture, the localization workflow, common tasks, and warnings, refer to
**[CLAUDE.md](CLAUDE.md)**.
