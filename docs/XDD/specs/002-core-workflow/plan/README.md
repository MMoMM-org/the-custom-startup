---
title: "M1 — Core Workflow Rebuild"
spec: "002-core-workflow"
status: draft
version: "1.0"
---

# Implementation Plan

## Validation Checklist

### CRITICAL GATES (Must Pass)

- [x] All `[NEEDS CLARIFICATION]` markers addressed
- [x] All specification file paths correct and exist
- [x] Each phase follows TDD: Prime → Test → Implement → Validate
- [x] Every task has verifiable success criteria
- [x] A developer could follow this plan independently

### QUALITY CHECKS (Should Pass)

- [x] Context priming section complete
- [x] All implementation phases defined with linked phase files
- [x] Dependencies between phases explicit (no circular dependencies)
- [x] Parallel work tagged with `[parallel: true]`
- [x] Activity hints provided for specialist selection
- [x] Every phase references relevant SDD sections
- [x] Integration & E2E tests defined in final phase
- [x] Project commands match actual project setup

---

## Context Priming

*GATE: Read all files in this section before starting any implementation.*

**Specification**:
- `.start/specs/002-core-workflow/requirements.md` — PRD (17 must-have features, personas, acceptance criteria)
- `.start/specs/002-core-workflow/solution.md` — SDD (directory map, skill contracts, ADRs, startup.toml schema)
- `plugins/tcs-start/skills/brainstorm/SKILL.md` — reference skill structure (PICS format, frontmatter)
- `plugins/tcs-start/skills/implement/SKILL.md` — skill being enhanced in Phase 4
- `plugins/tcs-start/skills/specify-meta/SKILL.md` — skill being renamed/updated in Phase 2

**Key Design Decisions**:
- **ADR-1**: Plugin rename via `git mv` — preserves history; all `/tcs-start:*` become `/tcs-workflow:*`
- **ADR-2**: startup.toml G/R scope — `~/.claude/startup.toml` (global) overridden by `.claude/startup.toml` (repo); default `docs_base = "docs/XDD"`
- **ADR-3**: tdd-guardian in `plugins/tcs-workflow/agents/` — self-contained in workflow plugin
- **ADR-4**: guide reads live git + plan files (bash-first) + memory hint for session recovery
- **ADR-5**: one-time migration of `.start/specs/` → `docs/XDD/specs/` in Phase 1; no legacy fallback

**Skill/Agent authoring rules**:
- All new/modified **skills** → authored via `/tcs-helper:skill-author`
- All new/modified **agents** → authored via `/plugin-dev:agent-creator`
- No hand-crafting SKILL.md or agent markdown outside these workflows

**Implementation Commands**:
```bash
# Python tests (tcs-helper scripts)
source venv/bin/activate && python3 -m pytest tests/tcs-helper/ -q

# Plugin reinstall after rename
./install.sh

# Tool availability check (required by skills)
command -v rg && command -v fd && command -v fzf || echo "Install: brew install ripgrep fd fzf"
```

---

## Implementation Phases

Each phase is defined in a separate file. Tasks follow: **Prime** (context) → **Test** (RED) → **Implement** (GREEN) → **Validate** (REFACTOR + verify).

> **Dependency order**: Phase 1 must complete before all others. Phases 2+3 can run in parallel after Phase 1. Phase 4 requires Phase 3. Phase 5 requires Phases 2+4. Phase 6 requires all.

- [ ] [Phase 1: Foundation](phase-1.md)
- [ ] [Phase 2: XDD Skill Family Renames](phase-2.md)
- [ ] [Phase 3: TDD Enforcement Core](phase-3.md)
- [ ] [Phase 4: Core Orchestration](phase-4.md)
- [ ] [Phase 5: Parallel Skills Expansion](phase-5.md)
- [ ] [Phase 6: Integration & Validation](phase-6.md)

---

## Plan Verification

| Criterion | Status |
|-----------|--------|
| A developer can follow this plan without additional clarification | ✅ |
| Every task produces a verifiable deliverable | ✅ |
| All PRD acceptance criteria map to specific tasks | ✅ |
| All SDD components have implementation tasks | ✅ |
| Dependencies are explicit with no circular references | ✅ |
| Parallel opportunities marked with `[parallel: true]` | ✅ |
| Each task has specification references `[ref: ...]` | ✅ |
| Project commands in Context Priming are accurate | ✅ |
| All phase files exist and linked as `[Phase N: Title](phase-N.md)` | ✅ |
