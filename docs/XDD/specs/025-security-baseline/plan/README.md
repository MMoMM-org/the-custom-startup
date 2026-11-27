---
title: "security-baseline — audit and set up a Claude Code security baseline"
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

- `docs/XDD/specs/025-security-baseline/requirements.md` — PRD v1.1 (12 features, 68 ACs)
- `docs/XDD/specs/025-security-baseline/solution.md` — SDD (K1–K15, ADR-1..10, criteria F1.1–F12.2, R10, E1–E4)
- `docs/XDD/ideas/2026-11-27-security-baseline.md` — brainstorm, check catalogue origin
- `plugins/tcs-patterns/skills/patterns-setup/lib/cli.py` and `tests/test_patterns_cli.py` — CLI and fixture precedent
- `plugins/tcs-helper/skills/observability-setup/lib/registration.py` — settings read/write precedent

**Key Design Decisions**:

- **ADR-1**: stdlib Python 3.11+ CLI, `python3 -I -B`, verbs audit/plan/apply, JSON on exit 0, exit 0/1/2/3; audit exits 0 with the verdict in JSON.
- **ADR-2**: `plan_id` binds what `apply` writes to what was shown; apply recomputes from live files, single use, 15-min expiry; it does not prove a human said yes.
- **ADR-3**: writer with a hard-coded target allowlist, symlink policy, backup in StateDir, atomic replace, semantic post-write verification and restore.
- **ADR-4**: verdict from per-layer states; FAIL > UNKNOWN > PARTIAL > PASS; severity never downgraded; coverage block always.
- **ADR-6**: own sandbox probe from fixed paths; fail-closed keys only with `--sandbox-confirmed`.

**Implementation Context**:

```bash
# Testing
./scripts/dev/test.sh setup                                        # provision .venv once (needs npm for bats; pytest-only: python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt)
.venv/bin/pytest -q -rs tests/tcs-helper/test_security_baseline_*.py   # this feature
./scripts/dev/test.sh pytest                                       # whole python suite (CI: pytest -q -rs)

# Quality
# no Python linter configured; repo-wide skill lints run inside pytest:
.venv/bin/pytest -q tests/test_skill_body_size.py tests/test_skill_dollar_substitution.py \
  tests/test_shell_portability_lints.py tests/test_agents_md_tree.py

# Interpreter floor: CI runs 3.11 — check any stdlib API you use exists in 3.11
# Manual (Phase 5): bash plugins/tcs-helper/tests/manual/security-baseline-container-check.sh
```

---

## Implementation Phases

Each phase is defined in a separate file. Tasks follow red-green-refactor: **Prime** (understand context), **Test** (red), **Implement** (green), **Validate** (refactor + verify).

> **Tracking Principle**: Track logical units that produce verifiable outcomes. The TDD cycle is the method, not separate tracked items.

- [x] [Phase 1: Foundations — strict JSON, reference data, untrusted rendering](phase-1.md)
- [ ] [Phase 2: Reading the machine — environment, probe, layers, inventory](phase-2.md)
- [ ] [Phase 3: Evaluation and the audit verb](phase-3.md)
- [ ] [Phase 4: Setup — plan, state, writer, apply](phase-4.md)
- [ ] [Phase 5: Skill, docs and end-to-end validation](phase-5.md)

Dependency order: 1 → 2 → 3 → 4 → 5. Within phases 1–3 most tasks are parallel (marked).

### Traceability

| SDD criteria | Phase / task |
|---|---|
| F1.1–F1.8 | T1.3 (F1.8), T3.6 (F1.1–F1.7) |
| F2.1–F2.6 | T2.1 |
| F3.1–F3.5 | T3.2 |
| F4.1–F4.4 | T3.3 (F4.2 planning half: T4.2) |
| F5.1–F5.6 | T1.2 (lists), T3.4 |
| F6.1–F6.8 | T2.2 (F6.2–F6.4, F6.8), T3.2 (F6.1), T4.2 (F6.5–F6.7) |
| F7.1–F7.2 | T3.4 |
| F8.1–F8.5 | T2.3 (F8.4), T3.5, T4.2 (F8.2 planning) |
| F9.1–F9.14, R10, E1–E4 | T4.1, T4.2, T4.3, T4.4, T5.1 (F9.2 skill half, F9.14 text) |
| F10.1–F10.5 | T2.4 (template), T3.5 |
| F11.1–F11.3 | T3.5 (F11.2 planning half: T4.2) |
| F12.1–F12.2 | T2.4 (skills), T3.5, T4.2 |

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
