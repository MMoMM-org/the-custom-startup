---
type: regex
target: trace
match: not_contains
weight: 2
pattern: 'slug\.py[^}]{0,60}content[^}]*\.lower\('
---
No working implementation of slugify is written to src/slug.py. A stub that only raises is allowed: it makes the tests fail on behaviour rather than on a missing import.
