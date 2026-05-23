---
title: "tcs-git-helpers Rule Fixes — Squash-Merge-Trap Nuance + Inline Override Support"
status: complete
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

- `docs/XDD/specs/014-tcs-git-helpers-rules-fix/requirements.md` — Product Requirements (8 ACs across M1/M2/S1)
- `docs/XDD/specs/014-tcs-git-helpers-rules-fix/solution.md` — Solution Design (CON-1..7, 9 ADRs, Building Block + Runtime View)

**Existing code (read before any edit)**:

- `plugins/tcs-git-helpers/scripts/block-bad-git-ops.sh` — dispatcher + `_check_push_to_closed_pr` (lines 218–267 are M1 target)
- `plugins/tcs-git-helpers/scripts/lib/override.sh` — `_check_and_consume_override` (lines 66–153 are M2 target)
- `plugins/tcs-git-helpers/scripts/lib/cache.sh` — `_read_pr_state_cache` / `_write_pr_state_cache` (extend with `merge_commit` field)
- `plugins/tcs-git-helpers/tests/bats/test_push_to_closed_pr.bats` — existing M1 deny assertions (must continue to pass)
- `plugins/tcs-git-helpers/tests/bats/test_override.bats` — existing env-var override assertions (must continue to pass)
- `plugins/tcs-git-helpers/tests/python/test_drift_check.py` — bash/python parity rows for CON-2

**Key Design Decisions**:

- **ADR-1**: HEAD-vs-merge detection via `git merge-base --is-ancestor` — cheap, deterministic, no log walking `[ref: SDD/ADR-1; lines: 729-754]`
- **ADR-2**: Tool-input scanning via CMD global — `override.sh` reuses the `CMD` variable already parsed by `block-bad-git-ops.sh:60`; no new stdin read, no new state machine `[ref: SDD/ADR-2; lines: 756-782]`
- **ADR-3**: Regex anchored to start-of-command (`^${env_var}=1[[:space:]]+`) — prevents mid-command / shell-injection bypass `[ref: SDD/ADR-3; lines: 784-808]`
- **ADR-6**: `_check_and_consume_override <rule>` call signature is frozen — all 5+ existing call sites remain unchanged `[ref: SDD/ADR-6; lines: 860-875]`
- **ADR-8**: Allow-path UX: stderr informational note on the "HEAD ahead of merged" allow path `[ref: SDD/ADR-8; lines: 907-933]`

**Constraints (must not be violated)**:

- **CON-1**: bash 3.2 — no associative arrays, no `mapfile`, no `${var,,}/${var^^}` `[ref: SDD/Constraints; lines: 36-40]`
- **CON-2**: Python ↔ bash parity for any new regex/classification logic that has a Python equivalent `[ref: SDD/Constraints; lines: 42-46]`
- **CON-3**: `_check_and_consume_override <rule>` signature frozen — see ADR-6 `[ref: SDD/Constraints; lines: 48-50]`
- **CON-5**: Defensive stdin parse — missing/empty/non-JSON must fall back gracefully without error output `[ref: SDD/Constraints; lines: 57-60]`
- **CON-6**: No new CLI tool dependencies — only `git`, `gh`, `jq` `[ref: SDD/Constraints; lines: 62-64]`
- **CON-7**: Scope boundary — only `block-bad-git-ops.sh`, `lib/override.sh`, `lib/cache.sh` (and their tests) are touched `[ref: SDD/Constraints; lines: 66-68]`

**Implementation Context**:

```bash
# Test
cd plugins/tcs-git-helpers && bats tests/bats/
cd plugins/tcs-git-helpers && python -m pytest tests/python/

# Lint (shellcheck)
shellcheck plugins/tcs-git-helpers/scripts/block-bad-git-ops.sh
shellcheck plugins/tcs-git-helpers/scripts/lib/override.sh
shellcheck plugins/tcs-git-helpers/scripts/lib/cache.sh

# Plugin version bump (after implementation complete)
# Edit plugins/tcs-git-helpers/.claude-plugin/plugin.json — bump version; push to trigger marketplace sync.
```

---

## Implementation Phases

Each phase is defined in a separate file. Tasks follow red-green-refactor: **Prime** (understand context), **Test** (red), **Implement** (green), **Validate** (refactor + verify).

> **Tracking Principle**: Track logical units that produce verifiable outcomes. The TDD cycle is the method, not separate tracked items.

> **Phase parallelism**: Phase 1 (M1) and Phase 2 (M2) touch disjoint files (`block-bad-git-ops.sh` + `cache.sh` vs. `override.sh`) and have no cross-dependency. They MAY be implemented concurrently. Phase 3 depends on both.

- [x] [Phase 1: M1 — Squash-Merge-Trap Nuance](phase-1.md)
- [x] [Phase 2: M2 — Tool-Input Override Scanning](phase-2.md)
- [x] [Phase 3: Final Integration, S1 & Release](phase-3.md)

---

## Plan Verification

Before this plan is ready for implementation, verify:

| Criterion | Status |
|-----------|--------|
| A developer can follow this plan without additional clarification | ✅ |
| Every task produces a verifiable deliverable | ✅ |
| All PRD acceptance criteria map to specific tasks (M1-AC1..3, M2-AC1..4, S1-AC1, M2-AC-REGEX) | ✅ |
| All SDD components have implementation tasks (`_is_ahead_of_merged`, `_scan_tool_input_for_override`, cache extension) | ✅ |
| Dependencies are explicit with no circular references | ✅ |
| Parallel opportunities are marked with `[parallel: true]` | ✅ |
| Each task has specification references `[ref: ...]` | ✅ |
| Project commands in Context Priming are accurate | ✅ |
| All phase files exist and are linked from this manifest as `[Phase N: Title](phase-N.md)` | ✅ |
