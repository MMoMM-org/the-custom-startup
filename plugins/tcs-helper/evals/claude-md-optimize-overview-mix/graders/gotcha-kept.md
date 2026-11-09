---
type: llm
focus: {source: file, path: claude-md-optimization/OPTIMIZATION-REPORT.md}
weight: 1
---
This is an optimization report for a repository's `CLAUDE.md`. Among content copied from the README,
that `CLAUDE.md` has one rule the README and the code do not contain: the nightly report job in the
`ops-reports` repository reads `tally.db`, so the `totals` table schema may change only together
with that job.

PASS if the report keeps that rule, either in the proposed `CLAUDE.md` or in a proposed memory
category file, and does not propose deleting it.

FAIL if the report proposes deleting that rule, or the rule appears nowhere in the report's kept or
migrated content.
