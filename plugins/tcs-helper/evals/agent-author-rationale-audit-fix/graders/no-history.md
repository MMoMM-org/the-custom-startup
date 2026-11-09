---
type: regex
target: {source: file, path: agents/log-triage.md}
match: not_contains
flags: i
pattern: '\b\d{4}-\d{2}-\d{2}\b|\b(?=[0-9a-f]*\d)(?=[0-9a-f]*[a-f])[0-9a-f]{7,40}\b|previously'
weight: 1
---
The agent file contains no ISO date, no commit SHA (7-40 hex characters with at least one digit and
one letter) and no "previously": history belongs in git, not in the instruction.
