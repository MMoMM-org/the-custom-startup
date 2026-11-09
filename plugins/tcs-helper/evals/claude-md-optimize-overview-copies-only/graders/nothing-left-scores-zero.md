---
type: llm
focus: {source: file, path: claude-md-optimization/OPTIMIZATION-REPORT.md}
weight: 1
---
This is an optimization report for a repository's `CLAUDE.md`. Every line of that `CLAUDE.md`
repeats content the repository's `README.md` already gives: the architecture overview, the project
layout, the tech stack and the setup steps. It has no rule, gotcha or fact of its own, so once the
copies are set aside nothing remains to score.

PASS only if, in the report's quality scores for `CLAUDE.md`, the Currency criterion scores 0 and
the Actionability criterion scores 0, or the report states that nothing remains to score on those
criteria once the copied content is set aside and gives them no points.

FAIL if Currency or Actionability receives any points above 0, for example Currency credited
because the copied paths, versions or commands are accurate or "not stale", or Actionability
credited for the copied setup steps.
