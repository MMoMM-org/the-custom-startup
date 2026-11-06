---
type: llm
focus: {source: file, path: skills/db-migrations/SKILL.md}
weight: 1
---
This is a skill file. The rules it enforces:

(a) Run database migrations only through `./scripts/migrate`, never by calling `alembic` directly.
(b) Run `./scripts/migrate --dry-run` and read the planned SQL before the real run.

PASS if the file has a Red Flags list (thoughts or excuses that signal the agent is about to break a
rule) or an excuse-to-reality table, and every rule above is addressed by at least one of its entries.

FAIL if there is no such list or table, or if a rule above has no entry in it. Judge only the list or
table; the wording of the rules elsewhere does not matter.
