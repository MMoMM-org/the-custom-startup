---
title: "Satori Documentation"
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
- `docs/XDD/specs/007-satori-docs/requirements.md` — Product Requirements (personas, journeys, features F1–F5, ACs)
- `docs/XDD/specs/007-satori-docs/solution.md` — Solution Design (4 ADRs, content model per file, cross-document link map, gotchas)

**Source of Truth Files** (ADR-2: read before writing any tool or config documentation):
- `modules/satori/src/tools/satori-context.ts` — `satori_context` Zod schema
- `modules/satori/src/tools/satori-manage.ts` — `satori_manage` Zod schema (10 sub-commands)
- `modules/satori/src/tools/satori-find.ts` — `satori_find` Zod schema
- `modules/satori/src/tools/satori-schema.ts` — `satori_schema` Zod schema
- `modules/satori/src/tools/satori-exec.ts` — `satori_exec` Zod schema
- `modules/satori/src/tools/satori-kb.ts` — `satori_kb` Zod schema (3 sub-commands)
- `modules/satori/src/execution/builtin-server.ts` — `bash` builtin tools (run/run_file/batch)
- `modules/satori/src/execution/runtime.ts` — Language union type (11 languages)
- `modules/satori/src/config/schema.ts` — All satori.toml fields
- `modules/satori/satori.toml.example` — Config example with comments
- `modules/satori/hooks/hooks.json` — Actual hook definitions

**Key Design Decisions**:
- **ADR-1**: 5 files in `modules/satori/docs/` — getting-started.md, configuration.md, tools.md, concepts.md, hooks.md
- **ADR-2**: Zod schemas + config schema are authoritative — never recall parameters from memory
- **ADR-3**: README updated in-place — add satori_kb, Documentation section, correct tool count
- **ADR-4**: `bash` builtin fully documented (implemented); Kairn = brief "Planned Extensions" mention only

**Implementation Context**:

```bash
# Verify docs directory created
ls modules/satori/docs/

# Verify no [NEEDS CLARIFICATION] markers remain
grep -r "NEEDS CLARIFICATION" modules/satori/docs/ 2>/dev/null

# Verify all 6 satori_* tools documented in tools.md
grep "^## \`satori_" modules/satori/docs/tools.md | wc -l  # expect: 6

# Verify bash builtin section exists
grep -c "bash" modules/satori/docs/tools.md  # expect: > 0

# Verify README updated
grep "satori_kb" modules/satori/README.md  # expect: match
grep "docs/getting-started" modules/satori/README.md  # expect: match

# Verify all cross-document links resolve
grep -rn "](docs/" modules/satori/ --include="*.md"
```

---

## Implementation Phases

Each phase follows red-green-refactor: **Prime** (understand context), **Test** (verify expected content), **Implement** (write the file), **Validate** (check accuracy and completeness).

- [x] [Phase 1: Foundation and Concepts](phase-1.md)
- [x] [Phase 2: Reference Layer](phase-2.md)
- [x] [Phase 3: Getting Started, README, and Validation](phase-3.md)

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
