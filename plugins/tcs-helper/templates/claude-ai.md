# docs/ai/ — Memory Bank Rules

## Maintenance
- /memory-add — capture learnings from this session
- /memory-sync — verify @imports and index are in sync
- /memory-cleanup — archive resolved issues and prune stale context (run monthly)
- /memory-promote — detect promotable domain patterns → reusable skills (run when domain.md grows)

## Category definitions
- general.md: naming, code style, git workflow (longlived)
- tools.md: CI, build, local dev quirks (longlived/medium)
- domain.md: business rules, data models (medium)
- decisions.md: architecture choices, ADR links (medium)
- context.md: current sprint focus, blockers (short — prune regularly)
- troubleshooting.md: known bugs + fixes (short — archive when resolved)

## Entry form
One falsifiable rule, its tell, one pointer — **≤ 250 characters**:

```
- **<rule>** — <tell>. → <consequence>. [<pointer>]
```

No verification dates or methods, no incident history, no second pointer. Full rules and a
worked before/after: `memory-add/reference/category-formats.md`.

## Budget
Bank ≤ 24 KB across the category files. Measure with `wc -c`, not `wc -l` — entries are single
long lines, so line counts say nothing about cost. /memory-sync checks both.
