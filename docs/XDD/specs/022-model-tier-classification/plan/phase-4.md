---
title: "Phase 4: Release and end-to-end validation"
status: in_progress
version: "1.0"
phase: 4
---

# Phase 4: Release and end-to-end validation

## Phase Context

**GATE**: Read all referenced files before starting this phase.

**Specification References**:
- `[ref: SDD/Deployment View]` — README notes the 2.1.292 minimum for opus@max
- `[ref: SDD/Risks and Technical Debt; Implementation Gotchas]` — `CLAUDE_CODE_EFFORT_LEVEL` override note
- `[ref: SDD/Quality Requirements]`
- `[ref: SDD/Constraints; CON-6, CON-7]`

**Key Decisions**:
- One tcs-workflow version bump; root and plugin CHANGELOG entries.
- A walkthrough, not only tests: green string tests over skill Markdown have missed defects a walkthrough found.

**Dependencies**:
- Phases 1–3.

---

## Tasks

Ships the feature and proves the workflow end to end.

- [x] **T4.1 Documentation and release notes** `[activity: documentation]`

  1. Prime: Read `plugins/tcs-workflow/README.md` and both CHANGELOGs `[ref: SDD/Deployment View]`.
  2. Test: `bash scripts/ci/check-changelog-version-sync.sh --allow-ahead 1` fails before the entries exist.
  3. Implement: README section on the model tier, the ladder, consent and its cost, the bounded review loop, the 2.1.292 minimum, the `CLAUDE_CODE_EFFORT_LEVEL` override, and that the served model is read from the subagent transcript (T1.1); CHANGELOG entries.
  4. Validate: Changelog sync check passes; docs-sync CI passes.
  5. Success: `[ref: SDD/Constraints; CON-6]`; `[ref: SDD/ADR-6]`

- [x] **T4.2 Walkthrough of both journeys** `[activity: validate]`

  1. Prime: Read the PRD journeys `[ref: PRD/User Journey Maps]`.
  2. Test: Walk xdd step 6 on spec 022 itself (expected: Incremental, `hard` via `adr_count >= 3`) and on a doc-only stub (expected: routine). Walk implement-incremental on paper: two FAILs in a row at sonnet → opus with the count reset; complexity BLOCKED at opus@max → fable consent question; YOLO → BLOCKED at opus@max; a planned frontier task whose fable dispatch errors → opus@max and the run continues; a task failing twice at its highest rung → BLOCKED, no further retry.
  3. Implement: Fix any step the walkthrough cannot follow from the skill text alone.
  4. Validate: Each walked step cites the skill line that produced it.
  5. Success: `[ref: PRD/AC-1.2]` `[ref: PRD/AC-5.3]` `[ref: PRD/AC-5.4]` `[ref: PRD/AC-5.7]` `[ref: PRD/AC-6.1]` hold in the skill text as written

- [ ] **T4.3 Final validation** `[activity: validate]`

  - Gate task. Full Python suite (`rm -rf tests/__pycache__ && .venv/bin/python -m pytest -q tests`), changelog sync, `Skill(tcs-workflow:validate)` drift for spec 022, skill-author audit of every changed SKILL.md. Record `Model tier: hard` in spec 022's own README once the reader exists.
