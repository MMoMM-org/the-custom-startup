---
type: regex
target: {source: file, path: skills/file-deletion/SKILL.md}
match: not_contains
flags: i
pattern: 'YOU MUST|No exceptions'
weight: 1
---
The skill file contains neither "YOU MUST" nor "No exceptions", in any case: current models follow
plain rules, and emphasis makes them over-apply the rule (PA-03).
