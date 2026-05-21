---
title: "Rule Enforcer Skill + Phrase Intercept Hook"
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

1. Document the deviation in the affected phase file with clear rationale.
2. Obtain approval before proceeding.
3. Update SDD when the deviation improves the design.
4. Record all deviations in the affected phase for traceability.

## Metadata Reference

- `[parallel: true]` — Tasks that can run concurrently
- `[ref: document/section]` — Links to PRD / SDD
- `[activity: type]` — Activity hint for specialist agent selection

### Success Criteria

**Validate** = Process verification ("did we follow TDD?")
**Success** = Outcome verification ("does it work correctly?")

---

## Context Priming

*GATE: Read all files in this section before starting any implementation.*

**Specification**:

- `docs/XDD/specs/013-rule-enforcer/requirements.md` — PRD (7 Must + 2 Should + 2 Could)
- `docs/XDD/specs/013-rule-enforcer/solution.md` — SDD (8 confirmed ADRs)
- `docs/XDD/ideas/2026-05-21-rule-enforcer.md` — original brainstorm

**Key Design Decisions (from SDD)**:

- **ADR-1**: Mechanism matrix lives in `reference/mechanism-matrix.md`, lazy-loaded at triage step 6
- **ADR-2**: Pre-push scaffolding produces standalone snippets in repo's `.githooks/` (NOT integrated with tcs-git-helpers bundle)
- **ADR-3**: No override-persistence in v1 — triage decisions live only in conversation context
- **ADR-4**: Hook script in Python 3 (matches `capture_learning.py` precedent)
- **ADR-5**: Trigger phrases stored as markdown with code-fenced regex per language
- **ADR-6**: No analytics / persistence layer in v1
- **ADR-7**: M6 inline scaffolding = preview + AskUserQuestion + Write tool (per PRD W1)
- **ADR-8**: Hook registered by appending to existing `plugins/tcs-helper/hooks/hooks.json` UserPromptSubmit array

**Precedent files (READ before starting Phase 1)**:

- `plugins/tcs-helper/scripts/capture_learning.py` — direct precedent for hook structure
- `plugins/tcs-helper/hooks/hooks.json` — registration target
- `plugins/tcs-helper/skills/skill-author/SKILL.md` + `reference/conventions.md` — skill structure
- `.github/workflows/auto-bump-versions.yml` + `scripts/ci/auto-bump-versions.sh` — CI scaffold template source
- `plugins/tcs-helper/skills/memory-add/SKILL.md` — hand-off target

**Implementation Context**:

```bash
# Hook test (any phase)
echo '{"prompt":"I keep forgetting X","cwd":"'$PWD'"}' \
  | python3 plugins/tcs-helper/scripts/intercept_rule_recurrence.py

# Skill test (any phase) — manual via Claude Code session
# Restart session after Phase 2 to pick up the new skill, then:
# /enforce-rule "test rule description"

# Plugin discovery refresh
# Skills are indexed at Claude Code startup — start a fresh session after Phase 2 + Phase 3
```

---

## Implementation Phases

- [ ] [Phase 1: Intercept Hook Foundation](phase-1.md)
- [ ] [Phase 2: Triage Skill + Hand-offs](phase-2.md)
- [ ] [Phase 3: Inline Templates + Self-Test + Docs](phase-3.md)

---

## Plan Verification

| Criterion | Status |
|-----------|--------|
| A developer can follow this plan without additional clarification | ✅ |
| Every task produces a verifiable deliverable | ✅ |
| All PRD acceptance criteria map to specific tasks | ✅ (mapping in each phase) |
| All SDD components have implementation tasks | ✅ |
| Dependencies are explicit with no circular references | ✅ (Phase 1 → 2 → 3 sequential; parallel within phases marked) |
| Parallel opportunities are marked with `[parallel: true]` | ✅ |
| Each task has specification references `[ref: ...]` | ✅ |
| Project commands in Context Priming are accurate | ✅ |
| All phase files exist and are linked from this manifest | ✅ |

---

## PRD Acceptance Criteria → Task Mapping

| PRD Feature | AC count | Tasks |
|-------------|----------|-------|
| M1 — UserPromptSubmit intercept hook | 4 | T1.1, T1.2, T1.3 |
| M2 — `/enforce-rule` slash command | 3 | T2.1 |
| M3 — 4-question triage logic | 5 | T2.3 |
| M4 — Mechanism matrix routing | 8 | T2.2, T2.3 |
| M5 — Hand-off to existing author skills | 4 | T2.4 |
| M6 — Inline scaffolding for 2 templates | 3 | T3.1, T3.2 |
| M7 — Self-test fixtures (3 cases) | 4 | T3.3 |
| S1 — Externalized trigger-phrase config | 2 | T1.1 |
| S2 — Worked examples in reference | 1 | T2.5 |
