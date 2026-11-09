---
name: team-reassign
description: Prompt for the team re-formation task (dev-helper) in cdev /coding Step 2, which assigns each file the closed design adds or changes to a coder under the team-analysis assignment rules, adding coders / reviewers when no existing one fits
template_id: 6dd623b7-91fb-45a7-acf4-cf08646878aa
---

Re-form the coders of the team so that each file the design sections add or change lies in the scope of exactly one coder and each coder is paired with a reviewer of its domain, and write the resulting coders / reviewers to `{{output_path}}`. Do not implement anything.

Design sections: Read every file in `{{design_paths}}`.
Roster: `{{roster_path}}` (the team-analysis result)
Names taken in this session: `{{taken_names}}`

Read `{{plugin_root}}/skills/coding/templates/team-analysis.md` and apply its Assignment rules; do not perform that template's own task. Build the agent pool per `{{plugin_root}}/rules/agents-detection.md` § Enumeration.

Constraints:

- Keep every coder and reviewer of the roster with its `name`, `slug`, and `reviewer` unchanged.
- Each file the design sections add or change ends up in the scope of exactly one coder, one that meets all three of the following, and in no other coder's scope (a scope holds a file when it names the file or a directory above it):
  - the Assignment rules let that coder hold it: a prompt file only to a coder whose scope holds no other source, any other file only to a coder whose scope holds no prompt file;
  - the file falls in the domain of that coder's paired reviewer, a test the design adds for a file that is not an AI-facing prompt file counting as in the domain of the file it tests, and a test for an AI-facing prompt file as in its own domain;
  - when the file is a test the design adds for another file that is not an AI-facing prompt file, and a coder whose scope holds no prompt file holds that other file after this re-formation, the coder is the one that holds that other file. A test for an AI-facing prompt file goes, like any other file that is not a prompt file, to a coder whose scope holds no prompt file.
- Leave a file with a coder whose scope holds it when that coder meets all three; otherwise take it out of any scope that holds it and give it to an existing coder that meets all three, or to a new coder when none does.
- Give each new member a kebab-case `slug` such that its role name (`coder-{slug}` / `reviewer-{slug}`) is neither in `{{taken_names}}` nor the role name of another entry in the output.
- Assign only paths under `{{target_dir}}`.
- Write `scope` / `reason` / `rationale` in {{doc_lang}}; keep `name` / `slug` as-is.

`{{output_path}}` format, listing all coders and reviewers, the roster's included; each field means what it means in the roster's `coders` / `reviewers`:

```
{"coders": [{"name": <string>, "slug": <string>, "scope": <string>, "reviewer": <string>, "reason": <string>}], "reviewers": [{"name": <string>, "slug": <string>, "reason": <string>}], "rationale": <string>}
```

Record a new reviewer's `name` as agents-detection.md § Result specifies.

Report completion to the leader (SendMessage with `to: "main"`) as one line naming `{{output_path}}`, the number of coders and of reviewers added, and the number of roster coders whose scope changed.
