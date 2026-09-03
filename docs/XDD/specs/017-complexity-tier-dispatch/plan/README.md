---
title: "Complexity-tier dispatch for xdd and implement — Implementation Plan"
status: draft
version: "1.0"
---

# Implementation Plan

## Validation Checklist

### CRITICAL GATES (Must Pass)

- [x] All `[NEEDS CLARIFICATION: ...]` markers have been addressed
- [x] All specification file paths are correct and exist
- [x] Each phase follows TDD: Prime → Test → Implement → Validate
- [x] Every task has verifiable success criteria
- [x] A developer could follow this plan independently

### QUALITY CHECKS (Should Pass)

- [x] Context priming section is complete
- [x] All implementation phases are defined with linked phase files
- [x] Dependencies between phases are clear (no circular dependencies)
- [x] Parallel work is properly tagged with `[parallel: true]`
- [x] Activity hints provided for specialist selection `[activity: type]`
- [x] Every phase references relevant SDD sections
- [x] Every test references PRD acceptance criteria
- [x] Integration & E2E tests defined in final phase
- [x] Project commands match actual project setup

---

## Output Schema

### PLAN Status Report

| Field | Value |
|-------|-------|
| specId | 017-complexity-tier-dispatch |
| title | Complexity-tier dispatch for xdd and implement |
| status | COMPLETE |
| totalTasks | 15 |
| parallelTasks | 4 |
| specReferences | 44 |
| clarificationsRemaining | 0 |

### PhaseStatus

| Phase | Name | Status | Tasks | File |
|-------|------|--------|-------|------|
| 1 | Tier metadata foundation | IMPLEMENTED | 4 | [phase-1.md](phase-1.md) |
| 2 | Classification in xdd | IMPLEMENTED | 3 | [phase-2.md](phase-2.md) |
| 3 | Implementation split and dispatch | IMPLEMENTED | 5 | [phase-3.md](phase-3.md) |
| 4 | Registration and end-to-end validation | IN_PROGRESS | 3 | [phase-4.md](phase-4.md) |

---

## Specification Compliance Guidelines

### How to Ensure Specification Adherence

1. **Before Each Phase**: Complete the Pre-Implementation Specification Gate — read the phase's referenced SDD sections before writing anything.
2. **During Implementation**: Reference specific SDD sections in each task.
3. **After Each Task**: Run Specification Compliance checks.
4. **Phase Completion**: Verify all specification requirements are met.

### Deviation Protocol

When implementation requires changes from the specification:
1. Document the deviation with clear rationale.
2. Obtain approval before proceeding.
3. Update the SDD when the deviation improves the design.
4. Record all deviations in this plan for traceability.

**One deviation is pre-authorised and expected:** the exact classifier thresholds in `SDD/Implementation Examples` are unvalidated against real data (SDD *Technical Debt*). If T2.1's test over the four traced specs disagrees with the documented rules, fix the *rules* and update the SDD table — do not bend the traced expectations to match a broken rule.

## Metadata Reference

- `[parallel: true]` — Tasks that can run concurrently
- `[ref: document/section]` — Links to specifications
- `[activity: type]` — Activity hint for specialist agent selection

### Success Criteria

**Validate** = Process verification ("did we follow TDD?")
**Success** = Outcome verification ("does it work correctly?")

---

## Context Priming

*GATE: Read all files in this section before starting any implementation.*

**Specification**:

- `docs/XDD/specs/017-complexity-tier-dispatch/requirements.md` — Product Requirements (24 acceptance criteria)
- `docs/XDD/specs/017-complexity-tier-dispatch/solution.md` — Solution Design (7 ADRs, 24 EARS criteria)
- `docs/about/skill-and-agent-design.md` — the extraction threshold behind ADR-5 and ADR-7
- `docs/about/principles.md` — progressive disclosure, activation contract

**Key Design Decisions**:

