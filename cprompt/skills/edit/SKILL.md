---
name: edit
description: Create and edit AI-facing prompts (agent / skill / rule / command, etc.) and self-check / fix them against prompt.md rules. Use proactively whenever a task involves writing or modifying an agent definition, SKILL.md, rule, slash command, or sub-agent prompt, even if the user does not name this skill.
allowed-tools: Agent, Read, Write, Edit, Glob, Grep, Bash(ls:*), Bash(mkdir:*), Bash(find:*)
---

# Prompt Editor

Create or edit an AI-facing prompt (markdown). The finished prompt satisfies `${CLAUDE_PLUGIN_ROOT}/rules/prompt.md`, carries no verbosity, and is still interpreted as intended after compression: produce it, self-check and fix it, compress it, then verify it by test.

Human-facing documentation (README, API references, design docs, etc.) is out of scope. That is governed by `${CLAUDE_PLUGIN_ROOT}/rules/document.md`.

## Input

The user specifies one of:

- New: kind (agent / skill / rule / command / prompt) + target path + requirements
- Edit: path to an existing file + edit requirements

If the argument is `$ARGUMENTS`, interpret it as the above. If the kind is not explicitly given, infer it from the target path:

- `.claude/agents/{name}.md` → agent
- `.claude/skills/{name}/SKILL.md` → skill
- `.claude/rules/{name}.md` → rule
- `.claude/commands/{name}.md` → command
- Anything else (e.g. a sub-agent prompt body extracted from a skill) → prompt

## Output rules

These hold for whatever this skill produces or edits.

### Sub-agent prompts embedded in a code block

When a prompt is to be passed to the Agent tool and you embed it inside a triple-backtick code block in the body, write it as plain text:

- Do not use headings (`#` / `##`, etc.), tables, or emphasis (`**` / `*` / `__`).
- Bullet lists (`-` or `1.`) for genuine enumerations and code / JSON snippets are allowed.
- Use `{...}` for placeholders (variables filled by the caller).

### Markdown output templates are externalized

When the prompt being edited contains a "markdown output template" (a skeleton of the produced markdown), do not embed it in a code block in the body. Split it out to an external file and reference it (avoids markdown-in-markdown):

- Location: `templates/{name}.md` under the relevant skill.
- In the body, leave only a path reference of the form: `Template: .claude/skills/{skill-name}/templates/{name}.md ({consumer} reads it to learn the skeleton).`

Exceptions (embedding in a code block is allowed):

- Input format examples (descriptions of documents / data formats the prompt being edited consumes).
- Examples in non-markdown formats such as JSONL / JSON / command lines.

## Step 1 — Produce the output

New: Read the template for the kind, `${CLAUDE_PLUGIN_ROOT}/skills/edit/templates/{kind}.md`, and fill in its placeholders (`{...}`) from the requirements — sections the requirements do not address may be removed, and sections the requirements call for may be added. Write the result at the target path, creating its directory with `mkdir -p` when missing.

Edit: Read the target path and edit it to the requirements.

## Step 2 — Self-check and fix

Goal: the output violates no item of `${CLAUDE_PLUGIN_ROOT}/rules/prompt.md`.

1. Read that rule and the file from Step 1, and list every violation as `path:line`. Cover the plain-text rule inside any sub-agent prompt code block, and any output template embedded in a triple-backtick block with the `markdown` language tag (input-format examples and non-markdown formats are excluded) — externalize that template and replace it with a path reference.
2. Fix the violations with Edit, then re-check that the fixes introduced no new ones. Repeat up to 2 times. If violations remain after the second pass, present the remaining list to the user and ask for judgment.

## Step 3 — Compress

Reduce verbosity in the file from Step 1, including any sub-agent prompt embedded in its code blocks; the output rules still apply. Apply Edit to remove the following:

- Polite forms such as "please ..." → use the imperative.
- The same rule repeated in multiple places → consolidate or replace with a reference.
- Statements the AI would naturally infer (e.g., per-edge-case instructions for self-evident cases) → remove.
- "A is the case, therefore not B" wording (the `x == a && x != b` pattern) → keep only the first half.
- Unnecessarily verbose code examples or templates → trim to the minimum skeleton.

Decision criterion: if removing the text does not change the action the AI should take, remove it. Keep judgment WHY (constraints, premises, anti-misunderstanding notes).

## Step 4 — Test

Have a sub-agent read the file produced in Step 1 and verify whether it is interpreted without missing or misleading information (in particular, whether Step 3's compression damaged any meaning).

1. Build a checklist. Each item is a question of the form "what should an agent reading this prompt do in situation X?" (examples: how to determine the kind when the input does not specify it, the fallback when step X fails, the input/output flow between steps, the threshold for each branch). Cover the input spec, each step, each branch condition, and the output spec.
2. Launch the test sub-agent via the Agent tool. Prompt:

```
Prompt-interpretation tester. Read {prompt_path} and answer each checklist item below in 1-2 sentences, using only what is readable from that prompt — no external knowledge, no guessing. Report an item as unclear with a one-sentence reason when the prompt leaves it unanswerable, ambiguous, or contradictory. Do not propose fixes or edit anything.

Checklist:
1. {item 1}
2. {item 2}
...

Return value: {pass, unclear_items: [{item, reason}]} (pass: true if unclear_items is an empty array)
```

3. If the return value is `pass: true`, finish.
4. If `unclear_items` are present, fix the places they name with Edit and rerun this step. Repeat up to 3 times. If unclear items remain after the third pass, present the remaining list to the user and ask for judgment.

## Step 5 — Report

Report the target path, the number of violations detected/fixed, whether compression occurred, and the test result (pass or remaining unclear items).
