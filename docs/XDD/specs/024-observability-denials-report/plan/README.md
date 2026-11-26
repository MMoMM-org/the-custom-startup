---
title: "Observability denials report"
status: approved
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
- `[model: routine|hard|frontier]` - Overrides the spec's model tier for this task

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

- `docs/XDD/specs/024-observability-denials-report/requirements.md` - Product Requirements (F1–F9)
- `docs/XDD/specs/024-observability-denials-report/solution.md` - Solution Design (ADR-1..8, classification table, walkthrough)
- `docs/XDD/specs/024-observability-denials-report/research.md` - Denial families, traps, field shapes
- `scripts/observability/report.py`, `scripts/observability/sources.py`, `tests/test_observability_report.py`, `tests/test_observability_sources.py` - integration points and test style

**Key Design Decisions**:

- **ADR-1**: new pure module `scripts/observability/denials.py`, no local imports; `report.py` calls it per source.
- **ADR-3**: per home, project dirs whose name starts with the encoded repo root (main + `*/subagents/`), then per-line cwd filter with worktree suffix stripped.
- **ADR-4/8**: ordered classification table with hook owners; prefixed unknown → hook deny, unattributed; unprefixed unknown → not a denial.
- **ADR-5**: only `type == "user"` + `is_error: true`; dedupe by `(file, tool_use_id)`.
- **CON-2**: no transcript or override `command` text in the output; `render` sees only `DenialsSummary`.

**Implementation Context**:

```bash
# Environment
python -m pip install -r requirements-dev.txt

# Testing
pytest -q tests/test_observability_denials.py tests/test_observability_sources.py tests/test_observability_report.py tests/test_observability_report_t30_golden.py

# Full validation
pytest -q
```

---

## Implementation Phases

Each phase is defined in a separate file. Tasks follow red-green-refactor: **Prime** (understand context), **Test** (red), **Implement** (green), **Validate** (refactor + verify).

> **Tracking Principle**: Track logical units that produce verifiable outcomes. The TDD cycle is the method, not separate tracked items.

- [x] [Phase 1: Reading and classifying transcripts](phase-1.md)
- [x] [Phase 2: Aggregation, overrides and rendering](phase-2.md)
- [x] [Phase 3: Report integration, docs and validation](phase-3.md)

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

### PRD acceptance criteria → tasks

| PRD feature | Tasks |
|---|---|
| F1 opt-in and enablement state | T1.1 (config key), T3.1 (not enabled / no transcripts in section) |
| F2 classification | T1.2 (table), T1.3 (scan, dedupe, non-error ignored) |
| F3 summary per source and period | T2.2 (aggregate), T2.3 (render), T3.1 (per-source placement) |
| F4 top repeated denials | T2.1 (override counts), T2.2 (top rows), T2.3 (render) |
| F5 empty and partial states | T1.3 (skipped lines, versions), T2.3 (render) |
| F6 no content in output | T2.3 (sentinel test), T3.1 (end-to-end sentinel) |
| F7 documented limits | T3.2 |
| F8 adjustable period | T2.2 (`period_from_args`), T3.1 (CLI) |
| F9 version breakdown (Could) | not planned; deferred per SDD |