- **ADR-1 What scales** — tier the PLAN only; requirements and solution are written at every tier, so the spec-first rule survives verbatim.
- **ADR-3 Tier count** — ship Direct and Incremental only; Factory is a named, reserved, unbuilt member of the vocabulary. Do not build factory machinery.
- **ADR-4 Dispatch signal** — detect the tier from artifacts present; the recorded tier is a cross-check that reports a mismatch, never the primary signal.
- **ADR-5 `implement` restructuring** — `implement` keeps its name and becomes a dispatcher; its current 296-line body moves **verbatim** into a hidden `implement-incremental`. This is a move, not a rewrite.
- **ADR-6 Where tier is recorded** — README Status row (human), decision log (audit), `spec.py --read` key (machine).

**Implementation Context**:

```bash
# Testing
.venv/bin/python -m pytest tests/ -q          # Python unit tests (spec.py, classifier rules, dispatch rules)
bats plugins/*/tests/bats                     # Shell/hook tests (untouched by this spec)

# Quality
shellcheck scripts/ci/*.sh                    # Shell lint (untouched by this spec)
bash scripts/ci/check-changelog-version-sync.sh --allow-ahead 1   # CHANGELOG/manifest invariant

# Skill conventions (CON-7) — run per new or modified skill
# Invoke the tcs-helper:skill-author skill in audit mode on each skill directory

# NEVER bump plugins/tcs-workflow/.claude-plugin/plugin.json by hand — CI owns it (CON-6)
```

---

## Implementation Phases

Each phase is defined in a separate file. Tasks follow red-green-refactor: **Prime** (understand context), **Test** (red), **Implement** (green), **Validate** (refactor + verify).

> **Tracking Principle**: Track logical units that produce verifiable outcomes. The TDD cycle is the method, not separate tracked items.

**Sequencing.** Phase 1 is the foundation both later phases depend on — Phase 2 writes the tier, Phase 3 reads it. Phases 2 and 3 touch disjoint files and are independent of each other; they may run concurrently once Phase 1 lands. Phase 4 is last because it validates the assembled whole.

```
Phase 1 (metadata) ──┬──> Phase 2 (xdd classifies) ──┬──> Phase 4 (registration + E2E)
                     └──> Phase 3 (implement splits) ─┘
```

- [x] [Phase 1: Tier metadata foundation](phase-1.md)
- [x] [Phase 2: Classification in xdd](phase-2.md)
- [x] [Phase 3: Implementation split and dispatch](phase-3.md)
- [ ] [Phase 4: Registration and end-to-end validation](phase-4.md)

---

## A note on how skills get tested here

TCS skills are Markdown interpreted by an agent, so most of them cannot be unit-tested the way a function can. This plan does not pretend otherwise. It gets real red-green coverage by extracting the two pieces of genuine *logic* into Python that tests can execute:

- **the classifier's rules** (T2.1) — tested against the four real specs traced in the SDD, plus its edge cases;
- **the dispatcher's detection table** (T3.1) — tested against all 16 existing spec directories, which is the executable form of CON-5.

Everything else is verified structurally (frontmatter assertions, the `skill-author` audit) and behaviourally (Phase 4's scripted walkthroughs). Where a control cannot be automated, the phase says so rather than inventing a test. Broader eval coverage for skills is tracked separately as issue #84 and is explicitly out of scope here.

---

## Plan Verification

| Criterion | Status |
|-----------|--------|
| A developer can follow this plan without additional clarification | ✅ |
| Every task produces a verifiable deliverable | ✅ |
| All PRD acceptance criteria map to specific tasks | ✅ |
| All SDD components have implementation tasks | ✅ |
| Dependencies are explicit with no circular references | ✅ |
| Parallel opportunities are marked with `[parallel: true]` | ✅ |
| Each task has specification references `[ref: ...]` | ✅ |
| Project commands in Context Priming are accurate | ✅ |
| All phase files exist and are linked from this manifest as `[Phase N: Title](phase-N.md)` | ✅ |
