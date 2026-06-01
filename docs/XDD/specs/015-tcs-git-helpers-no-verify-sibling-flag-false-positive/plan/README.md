---
title: "NO_VERIFY rule: stop false-positives on sibling-command flags"
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

### Deviation Protocol
When implementation requires changes from the specification: document the deviation with rationale,
obtain approval before proceeding, update the SDD if the deviation improves the design, and record
it in the Deviations table below.

| Date | Deviation | Rationale | Approved |
|------|-----------|-----------|----------|
| — | — | — | — |

## Metadata Reference
- `[parallel: true]` — Tasks that can run concurrently
- `[ref: document/section]` — Links to specifications
- `[activity: type]` — Activity hint for specialist agent selection

### Success Criteria
**Validate** = Process verification ("did we follow TDD?"). **Success** = Outcome verification ("does it work?").

---

## Context Priming

*GATE: Read all files in this section before starting any implementation.*

**Specification**:
- `docs/XDD/specs/015-tcs-git-helpers-no-verify-sibling-flag-false-positive/requirements.md` — Product Requirements
- `docs/XDD/specs/015-tcs-git-helpers-no-verify-sibling-flag-false-positive/solution.md` — Solution Design

**Source under change**:
- `plugins/tcs-git-helpers/scripts/lib/pattern_match.sh` — add `_match_no_verify`; `PATTERN_NO_VERIFY` stays byte-identical
- `plugins/tcs-git-helpers/scripts/block-bad-git-ops.sh` — swap NO_VERIFY dispatch line
- `plugins/tcs-git-helpers/tests/bats/lib_pattern_match.bats` — unit tests
- `plugins/tcs-git-helpers/tests/bats/block-bad-git-ops.bats` — dispatcher regression tests
- `plugins/tcs-git-helpers/tests/fixtures/commands/bypass_corpus.txt` — corpus (already has one NO_VERIFY case)

**Key Design Decisions**:
- **ADR-1** Per-clause matching — split the stripped command on shell separators, run the unchanged `PATTERN_NO_VERIFY` per clause so `.*` cannot bridge into a sibling command.
- **ADR-2** `PATTERN_NO_VERIFY` byte-identical — fix lives in the new helper + dispatch line only; add a pointer comment from the constant to the helper.
- **ADR-3** Separators `&&  ||  |  ;  &  newline`; pure-bash ordered parameter substitution (two-char operators before single-char); here-string `read` loop.

**Implementation Context**:
```bash
# Testing
bats plugins/tcs-git-helpers/tests/bats/                 # unit + dispatcher tests
bash plugins/tcs-git-helpers/tests/e2e/dogfood.sh        # end-to-end scenarios

# Quality
shellcheck plugins/tcs-git-helpers/scripts/lib/pattern_match.sh \
           plugins/tcs-git-helpers/scripts/block-bad-git-ops.sh

# Release
# plugin.json / marketplace.json version bumps are AUTOMATIC on merge to main
# (.github/workflows/auto-bump-versions.yml). Do NOT hand-bump. CHANGELOG is manual.
```

---

## Implementation Phases

Each phase is defined in a separate file. Tasks follow red-green-refactor: **Prime**, **Test** (red), **Implement** (green), **Validate** (refactor + verify).

- [ ] [Phase 1: Sibling-isolation fix (TDD)](phase-1.md)
- [ ] [Phase 2: Release notes & full verification](phase-2.md)

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
| All phase files exist and are linked from this manifest | ✅ |
