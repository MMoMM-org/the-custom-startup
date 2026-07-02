---
title: "rule-enforcer Batch/Extraction Mode — Implementation Plan"
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
| specId | 016-rule-enforcer-claude-md-sweep |
| title | rule-enforcer Batch/Extraction Mode |
| status | IN_REVIEW |
| totalTasks | 16 |
| parallelTasks | 5 |
| specReferences | 30+ |
| clarificationsRemaining | 0 |

---

## Specification Compliance Guidelines

### How to Ensure Specification Adherence

1. **Before Each Phase**: Read the phase Context Gate (SDD sections + ADRs).
2. **During Implementation**: Reference the cited SDD sections in each task.
3. **After Each Task**: Run the task's Validate step (self-tests, skill-author audit).
4. **Phase Completion**: Verify all cited PRD acceptance criteria are met.

### Deviation Protocol

When implementation requires changes from the specification:
1. Document the deviation with clear rationale.
2. Obtain approval before proceeding.
3. Update SDD when the deviation improves the design.
4. Record all deviations in the relevant phase file for traceability.

## Metadata Reference

- `[parallel: true]` — Tasks that can run concurrently
- `[ref: document/section]` — Links to specifications
- `[activity: type]` — Activity hint for specialist agent selection

---

## Context Priming

*GATE: Read all files in this section before starting any implementation.*

**Specification**:
- `docs/XDD/specs/016-rule-enforcer-claude-md-sweep/requirements.md` — Product Requirements
- `docs/XDD/specs/016-rule-enforcer-claude-md-sweep/solution.md` — Solution Design (6 ADRs)

**Existing code to extend / reuse (read before touching)**:
- `plugins/tcs-helper/skills/rule-enforcer/SKILL.md` — the skill being extended
- `plugins/tcs-helper/skills/rule-enforcer/reference/mechanism-matrix.md` — SSOT (do not fork)
- `plugins/tcs-helper/skills/rule-enforcer/reference/examples.md` — parity-test corpus
- `plugins/tcs-helper/skills/rule-enforcer/test_examples_md.sh` — self-test pattern to mirror
- `plugins/tcs-helper/skills/memory-claude-md-optimize/SKILL.md` — pointer insertion target
- `plugins/tcs-git-helpers/hooks/hooks.json`, `plugins/tcs-git-helpers/scripts/*.sh` — dedup source

**Key Design Decisions** (from SDD):
- **ADR-1** Dual-mode dispatch via explicit flag (`--scan` / `--from-file`); interactive path untouched.
- **ADR-2** Skip Q1; Q2 becomes a filter (judgment-only → guidance list, no per-line memory-add).
- **ADR-3** Reuse Step 8 hand-off verbatim by pre-filling `Candidate ≅ TriageState`.
- **ADR-4** Emit bare-label Q3 strings coupled to matrix headings + self-test.
- **ADR-5** Dedup: live inspection authoritative, catalog is a hint layer; key = mechanism+target-pattern.
- **ADR-6** Optimizer→batch pointer is one-directional text, no back-call.

**Implementation Context** (project commands — skill repo, bash/bats based):
```bash
# Self-tests (bash 3.2 compatible — repo guardrail)
bash plugins/tcs-helper/skills/rule-enforcer/test_examples_md.sh
bash plugins/tcs-helper/skills/rule-enforcer/test_batch_q3_labels.sh     # NEW (Phase 1)
# Bats suites (run with sandbox disabled — see memory: bats mktemp false-failures)
bats plugins/tcs-helper/tests/bats/                                       # if present
# Quality
shellcheck plugins/tcs-helper/skills/rule-enforcer/*.sh
# Skill audit before commit (project rule — feedback_skill-author-on-creation)
#   Skill(tcs-helper:skill-author) audit on the modified rule-enforcer skill
# Release (no manual marketplace/cache sync — feedback_no-manual-marketplace-sync)
#   bump plugins/tcs-helper/plugin.json version, then push
```

---

## Implementation Phases

Each phase is defined in a separate file. Tasks follow red-green-refactor: **Prime** (understand context), **Test** (red), **Implement** (green), **Validate** (refactor + verify).

> **Tracking Principle**: Track logical units that produce verifiable outcomes. The TDD cycle is the method, not separate tracked items.

- [ ] [Phase 1: Foundation — reference files, ADR, label-drift self-test](phase-1.md)
- [ ] [Phase 2: Batch mode in SKILL.md + parity & security tests](phase-2.md)
- [ ] [Phase 3: Optimizer integration, dogfood E2E, audit & release](phase-3.md)

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
| All phase files exist and are linked as `[Phase N: Title](phase-N.md)` | ✅ |
