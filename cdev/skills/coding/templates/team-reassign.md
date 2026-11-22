---
name: team-reassign
description: Prompt for the team re-formation task (dev-helper) in cdev /coding Step 2, which assigns each file the closed design adds or changes to a coder or a writer under the team-analysis assignment rules, adding coders / writers / reviewers when no existing one fits
template_id: 6dd623b7-91fb-45a7-acf4-cf08646878aa
---

Re-form the coders and writers of the team so that each file the design sections add or change lies in the scope of exactly one producer (a coder or a writer) and each producer is paired with a reviewer of its domain, and write the resulting coders / writers / reviewers to `{{output_path}}`. Do not implement anything.

Design sections: Read every file in `{{design_paths}}`.
Roster: `{{roster_path}}` (the team-analysis result)
Names taken in this session: `{{taken_names}}`
Team tag: `{{team_tag}}`

Read `{{plugin_root}}/skills/coding/templates/team-analysis.md` and apply its Assignment rules; do not perform that template's own task. Build the agent pool per `{{plugin_root}}/rules/agents-detection.md` § Enumeration.

Constraints:

- Keep every coder, writer, and reviewer of the roster with its `name`, `slug`, and `reviewer` unchanged.
- A scope holds a file when it names the file or a directory above it. The documentation files (per `{{plugin_root}}/rules/teammate.md` § Documentation files) are the files the design sections list as documentation.
- Each documentation file the design sections add or change ends up in the scope of exactly one writer, one whose paired reviewer's domain covers it, and in no coder's scope.
- Each other file the design sections add or change ends up in the scope of exactly one coder, one that meets all three of the following, and in no other coder's scope and no writer's:
  - the Assignment rules let that coder hold it: a prompt file only to a coder whose scope holds no other source, any other file only to a coder whose scope holds no prompt file;
  - the file falls in the domain of that coder's paired reviewer, a test the design adds for a file that is neither an AI-facing prompt file nor a documentation file counting as in the domain of the file it tests, and a test for an AI-facing prompt file or a documentation file as in its own domain;
  - when the file is a test the design adds for another file that is neither an AI-facing prompt file nor a documentation file, and a coder whose scope holds no prompt file holds that other file after this re-formation, the coder is the one that holds that other file. A test for an AI-facing prompt file or a documentation file goes, like any other file that is not a prompt file, to a coder whose scope holds no prompt file.
- Leave a file with a producer whose scope holds it when that producer meets the conditions above for it; otherwise take it out of any scope that holds it and give it to an existing producer that meets them, or to a new coder or writer when none does.
- Give each new member a kebab-case `slug` such that its role name (`coder-{slug}` / `writer-{slug}` / `reviewer-{slug}`, with `-{{team_tag}}` appended unless `{{team_tag}}` is `(none)`) is neither in `{{taken_names}}` nor the role name of another entry in the output.
- Assign only paths under `{{target_dir}}`.
- Write `scope` / `reason` / `rationale` in {{doc_lang}}; keep `name` / `slug` as-is.

`{{output_path}}` format, listing all coders, writers, and reviewers, the roster's included; each field means what it means in the roster's `coders` / `writers` / `reviewers`:

```
{"coders": [{"name": <string>, "slug": <string>, "scope": <string>, "reviewer": <string>, "reason": <string>}], "writers": [{"name": <string>, "slug": <string>, "scope": <string>, "reviewer": <string>, "reason": <string>}], "reviewers": [{"name": <string>, "slug": <string>, "reason": <string>}], "rationale": <string>}
```

Record a new reviewer's `name` as agents-detection.md § Result specifies.

Report completion to the leader (SendMessage with `to: "main"`) as one line naming `{{output_path}}`, the numbers of coders, of writers, and of reviewers added, and the numbers of roster coders and of roster writers whose scope changed.
