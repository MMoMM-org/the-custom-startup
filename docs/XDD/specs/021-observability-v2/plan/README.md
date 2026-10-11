---
title: "Observability v2: typed skills, named subagents and git commands leave a record"
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
| specId | 021-observability-v2 |
| title | Observability v2: typed skills, named subagents and git commands leave a record |
| status | IN_REVIEW |
| totalTasks | 13 |
| parallelTasks | 5 |
| clarificationsRemaining | 0 |

### PhaseStatus

| Phase | Name | Tasks | File |
|---|---|---|---|
| 1 | Writer hardening and git parsing | 3 | phase-1.md |
| 2 | Adapters | 3 | phase-2.md |
| 3 | Registration and install | 2 | phase-3.md |
| 4 | Report | 2 | phase-4.md |
| 5 | Guard fast path and end-to-end validation | 3 | phase-5.md |

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

---

## Context Priming

*GATE: Read all files in this section before starting any implementation.*

**Specification**:

- `docs/XDD/specs/021-observability-v2/requirements.md` - Product Requirements (35 ACs, F1–F8)
- `docs/XDD/specs/021-observability-v2/solution.md` - Solution Design (ADR-1..9, acceptance criteria per feature)
- `docs/XDD/specs/021-observability-v2/README.md` - measured payloads (Claude Code 2.1.296) and decisions
- `docs/XDD/specs/021-observability-v2/research.md` - file:line findings
- `docs/XDD/specs/018-observability-load-and-fire-log/solution.md` § Data Storage Changes, § Complex Logic - writer contract, `detail:` mechanism
- `docs/XDD/specs/019-observability-rollout-across-active-repos/solution.md` ADR-1, ADR-3, ADR-5 - registration, bundle versioning, ownership

**Key Design Decisions**:

- **ADR-1**: one PreToolUse entry, matcher `Skill|Agent|Bash`, script `log_tool.sh`; the registration model stays one entry per event.
- **ADR-2**: `_strip_heredocs`, `_strip_quoted` and the #213 executor predicate are copied into `git_ops.sh` and pinned by a parity test; the guard's raw-substring fallback is not copied.
- **ADR-6**: `log_tool.sh` and the guard use `#!/bin/bash`; `log_tool.sh` reads with `$(cat)` (measured: `read -d ''` 62 ms at 200 KB).
- **ADR-9 / CON-13**: git records carry names only — subcommand, flag names (short flags as first letter, ADR-3), override names and position, caller — never values.
- **ADR-5**: per-repo drift state `OURS-INCOMPLETE`; `setup.sh` must accept the new label.

**Implementation Context**:

```bash
# Testing
pytest -q                                    # all python tests (tests/, tests/tcs-helper/)
bats --recursive plugins/tcs-helper/tests/bats      # observability suites (run outside the Bash sandbox: mktemp)
bats --recursive plugins/tcs-git-helpers/tests/bats # guard and parity source

# Quality
shellcheck <changed .sh files>

# Gates (as CI runs them)
bash plugins/tcs-git-helpers/scripts/ci/check-hook-bundle-version.sh origin/main..HEAD
bash scripts/ci/check-docs-sync.sh --changed-files <file> --pr-body <file>
bash scripts/ci/check-changelog-version-sync.sh --allow-ahead 1

# Perf
pytest -m perf -q        # python perf tests only (opt-in)
# bats perf cases run in every bats run; bounds scale by TCS_PERF_SLACK (4 in CI)
```

---

## Implementation Phases

Each phase is defined in a separate file. Tasks follow red-green-refactor: **Prime** (understand context), **Test** (red), **Implement** (green), **Validate** (refactor + verify).

> **Tracking Principle**: Track logical units that produce verifiable outcomes. The TDD cycle is the method, not separate tracked items.

- [ ] [Phase 1: Writer hardening and git parsing](phase-1.md)
- [ ] [Phase 2: Adapters](phase-2.md)
- [ ] [Phase 3: Registration and install](phase-3.md)
- [ ] [Phase 4: Report](phase-4.md)
- [ ] [Phase 5: Guard fast path and end-to-end validation](phase-5.md)

Dependencies: 1 → 2 → 3; 4 needs 2 (record shapes); 5's T5.1 is independent of 1–4 and may run any time; T5.2–T5.3 need 1–4.

**Ships as one pull request.** `check-hook-bundle-version.sh` gates `scripts/observability/*.sh` over the PR's whole range: Phase 1 changes gated scripts, and the marker moves to h2 only in T3.2. A PR cut before T3.2 fails the gate.

---

## Plan Verification

| Criterion | Status |
|-----------|--------|
| A developer can follow this plan without additional clarification | ✅ |
| Every task produces a verifiable deliverable | ✅ |
| All PRD acceptance criteria map to specific tasks | ✅ (see § Traceability) |
| All SDD components have implementation tasks | ✅ |
| Dependencies are explicit with no circular references | ✅ |
| Parallel opportunities are marked with `[parallel: true]` | ✅ |
| Each task has specification references `[ref: ...]` | ✅ |
| Project commands in Context Priming are accurate | ✅ |
| All phase files exist and are linked from this manifest as `[Phase N: Title](phase-N.md)` | ✅ |

### Traceability (PRD AC → task)

| PRD | Task |
|---|---|
| F1 AC1, AC3, AC4 | T2.3 |
| F1 AC2 | T2.1 |
| F1 AC5 | T4.1 |
| F2 AC1, AC2, AC4 | T2.1 |
| F2 AC3 | T4.1 |
| F3 AC6, AC7, AC8, AC9 | T1.3 (parsing), T2.2 (records, end to end) |
| F3 AC1, AC2, AC3, AC4, AC5, AC10 | T2.2 |
| F4 AC1, AC2, AC4 | T4.1 |
| F4 AC3, AC5 | T4.2 |
| F5 AC1–AC5 | T3.1 (AC3 state), T3.2 (install, AC1 end to end) |
| F6 AC1, AC3 | T1.1 |
| F6 AC2 | T3.2 |
| F7 AC1, AC2 | T5.1 |
| F8 | deferred (Could; marked deferred in the PRD; excluded from T5.3's check-off) |
