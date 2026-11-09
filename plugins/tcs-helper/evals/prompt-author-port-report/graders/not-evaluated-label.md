---
type: regex
target: {source: file, path: port/report.md}
flags: i
pattern: 'not evaluated on (the )?target'
weight: 1
---
The report carries the "not evaluated on target" label: the case runs no target model, so this is the
only label a correct port can carry.
