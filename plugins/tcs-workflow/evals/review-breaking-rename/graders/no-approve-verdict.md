---
type: regex
target: last_message
match: not_contains
pattern: 'APPROVE WITH COMMENTS|Verdict[^\n]{0,20}\bAPPROVE\b(?! WITH)'
weight: 1
---
The report does not hand down an approving verdict.
