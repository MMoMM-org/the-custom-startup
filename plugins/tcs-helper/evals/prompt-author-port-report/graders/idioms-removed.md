---
type: regex
target: {source: file, path: port/review-helper.md}
match: not_contains
flags: i
pattern: 'AskUserQuestion|Claude project'
weight: 1
---
The port no longer names the AskUserQuestion tool or a Claude project, two source-environment idioms
a local chat model cannot act on (PA-40). Defining either inside the port would make no sense to the
target, so a correct port removes or rewrites both.
