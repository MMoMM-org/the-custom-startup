---
title: "Phase 4: About Section"
status: completed
version: "1.0"
phase: 4
---

# Phase 4: About Section

## Phase Context

**GATE**: Read all referenced files before starting this phase.

**Specification References**:
- `[ref: SDD/Directory Map — about/]` — 3 files: the-custom-philosophy.md, sources.md, principles.md
- `[ref: SDD/Technical Debt]` — PHILOSOPHY.md and the-custom-philosophy.md are duplicates; extract from both before deleting
- `[ref: PRD/Feature 5]` — attribution and sources document
- `[ref: SDD/Implementation Gotchas]` — concept/ files have no consistent format; use judgment on what to extract

**Key Decisions**:
- `about/the-custom-philosophy.md` replaces `docs/PHILOSOPHY.md` as the canonical philosophy doc (not the other way around)
- `about/sources.md` lists: base fork (rsmdt), citypaul skills (10 with names), TCS-native (5 with names), integration (2 with names)
- The custom-philosophy content takes precedence when it conflicts with PHILOSOPHY.md

**Dependencies**:
- Phase 1 complete (directory scaffold exists)
- T4.1, T4.2, T4.3 are independent and can run in parallel

---

## Tasks

Establishes the about/ section: philosophy, attribution, and principles.

- [x] **T4.1 Write about/the-custom-philosophy.md** `[activity: documentation]` `[parallel: true]`

  1. Prime: Read `docs/the-custom-philosophy.md` (current — this is the canonical version); read `docs/PHILOSOPHY.md` (older version — for any unique content); read `docs/concept/` and `docs/concept/v2/` files for insights to promote `[ref: SDD/Technical Debt; PRD/Feature 4]`
  2. Test: Note what `the-custom-philosophy.md` contains that `PHILOSOPHY.md` doesn't (and vice versa); identify 2-3 insights from concept/ worth promoting (e.g., activity-based agent rationale, XDD origins); ensure fork attribution to rsmdt is present
  3. Implement: Write `docs/about/the-custom-philosophy.md` — start from `the-custom-philosophy.md` content; incorporate any unique insights from `PHILOSOPHY.md` that aren't already covered; fold in the best concept/ insights (1-2 paragraphs max); keep attribution to rsmdt/the-startup intact
  4. Validate: File exists at `docs/about/the-custom-philosophy.md`; rsmdt attribution present; no `tcs-start` references
  5. Success: Canonical philosophy doc in correct location with concept/ insights promoted `[ref: PRD/Feature 4; PRD/Brainstorm decisions]`

- [x] **T4.2 Write about/sources.md** `[activity: documentation]` `[parallel: true]`

  1. Prime: Read `docs/XDD/ideas/2026-03-28-docs-rewrite.md` Attribution Notes section; glob `plugins/tcs-patterns/skills/*/SKILL.md` to confirm exact skill names for citypaul vs TCS-native attribution; read `plugins/tcs-patterns/` to identify integration skills (mcp-server, obsidian-plugin) `[ref: PRD/Feature 5; SDD/sources.md Content Model]`
  2. Test: Verify counts: citypaul-derived = 10 (list names), TCS-native = 5 (list names: event-driven, api-design, go-idiomatic, node-service, python-project), integration = 2 (mcp-server, obsidian-plugin); confirm rsmdt/the-startup URL
  3. Implement: Write `docs/about/sources.md` — sections: Base Fork (rsmdt with URL and what was derived), tcs-patterns origin (3 categories with counts + skill names listed), output styles origin, agent architecture origin (activity-based pattern rationale); keep tone factual and crediting
  4. Validate: All 3 skill categories present with correct counts (10 + 5 + 2 = 17); rsmdt URL included; tone is clear attribution, not promotional
  5. Success:
    - [ ] rsmdt/the-startup named as base fork with link `[ref: PRD/AC Feature 5]`
    - [ ] Skill origin categories with correct counts `[ref: PRD/AC Feature 5]`
    - [ ] 17 total skills accounted for `[ref: PRD/Feature 5]`

- [x] **T4.3 Move about/principles.md** `[activity: documentation]` `[parallel: true]`

  1. Prime: Read `docs/PRINCIPLES.md` (current) — assess if any stale plugin references exist `[ref: SDD/Directory Map]`
  2. Test: Check for any `tcs-start` or `start:` references; verify content is still accurate for v2
  3. Implement: Copy `docs/PRINCIPLES.md` to `docs/about/principles.md`; fix any stale plugin name references; minor update only — no content restructuring
  4. Validate: File exists at `docs/about/principles.md`; `grep "tcs-start" docs/about/principles.md` → 0 results
  5. Success: principles.md in correct location with accurate content `[ref: SDD/Directory Map]`

- [x] **T4.4 Phase 4 Validation** `[activity: validate]`

  - `ls docs/about/` → 3 files: `principles.md`, `sources.md`, `the-custom-philosophy.md`
  - `grep -r "tcs-start" docs/about/ --include="*.md"` → 0 results
  - Confirm `about/sources.md` mentions rsmdt and lists all 3 skill origin categories
  - Confirm `about/the-custom-philosophy.md` contains the fork attribution
