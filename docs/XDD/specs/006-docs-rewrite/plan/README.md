---
title: "TCS v2 Documentation Rewrite"
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

## Context Priming

*GATE: Read all files in this section before starting any implementation.*

**Specification**:
- `docs/XDD/specs/006-docs-rewrite/requirements.md` — Product Requirements
- `docs/XDD/specs/006-docs-rewrite/solution.md` — Solution Design (ADRs, directory map, link map)
- `docs/XDD/ideas/2026-03-28-docs-rewrite.md` — Brainstorm context and attribution counts

**Key Design Decisions**:
- **ADR-1**: 4-subdir IA — `getting-started/` · `reference/` · `guides/` · `about/` — old flat paths will be deleted
- **ADR-2**: Clean delete — no symlinks or redirects; git history is the migration trail
- **ADR-3**: CHANGELOG.md at repo root (not inside docs/)
- **ADR-4**: SKILL.md as source of truth — every skill description must be read from the actual file, never recalled

**Implementation Context**:

```bash
# Verify no stale plugin references remain (run after each phase)
grep -r "tcs-start" docs/ README.md --include="*.md" 2>/dev/null

# Check for broken internal links (manual scan)
grep -rn "](docs/" docs/ README.md --include="*.md" | grep -v "XDD\|ai/\|templates/"

# Verify structure after Phase 5
ls docs/            # should show only: getting-started/ reference/ guides/ about/ XDD/ ai/ templates/
ls docs/reference/  # should show: skills.md plugins.md agents.md output-styles.md xdd.md
```

---

## Implementation Phases

Each phase is defined in a separate file. Tasks follow red-green-refactor: **Prime** (understand context), **Test** (verify expected content), **Implement** (write the file), **Validate** (check for accuracy and completeness).

> **Tracking Principle**: "Test" for documentation tasks means: verify the source material exists and is readable, and write down what the output should contain. "Implement" means write the file. "Validate" means check it against the acceptance criteria.

- [ ] [Phase 1: Foundation and Getting Started](phase-1.md)
- [ ] [Phase 2: Reference Layer](phase-2.md)
- [ ] [Phase 3: Workflow and Patterns](phase-3.md)
- [ ] [Phase 4: About Section](phase-4.md)
- [ ] [Phase 5: README, Cleanup, and Validation](phase-5.md)

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
| All phase files exist and are linked from this manifest as `[Phase N: Title](phase-N.md)` | ✅ |
