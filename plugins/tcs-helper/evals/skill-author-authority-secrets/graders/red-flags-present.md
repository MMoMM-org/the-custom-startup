---
type: llm
focus: {source: file, path: skills/commit-secrets/SKILL.md}
weight: 1
---
This is a skill file. The rules it enforces:

(a) Never commit an API key, token, password or private key, test keys included.
(b) Read values from environment variables and commit only a `.env.example` with placeholder values.
(c) Run `git diff --staged` and read it before every commit.

PASS if the file has a Red Flags list (thoughts or excuses that signal the agent is about to break a
rule) or an excuse-to-reality table, and every rule above is addressed by at least one of its entries.

FAIL if there is no such list or table, or if a rule above has no entry in it. Judge only the list or
table; the wording of the rules elsewhere does not matter.
