---
title: "tcs-git-helpers hook runtime contract & plugin-update propagation"
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

## Specification Compliance Guidelines

### How to Ensure Specification Adherence

1. **Before Each Phase**: Read the Context Priming + the phase's Specification References.
2. **During Implementation**: Reference SDD sections / PRD acceptance criteria in each task's Success.
3. **After Each Task**: Run Validate step; on failure stop and reconcile.
4. **Phase Completion**: Verify all phase Success criteria pass and all PRD ACs that the phase claims are now demonstrably met.

### Deviation Protocol

When implementation requires changes from the specification:
1. Document the deviation in the affected phase file with clear rationale.
2. Obtain approval before proceeding.
3. Update SDD when the deviation improves the design.
4. Record all deviations in the affected phase for traceability.

## Metadata Reference

- `[parallel: true]` — Tasks that can run concurrently
- `[ref: document/section]` — Links to PRD / SDD / patterns
- `[activity: type]` — Activity hint for specialist agent selection

### Success Criteria

**Validate** = Process verification ("did we follow TDD?")
**Success** = Outcome verification ("does it work correctly?")

---

## Context Priming

*GATE: Read all files in this section before starting any implementation.*

**Specification**:

- `docs/XDD/specs/012-tcs-git-helpers-hook-runtime-contract/requirements.md` — PRD
- `docs/XDD/specs/012-tcs-git-helpers-hook-runtime-contract/solution.md` — SDD
- `docs/XDD/specs/011-tcs-git-helpers/solution.md` — original tcs-git-helpers SDD (extends from there)
- `docs/ai/memory/tools.md` — env-var contract fact recorded this session

**Key Design Decisions** (extracted from SDD § Architecture Decisions):

- **ADR-1 — Sibling layout**: hook files + `lib-bundle.sh` are siblings in `.githooks/`; hooks source the lib via `"$(dirname "$0")/lib-bundle.sh"`.
- **ADR-2 — Bundle version source-of-truth**: `templates/githooks/tcs-git-helpers-version` (single-line file).
- **ADR-3 — Skill reads installed version from `.githooks/tcs-git-helpers-version`**, never by parsing hook banner.
- **ADR-4 — Shared drift-check helper** in plugin source: `scripts/lib/drift_check.{sh,py}`.
- **ADR-5 — `cmd_cleanup` live-refreshes cache** every invocation when `gh` is authenticated.
- **ADR-6 — Structured stderr one-liners** replace every silent `return 0` guard path.
- **ADR-7 — CI gate** at `scripts/ci/check-hook-bundle-version.sh` enforces the maintainer contract.
- **ADR-8 — Pre-bundle installs surface as `MISSING`**, not a special legacy state.

**Implementation Context**:

```bash
# Tests
bats plugins/tcs-git-helpers/tests/bats/                # Bash test suite
bats plugins/tcs-git-helpers/tests/integration/         # Integration bats
pytest plugins/tcs-git-helpers/tests/python/            # Python tests
pytest plugins/tcs-git-helpers/tests/e2e/               # E2E tests (where applicable)

# Quality
shellcheck plugins/tcs-git-helpers/templates/githooks/* \
           plugins/tcs-git-helpers/scripts/**/*.sh \
           plugins/tcs-git-helpers/skills/git-setup/lib/*.sh

# CI gate (NEW — created in Phase 3)
plugins/tcs-git-helpers/scripts/ci/check-hook-bundle-version.sh

# Reinstall hooks in a target repo
/tcs-git-helpers:git-setup    # invokes install_files.sh
```

---

## Implementation Phases

Each phase is defined in a separate file. Tasks follow red-green-refactor: **Prime** (understand context), **Test** (red), **Implement** (green), **Validate** (refactor + verify).

> **Tracking Principle**: Track logical units that produce verifiable outcomes. The TDD cycle is the method, not separate tracked items.

- [x] [Phase 1: Self-contained hook bundle](phase-1.md)
- [ ] [Phase 2: Skill-side drift check + cmd_cleanup refresh](phase-2.md)
- [ ] [Phase 3: CI maintainer-contract gate + E2E lockdown](phase-3.md)

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

## PRD Acceptance Criterion → Phase mapping

Every PRD AC maps to one or more phase tasks. Cross-reference for traceability:

| PRD Feature | Acceptance Criterion | Phase | Task(s) |
|---|---|---|---|
| F1 — post-merge writes cache | hook writes cache w/o env vars | 1 | T1.1, T1.2, T1.4, T1.5 |
| F1 — graceful degrade on no-gh | structured stderr on guards | 1 | T1.2, T1.5 |
| F2 — cleanup matches git reality | live refresh in cmd_cleanup | 2 | T2.3, T2.6 |
| F2 — gh-unauth fallback | fallback path emits message | 2 | T2.3 |
| F3 — version updates propagate | drift surfaces via skill | 2 | T2.3, T2.4 |
| F3 — re-run git-setup updates all four | atomic install | 1 | T1.4, T3.3 |
| F4 — skill checks installed version | drift_check used at invocation | 2 | T2.1, T2.2, T2.3, T2.4 |
| F4 — silent on happy path | drift_check returns OK silently | 2 | T2.1, T2.2 |
| F4 — distinct "not installed" message | MISSING branch wording | 2 | T2.1, T2.2 |
| F5 — silent failures eliminated | structured stderr one-liners | 1 | T1.1 (helper), T1.2 (callers) |
| F5 — exit 0 always | preserved in all hook paths | 1 | T1.2, T1.5 |
| F6 — one versioned bundle | single tcs-git-helpers-version file installed | 1 | T1.3, T1.4 |
| F6 — CI enforces version bump | check-hook-bundle-version.sh | 3 | T3.1, T3.2 |
