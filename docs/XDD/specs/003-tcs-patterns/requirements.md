---
spec: 003-tcs-patterns
document: requirements
status: placeholder — specify after M1 stable
---

# PRD — tcs-patterns Plugin (M3)

## Summary

New optional plugin providing domain knowledge skills. Skills are loaded on demand when the relevant domain pattern is needed. Domain knowledge promoted from repo memory files (via M2 memory-promote) lands here.

## Key Deliverables

- New `tcs-patterns` plugin with standard `.claude-plugin/plugin.json`
- Domain knowledge skills (from citypaul/.dotfiles):
  - `ddd` — Domain-Driven Design patterns
  - `hexagonal` — Ports and adapters architecture
  - `functional` — Functional/immutable programming patterns
  - `typescript-strict` — TypeScript strict mode enforcement
  - `mutation-testing` — Strengthen test suites via mutation
  - `frontend-testing` — Frontend-specific test patterns
  - `react-testing` — React component and hook testing
  - `twelve-factor` — 12-factor app compliance
- ADR agent: `tcs-team:the-architect/record-decision.md`
- Promotion pipeline: `memory-promote` (M2) → tcs-patterns skill stub

## Reference

- `docs/concept/overlap-analysis.md` — citypaul extraction table
- `docs/concept/tcs-vision.md` — tcs-patterns plugin section
