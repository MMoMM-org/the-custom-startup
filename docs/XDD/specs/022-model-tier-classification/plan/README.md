---
title: "Model-tier classification and a frontier rung for implement"
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

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| specId | string | Yes | Spec identifier (NNN-name format) |
| title | string | Yes | Feature title |
| status | enum: `DRAFT`, `IN_REVIEW`, `COMPLETE` | Yes | Document readiness |
| phases | PhaseStatus[] | Yes | Status of each implementation phase |
| totalTasks | number | Yes | Total tasks across all phases |
| parallelTasks | number | Yes | Tasks marked `[parallel: true]` |
| specReferences | number | Yes | Count of `[ref: ...]` specification links |
| clarificationsRemaining | number | Yes | Count of `[NEEDS CLARIFICATION]` markers |

### PhaseStatus

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| phase | number | Yes | Phase number |
| name | string | Yes | Phase name |
| status | enum: `COMPLETE`, `NEEDS_CLARIFICATION`, `IN_PROGRESS` | Yes | Current state |
| tasks | number | Yes | Task count in this phase |
| file | string | Yes | Path to phase file (phase-N.md) |
| detail | string | No | What needs clarification or what's in progress |

---

## Specification Compliance Guidelines

### How to Ensure Specification Adherence

1. **Before Each Phase**: Complete the Pre-Implementation Specification Gate
2. **During Implementation**: Reference specific SDD sections in each task
3. **After Each Task**: Run Specification Compliance checks
4. **Phase Completion**: Verify all specification requirements are met

### Deviation Protocol

When implementation requires changes from the specification:
1. Document the deviation with clear rationale
2. Obtain approval before proceeding
3. Update SDD when the deviation improves the design
4. Record all deviations in this plan for traceability

## Metadata Reference

- `[parallel: true]` - Tasks that can run concurrently
- `[component: component-name]` - For multi-component features
- `[ref: document/section; lines: 1, 2-3]` - Links to specifications, patterns, or interfaces and (if applicable) line(s)
- `[activity: type]` - Activity hint for specialist agent selection

### Success Criteria

**Validate** = Process verification ("did we follow TDD?")
**Success** = Outcome verification ("does it work correctly?")

```markdown
# Single-line format
- Success: [Criterion] `[ref: PRD/AC-X.Y]`

# Multi-line format
- Success:
  - [ ] [Criterion 1] `[ref: PRD/AC-X.Y]`
  - [ ] [Criterion 2] `[ref: SDD/Section]`
```

---

## Context Priming

*GATE: Read all files in this section before starting any implementation.*

**Specification**:

- `docs/XDD/specs/022-model-tier-classification/requirements.md` - Product Requirements (27 acceptance criteria, AC-1.1 … AC-6.4)
- `docs/XDD/specs/022-model-tier-classification/solution.md` - Solution Design (ADR-1 … ADR-7)
- `docs/XDD/specs/017-complexity-tier-dispatch/solution.md` - the decomposition-tier contract this extends (CON-5, CON-8, ADR-6)

**Key Design Decisions**:

- **ADR-1**: Model tier is a second section of `classifier.md`, confirmed in step 6's single confirmation round, written as prose (the CON-8 test counts the tool name, already used by the Finalize gate).
- **ADR-3**: One ladder, haiku → sonnet → opus → opus@max → fable, in `xdd/reference/model-ladder.md` beside the classifier; opus@max is `opus` with per-dispatch `effort: max`. The dispatcher `implement/SKILL.md` is not touched.
- **ADR-4**: Absent tier = today's behaviour exactly; `[model:]` task tag overrides the spec tier.
- **ADR-5**: Escalate one rung on a complexity BLOCKED or two review FAILs in a row at one rung (count resets); BLOCKED at the highest reachable rung; fable only with consent; nobody to ask → BLOCKED at opus@max; fable failure → planned task continues on opus@max, escalated task BLOCKED, fable off for the run.
- **ADR-7**: `spec.py` generalises its fail-open reader and prints `model_tier`.

**Implementation Context**:

```bash
# Testing
rm -rf tests/__pycache__ && .venv/bin/python -m pytest -q tests     # Python suite

# Quality
bash scripts/ci/check-changelog-version-sync.sh --allow-ahead 1     # CHANGELOG / manifest sync

# Spec metadata
python3 plugins/tcs-workflow/skills/xdd-meta/spec.py 022 --read
```

---

## Implementation Phases

Each phase is defined in a separate file. Tasks follow red-green-refactor: **Prime** (understand context), **Test** (red), **Implement** (green), **Validate** (refactor + verify).

> **Tracking Principle**: Track logical units that produce verifiable outcomes. The TDD cycle is the method, not separate tracked items.

- [x] [Phase 1: Spike and metadata foundation](phase-1.md)
- [ ] [Phase 2: Model ladder and plan tag](phase-2.md)
- [ ] [Phase 3: Classifier and implement loops](phase-3.md)
- [ ] [Phase 4: Release and end-to-end validation](phase-4.md)

---

## Plan Verification

Before this plan is ready for implementation, verify:

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

### Acceptance-criteria coverage

| PRD AC | Task |
|---|---|
| AC-1.1, 1.4, 1.5 | T3.1 |
| AC-1.2, 1.3 | T3.2 |
| AC-2.1 | T1.3, T3.2 |
| AC-2.2, 2.3 | T1.2 |
| AC-3.1, 3.2 | T2.2, T3.3 |
| AC-3.3 | T2.1, T3.3 |
| AC-4.1, 4.2, 4.3, 4.5 | T2.1, T3.3 |
| AC-4.4 | T2.1, T3.4 |
| AC-5.1 … 5.7 | T2.1, T3.3, T3.4 |
| AC-6.1 … 6.4 | T2.1, T3.3, T3.4 (T1.1 informs the wording of 6.2) |
