---
title: "Phase 2: Reference Layer"
status: completed
version: "1.0"
phase: 2
---

# Phase 2: Reference Layer

## Phase Context

**GATE**: Read all referenced files before starting this phase. Phase 1 must be complete.

**Specification References**:
- `[ref: SDD/ADR-2]` — Zod schemas are authoritative; read source files before writing
- `[ref: SDD/tools.md content model]` — 7 tool sections (6 satori_* + bash builtin)
- `[ref: SDD/configuration.md content model]` — all sections, per-runtime tables
- `[ref: SDD/Implementation Gotchas]` — bash not in satori_find catalog; ThrottleBlock return shape; hooks.json field

**Key Decisions**:
- ADR-2: Read every Zod schema and `src/config/schema.ts` before writing — never recall parameters from memory
- ADR-4: `bash` builtin fully documented including intent-driven mode; note explicitly that it is NOT discoverable via `satori_find`
- T2.1 and T2.2 are fully independent and must run in parallel

**Dependencies**:
- Phase 1 complete (docs/ directory exists)
- T2.1 and T2.2 are independent — run in parallel

---

## Tasks

Builds the two authoritative reference documents that users bookmark for ongoing use.

- [ ] **T2.1 Write `modules/satori/docs/configuration.md`** `[activity: documentation]` `[parallel: true]`

  1. Prime: Read `modules/satori/src/config/schema.ts` (all field definitions); read `modules/satori/satori.toml.example` (field comments and examples); cross-reference both — schema.ts is authoritative for field names and types, example file for default values and comments `[ref: SDD/configuration.md content model; SDD/ADR-2; PRD/F2]`
  2. Test: List all sections that must exist: (a) config resolution order (global → project → repo, merge rules), (b) project_dir + set_project_dir, (c) [gateway] — auto_register_mcp_json, (d) [context] — db_path, session_guide_max_bytes, retain_days, (e) [lifecycle] — npx_startup_timeout_ms, (f) [security] — startup_scan, runtime_scan, return_scan, audit_log + scan statuses, (g) [[servers]] with per-runtime tables (npx/docker/external); confirm env var interpolation syntax
  3. Implement: Write `modules/satori/docs/configuration.md` — every field documented with name, type, default, description; per-runtime table with required vs optional columns; at least one complete [[servers]] example per runtime type; env var interpolation shown (`"${GITHUB_TOKEN}"` syntax)
  4. Validate: `grep "auto_register_mcp_json\|session_guide_max_bytes\|npx_startup_timeout_ms\|retain_days\|startup_scan" modules/satori/docs/configuration.md` — all 5 fields present; `grep "NEEDS CLARIFICATION" modules/satori/docs/configuration.md` — 0 results
  5. Success:
    - [ ] All satori.toml fields documented with type and default `[ref: PRD/AC-2]`
    - [ ] Per-runtime tables complete (npx, docker, external) `[ref: SDD/configuration.md content model]`
    - [ ] Config resolution order explained `[ref: SDD/ADR-2]`

- [ ] **T2.2 Write `modules/satori/docs/tools.md`** `[activity: documentation]` `[parallel: true]`

  1. Prime: Read all 6 Zod schema files: `src/tools/satori-context.ts`, `satori-manage.ts`, `satori-find.ts`, `satori-schema.ts`, `satori-exec.ts`, `satori-kb.ts`; read `src/execution/builtin-server.ts` for bash tools; read `src/execution/runtime.ts` for Language union; note `ThrottleBlock` return shape from `src/knowledge/knowledge-db.ts` `[ref: SDD/tools.md content model; SDD/ADR-2; SDD/Implementation Gotchas; PRD/F3]`
  2. Test: List what each section must contain:
     - `satori_context`: 4 sub-commands (restore, query, status, flush) with all params
     - `satori_manage`: 10 sub-commands with all params, scope field explained
     - `satori_find`: query + optional server filter; return shape `{server, tool, description, state}`
     - `satori_schema`: server + tool params; return shape `{name, description, inputSchema}`
     - `satori_exec`: server + tool + args + session_id; hot-start note
     - `satori_kb`: 3 sub-commands (index, search, fetch_and_index); ThrottleBlock as possible return
     - `bash` builtin: explicit note it bypasses satori_find; run/run_file/batch with all params; 11 languages listed; intent-driven mode with 5000-byte threshold explained
  3. Implement: Write `modules/satori/docs/tools.md` — one H2 per tool, sub-commands as H3; at least one code example per sub-command; error cases noted; `bash` section includes explicit "not discoverable via satori_find" callout and intent-driven mode explanation
  4. Validate: `grep "^## \`satori_" modules/satori/docs/tools.md | wc -l` → 6; `grep "bash\|builtin" modules/satori/docs/tools.md` → present; `grep "ThrottleBlock\|throttle" modules/satori/docs/tools.md` → present; `grep "NEEDS CLARIFICATION" modules/satori/docs/tools.md` → 0
  5. Success:
    - [ ] All 6 satori_* tools documented with all sub-commands `[ref: PRD/AC-1]`
    - [ ] bash builtin documented with intent-driven mode `[ref: SDD/ADR-4]`
    - [ ] satori_kb present (was missing from existing README) `[ref: PRD/F3]`

- [ ] **T2.3 Phase 2 Validation** `[activity: validate]`

  - `ls modules/satori/docs/` → 4 files: `.gitkeep`, `concepts.md`, `hooks.md`, `configuration.md`, `tools.md`
  - `grep -r "NEEDS CLARIFICATION" modules/satori/docs/` → 0 results
  - `grep "^## \`satori_" modules/satori/docs/tools.md | wc -l` → 6
  - `grep "bash" modules/satori/docs/tools.md` → bash builtin section present
  - `grep "auto_register_mcp_json" modules/satori/docs/configuration.md` → match
