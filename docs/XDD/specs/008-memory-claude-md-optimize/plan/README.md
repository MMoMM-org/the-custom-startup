---
title: "memory-claude-md-optimize: Implementation Plan"
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
- [x] All phase files exist and are linked from this manifest as `[Phase N: Title](phase-N.md)`

---

## Specification Compliance Guidelines

### Deviation Protocol

When implementation requires changes from the specification:
1. Document the deviation with clear rationale
2. Obtain approval before proceeding
3. Update SDD when the deviation improves the design
4. Record all deviations in this plan for traceability

## Metadata Reference

- `[parallel: true]` - Tasks that can run concurrently
- `[ref: document/section; lines: 1, 2-3]` - Links to specifications
- `[activity: type]` - Activity hint for specialist agent selection

### Success Criteria

**Validate** = Process verification ("did we follow TDD?")
**Success** = Outcome verification ("does it work correctly?")

---

## Context Priming

*GATE: Read all files in this section before starting any implementation.*

**Specification**:
- `docs/XDD/specs/008-memory-claude-md-optimize/requirements.md` - Product Requirements
- `docs/XDD/specs/008-memory-claude-md-optimize/solution.md` - Solution Design

**Key Design Decisions**:
- **ADR-1**: Pure Skill Architecture — single SKILL.md with reference docs, no Python helpers. Claude uses Read/Write/Glob/Grep/Bash directly.
- **ADR-2**: Rubric-Guided LLM Categorization — reference doc provides category definitions and signals; Claude applies judgment to classify.
- **ADR-3**: In-Place Suffixed Backups — `.backup-YYYYMMDD-HHMMSS` next to originals.
- **ADR-4**: Non-Blocking Secret Detection — warn in report, don't block operations.

**Existing Patterns to Follow**:
- `plugins/tcs-helper/skills/memory-add/SKILL.md` — skill structure, frontmatter, categorization signals
- `plugins/tcs-helper/skills/memory-cleanup/SKILL.md` — audit + propose + execute pattern
- `plugins/tcs-helper/skills/memory-sync/SKILL.md` — structural integrity checks
- `plugins/tcs-helper/templates/routing-reference.md` — Memory Bank routing rules
- `plugins/tcs-helper/templates/memory-*.md` — category file templates

**Implementation Context**:
```bash
# Quality (skill files are markdown — no build/test commands)
/skill-author audit    # Validates skill structure, frontmatter, quality

# Manual validation
# Invoke /memory-claude-md-optimize in a Claude Code session
# Test with --dry-run flag first
```

---

## Implementation Phases

Each phase is defined in a separate file. Tasks follow red-green-refactor: **Prime** (understand context), **Test** (red), **Implement** (green), **Validate** (refactor + verify).

> **Tracking Principle**: Track logical units that produce verifiable outcomes. The TDD cycle is the method, not separate tracked items.

- [ ] [Phase 1: Reference Documents](phase-1.md)
- [ ] [Phase 2: Core Skill Workflow](phase-2.md)
- [ ] [Phase 3: Integration & Validation](phase-3.md)

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
