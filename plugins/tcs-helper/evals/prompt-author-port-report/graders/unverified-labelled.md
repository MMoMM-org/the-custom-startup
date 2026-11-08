---
type: regex
target: {source: file, path: port/report.md}
flags: i
pattern: '\bunverified\b'
weight: 1
---
The report labels at least one change unverified. The small-local profile grades every topic except
Turn shape and Gate exits unverified, and this source triggers several of them (Emphasis for the
capitalised IMPORTANT and ALWAYS, Delimiters for the undelimited diff), so a port that applies the
profile reports at least one unverified change.
