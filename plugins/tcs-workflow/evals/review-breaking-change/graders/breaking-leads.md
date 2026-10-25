---
type: llm
focus: last_message
weight: 2
---
PASS if the report has a breaking-change section (or equivalent heading) that comes before any
severity table or severity-grouped findings, and it identifies removing the `currency` parameter
from `total()` as breaking for code that installed tinyprice from PyPI, with a migration (for
example: keep `currency` with a default, deprecate first, or release a major version).
FAIL if the removed parameter is not called breaking, if it appears only as one row among other
findings, or if no migration is given.
