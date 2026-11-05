---
title: "prompt-author: write, audit, port and measure LLM prompts beyond skills and agents"
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

PRD references use `PRD/F<n>` plus a short quote of the acceptance criterion, because the PRD's criteria are not numbered.

---

## Context Priming

*GATE: Read all files in this section before starting any implementation.*

**Specification**:

- `docs/XDD/specs/023-prompt-author/requirements.md` - Product Requirements (approved 2026-11-05)
- `docs/XDD/specs/023-prompt-author/solution.md` - Solution Design (approved 2026-11-05)
- `docs/XDD/specs/023-prompt-author/research-internal.md` - file:line of every rule copy that migrates
- `docs/XDD/specs/023-prompt-author/research-technical.md` - lint false-alarm data, security requirements 1-11
- `docs/XDD/specs/023-prompt-author/research-corpus.md` - 16-prompt corpus (audit recall set)
- `docs/XDD/specs/023-prompt-author/research-external.md` - vendor sources for evidence grades and profiles
- `docs/XDD/specs/023-prompt-author/experiment/results.md` and `experiment/harness/` - measured modes; runner origin
- `plugins/tcs-helper/skills/skill-author/reference/plugin-evals.md` - case layout, proving signal

**Key Design Decisions**:

- **SDD-ADR-1**: Catalog lives in `plugins/tcs-helper/skills/prompt-author/reference/catalog/`. Consumers link `../prompt-author/…` (the model-ladder precedent).
- **SDD-ADR-2**: Stable `PA-NN` IDs plus a fingerprint test. A copied rule or a dead ID fails `tests/tcs-helper/test_prompt_catalog.py`.
- **SDD-ADR-3**: Two eval routes share one kit format: `plugin eval` at two git states via `eval_compare.py`, and `prompt_eval.py` on `claude -p` / Ollama.
- **SDD-ADR-4**: Migration writes the eval case first, proves its signal, then corrects. A regression reverts that rule group for that skill.
- **SDD-ADR-5 / SDD-ADR-7**: Lint E1–E4 and W1–W3 are calibrated on the repo. The judge is configurable (`prompt_eval_judge` in startup.toml, default `claude:haiku`) and validated by labels (≥8 decided, ≥85%).

**Implementation Context**:

```bash
# Testing (CI: .github/workflows/tests.yml, ubuntu + macOS, py3.11)
pytest -q -rs                                    # all python tests
pytest -q tests/tcs-helper -k prompt             # this spec's tests

# Quality
python3 plugins/tcs-helper/skills/prompt-author/scripts/prompt_lint.py --repo   # from Phase 1

# Evals (always --no-publish and a cost ceiling)
claude plugin eval plugins/tcs-helper --case '<glob>' --runs 3 --trust-plugin --no-publish --max-cost-usd 5

# Local skill testing (CLAUDE.md procedure; copy prompt-author too from Phase 3 on)
cp -r plugins/tcs-helper/skills/<skill> ~/.claude/plugins/cache/the-custom-startup/tcs-helper/*/skills/
cp -r plugins/tcs-helper/skills/<skill> ~/.claude/plugins/marketplaces/the-custom-startup/plugins/tcs-helper/skills/
```

---

## Implementation Phases

Each phase is defined in a separate file. Tasks follow red-green-refactor: **Prime** (understand context), **Test** (red), **Implement** (green), **Validate** (refactor + verify).

> **Tracking Principle**: Track logical units that produce verifiable outcomes. The TDD cycle is the method, not separate tracked items.

- [ ] [Phase 1: Catalog, Lint and Single-Source Test](phase-1.md)
- [ ] [Phase 2: prompt-author Skill and Eval Runners](phase-2.md)
- [ ] [Phase 3: Measured Migration of the Authoring Skills](phase-3.md)
- [ ] [Phase 4: Write-Time Nudge, Install Check and End-to-End Validation](phase-4.md)

---

## Plan Verification

Before this plan is ready for implementation, verify:

| Criterion | Status |
|-----------|--------|
| A developer can follow this plan without additional clarification | ✅ |
| Every task produces a verifiable deliverable | ✅ |
| All PRD acceptance criteria map to specific tasks | ✅ (traceability table in phase-4.md) |
| All SDD components have implementation tasks | ✅ C1 T1.1/T1.2, C2 T2.4, C3 T1.3, C4 T2.1–T2.3, C5 T1.4, C6 Phase 3, C7 T4.1 |
| Dependencies are explicit with no circular references | ✅ |
| Parallel opportunities are marked with `[parallel: true]` | ✅ |
| Each task has specification references `[ref: ...]` | ✅ |
| Project commands in Context Priming are accurate | ✅ |
| All phase files exist and are linked from this manifest as `[Phase N: Title](phase-N.md)` | ✅ |
