---
title: "tcs-patterns selective install"
status: draft
version: "1.0"
---

# Implementation Plan

## Validation Checklist

### CRITICAL GATES (Must Pass)

- [x] All clarification markers have been addressed
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
| specId | 020-tcs-patterns-selective-install |
| title | tcs-patterns selective install |
| status | IN_REVIEW |
| totalTasks | 29 |
| parallelTasks | 6 |
| specReferences | 155 |
| clarificationsRemaining | 0 |

### PhaseStatus

| Phase | Name | Status | Tasks | File |
|-------|------|--------|-------|------|
| 1 | The catalogue and its maintainer contract | COMPLETED | 5 (5 done) | [phase-1.md](phase-1.md) |
| 2 | Detection, fixtures before rules | COMPLETED | 7 (7 done) | [phase-2.md](phase-2.md) |
| 3 | The install path | COMPLETED | 6 (6 done) | [phase-3.md](phase-3.md) |
| 4 | Drift and the advisory | COMPLETED | 4 (4 done) | [phase-4.md](phase-4.md) |
| 5 | The skills, the docs, end to end | IN_PROGRESS | 7 (5 done) | [phase-5.md](phase-5.md) |

Every row of this table read `IN_PROGRESS` until 2026-10-05, including Phase 1, which had been
`completed` in its own frontmatter since the day it shipped. The Tasks column was wrong too --
Phase 2 was listed at 6 and has 7. So the table was a template artefact that had never been
maintained, and a table whose every row is wrong is worse than no table: it reads as a status
surface. It is now filled from each phase file's own `status:` frontmatter and its own task
checkboxes, which are the authority. Re-derive it from those two sources rather than editing a
row by hand.

`totalTasks` read 26 while the five phase files held 27 checkboxes (5 + 7 + 6 + 4 + 5), so
that figure was stale too. Re-counted 2026-10-06, when T5.1a made it 28.

---

## Specification Compliance Guidelines

1. **Before each phase**: read every file in that phase's Phase Context gate.
2. **During implementation**: each task names the SDD section that specifies it; build what that
   section says, not what seems reasonable.
3. **After each task**: the Success line is the check, and it cites the criterion it satisfies.
4. **Phase completion**: the phase's final validation task runs both test legs and the relevant
   gates.

### Deviation Protocol

The SDD was written against measurements, so a deviation usually means a measurement was wrong —
which is worth knowing. Document it, get approval before proceeding, update the SDD when the
deviation improves the design, and record it in the phase file. Do not silently diverge: three
figures in this spec were already corrected once because they were stated more precisely than they
had been measured.

## Metadata Reference

- `[parallel: true]` — can run concurrently with its siblings
- `[ref: doc/section]` — links to the specification section that governs the task
- `[activity: type]` — hint for specialist selection

### Success Criteria

**Validate** = process verification ("did we follow TDD?").
**Success** = outcome verification ("does it work correctly?").

---

## Context Priming

*GATE: Read all files in this section before starting any implementation.*

**Specification**:

- `docs/XDD/specs/020-tcs-patterns-selective-install/requirements.md` — the problem, ten Must
  features, 36 acceptance criteria, the scan's business rules and edge cases
- `docs/XDD/specs/020-tcs-patterns-selective-install/solution.md` — components, directory map, the
  four file formats, the traced gating walkthrough, and Implementation Gotchas
- `docs/XDD/specs/012-tcs-git-helpers-hook-runtime-contract/solution.md` — the bundle-versioning
  pattern this follows at a finer grain

**Key Design Decisions**:

- **ADR-1**: an installed pattern is named `tcs-<pattern>`. A skill registers under its frontmatter
  `name:`, not its directory, so the installer rewrites that line and raises if it is missing —
  otherwise the prefix is silently defeated.
- **ADR-2**: detector and installer in Python; the only new shell is one advisory segment and one
  CI-gate rule, both inside existing scripts.
