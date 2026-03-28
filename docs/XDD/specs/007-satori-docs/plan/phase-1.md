---
title: "Phase 1: Foundation and Concepts"
status: completed
version: "1.0"
phase: 1
---

# Phase 1: Foundation and Concepts

## Phase Context

**GATE**: Read all referenced files before starting this phase.

**Specification References**:
- `[ref: SDD/ADR-1]` — 5-file IA; docs/ in modules/satori/
- `[ref: SDD/concepts.md content model]` — 8 sections including ASCII diagram
- `[ref: SDD/hooks.md content model]` — read hooks/hooks.json before writing
- `[ref: PRD/F4]` — conceptual overview requirements
- `[ref: PRD/F5]` — hooks setup requirements

**Key Decisions**:
- ADR-1: All docs live in `modules/satori/docs/` (the submodule, not the TCS docs/)
- ADR-4: `bash` builtin is fully implemented — mention it in concepts.md under "Three layers" as part of gateway; Kairn in "Planned Extensions" only
- T1.2 and T1.3 are independent and can run in parallel after T1.1

**Dependencies**:
- None — this is the first phase
- T1.1 must complete before T1.2 and T1.3 (directory must exist)

---

## Tasks

Establishes the docs/ directory and the two context-setting documents that all other docs link back to.

- [ ] **T1.1 Create `modules/satori/docs/` directory** `[activity: documentation]`

  1. Prime: Confirm `modules/satori/docs/` does not yet exist
  2. Test: After creation, `ls modules/satori/docs/` returns the empty directory
  3. Implement: Create `modules/satori/docs/` with a `.gitkeep` so it appears in git
  4. Validate: `ls modules/satori/docs/` — directory exists
  5. Success: Directory scaffold in place `[ref: SDD/ADR-1]`

- [ ] **T1.2 Write `modules/satori/docs/concepts.md`** `[activity: documentation]`

  1. Prime: Read `docs/XDD/specs/007-satori-docs/solution.md` concepts.md content model section; understand the 8 sections and ASCII diagram; read `modules/satori/src/execution/builtin-server.ts` to understand intent-driven mode threshold `[ref: SDD/concepts.md content model; PRD/F4]`
  2. Test: List what the file must contain: (a) gateway explained (one MCP entry, N downstream servers), (b) three layers (gateway, context DB, knowledge base), (c) hot/cold loading, (d) security scan flow, (e) intent-driven mode with 5000-byte threshold, (f) session continuity, (g) ASCII architecture diagram, (h) Planned Extensions — Kairn only
  3. Implement: Write `modules/satori/docs/concepts.md` with all 8 sections; include the ASCII diagram from SDD; frame intent-driven mode accurately (bash builtin + satori_exec with intent param); keep Kairn in Planned Extensions only
  4. Validate: `grep "Kairn" modules/satori/docs/concepts.md` — appears only in "Planned Extensions" section; `grep "5000\|5_000" modules/satori/docs/concepts.md` — threshold mentioned; `grep "NEEDS CLARIFICATION" modules/satori/docs/concepts.md` — 0 results
  5. Success: Conceptual overview complete; all three layers explained; hot/cold and security scan flow documented `[ref: PRD/AC-6; PRD/F4]`

- [ ] **T1.3 Write `modules/satori/docs/hooks.md`** `[activity: documentation]` `[parallel: true]`

  1. Prime: Read `modules/satori/hooks/hooks.json` (ADR-2: authoritative source); understand what each hook does — PreCompact triggers session guide, PostToolUse captures tool output `[ref: SDD/hooks.md content model; PRD/F5; SDD/ADR-2]`
  2. Test: List what the file must contain: (a) why hooks are needed (passive capture), (b) each hook listed with exact command from hooks.json, (c) exact JSON snippet to add to `.claude/settings.json`, (d) verification step (`satori_context(status)` → capture count > 0)
  3. Implement: Write `modules/satori/docs/hooks.md` with hook commands verbatim from `hooks/hooks.json`; show the complete settings.json structure with hooks merged in; do not invent hook command formats
  4. Validate: `grep -A2 "PreCompact\|PostToolUse" modules/satori/docs/hooks.md` — commands match `hooks/hooks.json` exactly; `grep "NEEDS CLARIFICATION" modules/satori/docs/hooks.md` — 0 results
  5. Success: Hooks setup complete with verbatim commands from source `[ref: PRD/AC-7; PRD/F5]`

- [ ] **T1.4 Phase 1 Validation** `[activity: validate]`

  - `ls modules/satori/docs/` — directory exists with `.gitkeep`, `concepts.md`, `hooks.md`
  - `grep -r "NEEDS CLARIFICATION" modules/satori/docs/` — 0 results
  - `grep "Kairn" modules/satori/docs/concepts.md | grep -v "Planned"` — 0 results (Kairn only in Planned section)
  - `grep "three layers\|hot/cold\|security scan" modules/satori/docs/concepts.md` — all three present
