---
type: regex
target: {source: file, path: skills/deploy-checklist/SKILL.md}
match: not_contains
flags: i
pattern: '\b\d{4}-\d{2}-\d{2}\b|\b(?=[0-9a-f]*\d)(?=[0-9a-f]*[a-f])[0-9a-f]{7,40}\b|previously'
weight: 1
---
The skill file contains no ISO date, no commit SHA (7-40 hex characters with at least one digit and
one letter) and no "previously": the brief's history belongs in git, not in the instruction.
