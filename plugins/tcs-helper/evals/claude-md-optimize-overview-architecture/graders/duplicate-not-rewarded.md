---
type: llm
focus: {source: file, path: claude-md-optimization/OPTIMIZATION-REPORT.md}
weight: 1
---
This is an optimization report for a repository's `CLAUDE.md`. That `CLAUDE.md` repeats the architecture overview (the three modules, what each does, and the data flow)
from the repository's `README.md` and code, which already give it in full.

PASS only if both hold:

(a) The quality score does not reward the repeated content: no criterion score is credited for it
(for example, architecture, commands or actionability points earned by the copied overview, tree,
stack list or setup steps), and the report either names it as duplicating the README or code or
leaves it out of what earned points.

(b) The report proposes removing the repeated content from `CLAUDE.md` outright, at most leaving a
pointer to the README. Moving it into a memory category file, or keeping it, is not removing it.

FAIL if a criterion score cites the repeated content as a strength, or if the report keeps it or
relocates it instead of removing it.