- **ADR-3**: one `VERSION` integer per pattern directory, no central catalogue file — which is what
  lets the CI gate be a per-directory membership test with no parsing.
- **ADR-4**: the manifest records a SHA-256 of the installed `SKILL.md`, so `update` can overwrite
  exactly when it is uninteresting. The hash covers `SKILL.md` only, deliberately.
- **ADR-7**: the Obsidian rule stays duplicated between the bash hook and the Python detector, with
  a test asserting the two agree over the detection fixtures.
- **ADR-9**: the existing multi-bundle CI gate gains a per-pattern rule; no new script, no new
  workflow.

**Implementation Context**:

```bash
# Tests — discovered from pytest.ini and plugins/*/tests/bats
python3 -m pytest -q                               # full suite, perf deselected
python3 -m pytest tests/test_patterns_detect.py -q # this spec's detection suite
bats plugins/tcs-helper/tests/bats                 # bats legs
bats plugins/tcs-git-helpers/tests/bats

# Gates runnable locally — run before pushing, not after CI complains
plugins/tcs-git-helpers/scripts/ci/check-hook-bundle-version.sh "origin/main..HEAD"
scripts/ci/check-docs-sync.sh
scripts/ci/check-changelog-version-sync.sh

# Inspection
python3 scripts/observability/report.py            # walks the real tree; verifies the relocation
claude plugin validate plugins/tcs-patterns        # smoke only: does NOT validate skill frontmatter
```

Two standing constraints that bite in this repository: `bats setup()`'s `mktemp -d` fails under the
Bash sandbox, so re-run with the sandbox disabled before treating a bats failure as real; and CI
must be read **per leg**, never from the run's verdict — a green aggregate hid a red Linux leg for
four days in the previous spec.

---

## Implementation Phases

Each phase is defined in a separate file. Tasks follow red-green-refactor: **Prime** (understand
context), **Test** (red), **Implement** (green), **Validate** (refactor + verify).

> **Tracking Principle**: Track logical units that produce verifiable outcomes. The TDD cycle is
> the method, not separate tracked items.

- [x] [Phase 1: The catalogue and its maintainer contract](phase-1.md)
- [x] [Phase 2: Detection, fixtures before rules](phase-2.md)
- [x] [Phase 3: The install path](phase-3.md)
- [x] [Phase 4: Drift and the advisory](phase-4.md)
- [ ] [Phase 5: The skills, the docs, end to end](phase-5.md)

### Why this order

Phase 1 first because every other component reads the catalogue, and because the relocation is the
only change whose verification needs a fresh session or the inventory walk — the plugin cache is
stale inside the session that updated it.

Phase 2 next and alone: the detector depends on nothing but the catalogue's name list, its fixtures
are synthetic, and it is the PRD's answer to its own top risk. Building it before any installer
exists keeps it honest — there is nothing to run it against except fixtures.

Phase 3 needs the catalogue (source), the guard (which must refuse before any write) and the
manifest (which the installer writes). Phase 4 needs the manifest format and the `VERSION` files.
Phase 5 is last because the interview is only usable once detection and installation both exist,
and because end-to-end verification needs all of it.

---

## Plan Verification

| Criterion | Status |
|-----------|--------|
| A developer can follow this plan without additional clarification | ✅ |
| Every task produces a verifiable deliverable | ✅ |
| All PRD acceptance criteria map to specific tasks | ✅ |
| All SDD components have implementation tasks | ✅ C1→P1, C2→P2, C4/C5/C6→P3, C7→P4, C3/C8→P5, C9→P1 |
| Dependencies are explicit with no circular references | ✅ |
| Parallel opportunities are marked with `[parallel: true]` | ✅ 6 tasks |
| Each task has specification references `[ref: ...]` | ✅ |
| Project commands in Context Priming are accurate | ✅ discovered from pytest.ini, bats dirs, scripts/ci/ |
| All phase files exist and are linked from this manifest | ✅ |
