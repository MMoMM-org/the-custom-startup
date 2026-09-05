# docs/ai/ — Memory Bank Rules

## Maintenance
- /memory-add — capture learnings from this session
- /memory-sync — verify @imports and index are in sync
- /memory-cleanup — archive resolved issues and prune stale context (run monthly)
- /memory-promote — detect promotable domain patterns → reusable skills (run when domain.md grows)

## Before proposing something structural
Read `declined.md` first. A new layer, tool swap, restructure, automation, or upstream adoption that is already recorded there is re-pitched only when its `Revisit if` condition holds — or explicitly as a trade-off quoting the original decline. Never as a fresh idea.

## Category definitions
- general.md: naming, code style, git workflow (longlived)
- tools.md: CI, build, local dev quirks (longlived/medium)
- domain.md: business rules, data models (medium)
- decisions.md: architecture choices, ADR links (medium)
- context.md: current sprint focus, blockers (short — prune regularly)
- troubleshooting.md: known bugs + fixes (short — archive when resolved)
- active.md: the always-loaded layer — @-imported from CLAUDE.md, reaches every subagent
- declined.md: structural things ruled out, with the condition that reopens each (longlived — supersede, never delete)

## Entry form
One falsifiable rule and its tell — **≤ 250 characters**:

```
- **<rule>** — <tell>. → <consequence>.
```

No verification dates or methods, no incident history, no spec or ADR references. Full rules and a
worked before/after: `memory-add/reference/category-formats.md`.

## Budget
Bank ≤ 24 KB across the category files. Measure with `wc -c`, not `wc -l` — entries are single
long lines, so line counts say nothing about cost. /memory-sync checks both.
