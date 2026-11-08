---
type: regex
target: {source: file, path: audit/findings.md}
flags: i
pattern: '^(?=[\s\S]*\n\|[^\n]*fix[^\n]*\|)(?=[\s\S]*\n(?=\|(?:[^|\n]*\|){6})(?=[^\n]*\|[ \t*]*(blocking|major|minor)[ \t*]*\|)(?=[^\n]*[\w./-]+\.\w+:\d+)(?=[^\n]*(PA-\d{2}|uncatalogued)))(?![\s\S]*\n(?:(?=\|(?:[^|\n]*\|){6})(?=[^\n]*\|[ \t*]*(blocking|major|minor)[ \t*]*\|)(?:(?![^\n]*[\w./-]+\.\w+:\d+)|(?![^\n]*(PA-\d{2}|uncatalogued))|(?=[^\n]*\|[ \t]*\|[ \t]*(?:\n|$)))|(?=\|(?:[^|\n]*\|){6})(?![^\n]*\|[ \t*]*(blocking|major|minor)[ \t*]*\|)(?=[^\n]*[\w./-]+\.\w+:\d+)(?=[^\n]*(PA-\d{2}|uncatalogued))))'
weight: 1
---
Every finding row carries the four parts of the finding format (PRD F3 AC1). The report has a table
whose header names a fix column, and at least one finding row. A finding row is a table row of five or
more columns with a severity cell of `blocking`, `major` or `minor`. Every such row has a
`path:line` location, an entry (`PA-NN` or `uncatalogued`), and a non-empty last cell (the fix).
No row of five or more columns has a location and an entry but a severity outside that set. Column
order, bold severities, link-wrapped entries and line ranges (`path:12-14`) all pass. One entry per
row is checked only as "at least one": a row that mentions a second ID in its problem text still
passes.
