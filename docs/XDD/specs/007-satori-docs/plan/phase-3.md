---
title: "Phase 3: Getting Started, README, and Validation"
status: completed
version: "1.0"
phase: 3
---

# Phase 3: Getting Started, README, and Validation

## Phase Context

**GATE**: Read all referenced files before starting this phase. Phases 1 and 2 must be complete.

**Specification References**:
- `[ref: SDD/ADR-3]` — README in-place update: add satori_kb, Documentation section, correct tool count
- `[ref: SDD/getting-started.md content model]` — 7 sections; standalone path primary, TCS path secondary
- `[ref: SDD/README update model]` — exact changes: tools table, Documentation section
- `[ref: PRD/F1]` — getting started guide requirements
- `[ref: PRD/Journey 1]` — standalone setup flow: clone → build → config → MCP entry → verify → first call
- `[ref: SDD/Cross-Document Link Map]` — getting-started links to configuration.md, hooks.md, tools.md

**Key Decisions**:
- getting-started.md is the last doc to write — it references tools.md and configuration.md which must exist first
- Absolute path requirement for MCP config must be called out explicitly (most common setup error)
- TCS-integrated path is a subsection, not the primary flow

**Dependencies**:
- Phase 2 complete (tools.md and configuration.md must exist before writing getting-started.md)
- T3.1 and T3.2 are independent and can run in parallel
- T3.3 (validation) depends on both T3.1 and T3.2

---

## Tasks

Completes the documentation set: the primary entry point for new users, the README update, and final quality checks.

- [ ] **T3.1 Write `modules/satori/docs/getting-started.md`** `[activity: documentation]`

  1. Prime: Read `modules/satori/docs/tools.md` (just written in Phase 2) for accurate tool names; read `modules/satori/docs/configuration.md` for accurate config fields; read `modules/satori/README.md` for current MCP config example; read `modules/satori/satori.toml.example` for minimal working config `[ref: SDD/getting-started.md content model; PRD/F1; PRD/Journey 1]`
  2. Test: Outline the 7 sections: (a) Prerequisites (Node.js ≥18, npm), (b) Build (npm install && npm run build), (c) Configure satori.toml (minimal working example with one npx server), (d) Register with Claude Code (absolute path JSON, why absolute is required), (e) Verify (satori_manage(list) or satori_find), (f) First tool call (satori_find → satori_schema → satori_exec flow), (g) TCS-integrated path (subsection: what install.sh configures, what to customize); confirm all tool names match tools.md
  3. Implement: Write `modules/satori/docs/getting-started.md` — standalone flow first, TCS subsection at end; call out absolute path requirement with a warning callout; show minimal satori.toml (not the full example); Journey 1 flows naturally from section to section; cross-links to configuration.md, hooks.md, tools.md per link map
  4. Validate: `grep "absolute\|ABSOLUTE" modules/satori/docs/getting-started.md` → absolute path callout present; `grep "satori_find\|satori_exec\|satori_manage" modules/satori/docs/getting-started.md` → all three referenced; `grep "configuration.md\|hooks.md\|tools.md" modules/satori/docs/getting-started.md` → all three linked; `grep "NEEDS CLARIFICATION" modules/satori/docs/getting-started.md` → 0 results
  5. Success: A new user can follow this guide from clone to first successful satori_exec call `[ref: PRD/AC-3; PRD/Journey 1]`

- [ ] **T3.2 Update `modules/satori/README.md`** `[activity: documentation]` `[parallel: true]`

  1. Prime: Read current `modules/satori/README.md`; identify: (a) tools table (missing satori_kb), (b) no Documentation section, (c) usage example (check if still accurate) `[ref: SDD/ADR-3; SDD/README update model; PRD/AC-4]`
  2. Test: List changes needed: (a) tools table: add satori_kb row + bash builtin note, (b) new Documentation section with links to all 5 docs files, (c) usage example: verify tool names are valid (no changes if accurate)
  3. Implement: Update `modules/satori/README.md` in-place — add satori_kb to tools table; add note about bash builtin (`satori_exec("bash", ...)` — not listed as a separate tool entry); insert Documentation section after Quick Start; do not restructure existing sections
  4. Validate: `grep "satori_kb" modules/satori/README.md` → present; `grep "docs/getting-started" modules/satori/README.md` → present; `grep "docs/tools\|docs/configuration\|docs/concepts\|docs/hooks" modules/satori/README.md` → all 4 present
  5. Success:
    - [ ] satori_kb added to README tools table `[ref: PRD/AC-4]`
    - [ ] Documentation section links all 5 docs files `[ref: SDD/ADR-3]`

- [ ] **T3.3 Final validation** `[activity: validate]`

  Run all acceptance criteria checks:

  ```bash
  # AC-1: All 6 satori_* tools documented
  grep "^## \`satori_" modules/satori/docs/tools.md | wc -l  # expect: 6

  # AC-1: bash builtin documented
  grep "bash" modules/satori/docs/tools.md  # expect: match

  # AC-2: All config fields documented
  grep "auto_register_mcp_json\|session_guide_max_bytes\|retain_days\|npx_startup_timeout_ms\|startup_scan\|runtime_scan\|return_scan\|audit_log" modules/satori/docs/configuration.md  # expect: all 8 match

  # AC-3: Getting started guide complete
  ls modules/satori/docs/getting-started.md  # expect: file exists

  # AC-4: README updated
  grep "satori_kb" modules/satori/README.md  # expect: match
  grep "docs/getting-started" modules/satori/README.md  # expect: match

  # AC-5: No undated post-MVP content
  grep -r "Kairn" modules/satori/docs/ | grep -v "Planned\|planned"  # expect: 0 results

  # AC-6: Three layers + hot/cold in concepts.md
  grep "three layers\|hot.cold\|security scan" modules/satori/docs/concepts.md  # expect: all match

  # AC-7: hooks.md has JSON structure
  grep "settings.json\|PreCompact\|PostToolUse" modules/satori/docs/hooks.md  # expect: all match

  # No NEEDS CLARIFICATION anywhere
  grep -r "NEEDS CLARIFICATION" modules/satori/docs/ modules/satori/README.md  # expect: 0 results

  # All 5 docs files exist
  ls modules/satori/docs/  # expect: getting-started.md, configuration.md, tools.md, concepts.md, hooks.md
  ```

  5. Success: All 7 acceptance criteria from PRD pass `[ref: PRD/AC-1 through AC-7]`

- [ ] **T3.4 Update spec README** `[activity: validate]`

  1. Update `docs/XDD/specs/007-satori-docs/README.md`:
     - Set `plan/` status to `completed`
     - Set Current Phase to `Ready`
     - Log final decision: "Implementation complete, all acceptance criteria pass"
  2. Commit all changes: `docs(satori): add documentation for miyo-satori`
