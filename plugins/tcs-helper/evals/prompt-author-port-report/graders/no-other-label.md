---
type: regex
target: {source: file, path: port/report.md}
match: not_contains
flags: i
pattern: '(?<!(not|never|been|be|is|was|yet) )evaluated on (?!(the )?target)'
weight: 1
---
The report carries no second delivery label: no "evaluated on <target>" and no "proxy: evaluated on
<model>", since no model was run. A sentence saying the port was not, or has not been, evaluated on a
model does not count as a label.
