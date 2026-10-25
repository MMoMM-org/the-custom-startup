---
type: llm
focus: last_message
weight: 2
---
PASS if the report has a breaking-change section (or equivalent heading) before any severity
table or severity-grouped findings, and it identifies renaming the public function `total` to
`order_total` without keeping the old name as breaking for code that installed tinyprice from
PyPI, with a migration (for example: keep `total` as a deprecated alias, or release a major version).
FAIL if the rename is not called breaking, if it appears only as one row among other findings, or
if no migration is given.
