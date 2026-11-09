---
type: llm
focus: {source: file, path: skills/release-changelog/SKILL.md}
weight: 1
---
This is a skill file. The rules it enforces:

(a) Add a `CHANGELOG.md` entry for every release, patch releases included.
(b) Write the entry in the same pull request as the version bump.
(c) List breaking changes first, under a `Breaking` heading.

PASS if the file has a Red Flags list (thoughts or excuses that signal the agent is about to break a
rule) or an excuse-to-reality table, and every rule above is addressed by at least one of its entries.

FAIL if there is no such list or table, or if a rule above has no entry in it. Judge only the list or
table; the wording of the rules elsewhere does not matter.
