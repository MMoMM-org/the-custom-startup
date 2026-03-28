---
title: "Phase 5: Integration & E2E Validation"
status: completed
version: "1.0"
phase: 5
---

# Phase 5: Integration & E2E Validation

## Phase Context

**GATE**: Read all referenced files before starting this phase.

**Specification References**:
- `[ref: PRD/Acceptance Criteria; F1–F7 all items]`
- `[ref: SDD/Acceptance Criteria (EARS)]`
- `[ref: SDD/Quality Requirements]`
- `[ref: SDD/Graceful Degradation]`
- `[ref: SDD/Risks; FTS5 trigram SQLite version, kb.sqlite growth]`

**Key Decisions**:
- This phase validates the full system end-to-end, not individual components
- Graceful degradation must be verified with Satori absent (hooks, skills detection)
- The source fidelity audit is a separate post-all-milestones concern (tracked in project-context.md)
- Performance targets: `satori_kb("search")` < 200ms for 10K chunks; exec overhead < 50ms

**Dependencies**:
- All Phases 1–4 complete

---

## Tasks

Validates that all PRD acceptance criteria are met end-to-end and that graceful degradation works correctly in all Satori-absent scenarios.

- [x] **T5.1 BuiltinRuntime E2E** `[activity: validate]`

  **Prime**: Read `[ref: PRD/F3; all AC]` and `[ref: SDD/Primary Flow; satori_exec sequence]`

  **Test** (integration, real Satori process):
  - `satori_exec("bash", "run", {language: "shell", code: "echo hello"})` returns `hello\n`
  - `satori_exec("bash", "run", {language: "python", code: "print(2+2)"})` returns `4\n` (if python3 available)
  - `satori_exec("bash", "run", {language: "shell", code: "...", intent: "find output"})` with >5KB output returns intent-matched result, not full output
  - `satori_exec("bash", "batch", {commands: [{label: "ls", command: "ls /tmp"}], queries: ["tmp"]})` returns indexed results
  - Output captured to ContentDB (verify via `satori_context("query", {q: "echo hello"})`)
  - `satori_manage("disable", {name: "bash"})` → restart Satori → "bash" not in tool list
  - `satori_manage("list")` includes `{name: "bash", runtime: "builtin"}`

  **Implement**: Write `modules/satori/src/__tests__/e2e-builtin.test.ts` — integration tests spinning up real Satori MCP server

  **Validate**: Tests pass; `npm run typecheck`

  - Success: All F3 acceptance criteria met `[ref: PRD/F3]`
  - Success: Execution output appears in ContentDB captures `[ref: SDD/Primary Flow]`

- [x] **T5.2 satori_kb E2E** `[activity: validate]`

  **Prime**: Read `[ref: PRD/F4; all AC]` and `[ref: SDD/Complex Logic; RRF + Proximity Search]`

  **Test** (integration):
  - Index a markdown document with multiple headings → verify chunk count matches heading count
  - Search for a term that appears in a heading → heading-weighted result ranks first
  - Search with a typo ("searh" → "search") → Levenshtein correction fires, results returned
  - Search with `contentType: "code"` → only code chunks returned
  - Run 9 searches → 9th returns throttle block with redirect message
  - `fetch_and_index` with a real URL → chunks stored, raw HTML not in any chunk content
  - `search()` < 200ms on a 10K-chunk corpus (performance gate)

  **Implement**: Write `modules/satori/src/__tests__/e2e-kb.test.ts`

  **Validate**: Tests pass; performance gate logged

  - Success: All F4 acceptance criteria met `[ref: PRD/F4]`
  - Success: Search < 200ms for 10K chunks `[ref: SDD/Quality Requirements]`

- [x] **T5.3 Graceful degradation** `[activity: validate]`

  **Prime**: Read `[ref: SDD/Graceful Degradation table]` and `[ref: PRD/Graceful Degradation table]`; read `[ref: SDD/Error Handling; Satori absent]`

  **Test**:
  - PostToolUse hook script exits 0 when `.satori/` does not exist
  - PreCompact hook script exits 0 when `.satori/` does not exist
  - SessionStart hook script exits 0 when `.satori/` does not exist and prints nothing
  - Skills detecting Satori: `satori_context` absent from tool list → file fallback path taken (document the check pattern for skill implementors)
  - `satori_manage("disable", {name: "bash"})` disables builtin server; `satori_exec("bash", ...)` returns isError

  **Implement**: Write degradation test suite `modules/satori/src/__tests__/e2e-degradation.test.ts`; add detection-pattern documentation to `modules/satori/docs/skill-detection.md` (NEW — for skill authors)

  **Validate**: All degradation tests pass; hook scripts verified with `bash -c "test -d /nonexistent || echo ok"` guard

  - Success: All hook scripts exit 0 with Satori absent `[ref: PRD/F2; detection AC]`
  - Success: No errors surface to user when Satori is not running `[ref: PRD/Graceful Degradation]`

- [x] **T5.4 Kairn backend warning** `[activity: validate]`

  **Prime**: Read `[ref: PRD/F7; AC]` and `[ref: SDD/ADR-7]`; read `modules/satori/src/index.ts` (Phase 3 output)

  **Test**:
  - Start Satori with `context.backend = "kairn"` in satori.toml → warning logged to stderr; server starts normally
  - Start Satori with `context.backend = "satori"` → no warning; normal startup
  - Start Satori with no `backend` field → no warning; normal startup

  **Implement**: Write test `modules/satori/src/__tests__/e2e-backend-warning.test.ts`

  **Validate**: Tests pass

  - Success: All F7 acceptance criteria met `[ref: PRD/F7]`

- [x] **T5.5 Full PRD acceptance criteria audit** `[activity: validate]`

  **Prime**: Read `[ref: PRD/requirements.md; full Acceptance Criteria for F1–F7]` and `[ref: SDD/Acceptance Criteria (EARS)]`

  **Test**: Map each PRD AC to a passing test. Document any gaps.

  **Implement**: Create `modules/satori/src/__tests__/ac-coverage.md` — table mapping each PRD AC (F1–F7) to the test file and test name that covers it. Any uncovered AC gets a failing test added.

  **Validate**: All ACs covered; full `npm run test` passes; `npm run typecheck` passes; `npm run build` succeeds

  - Success: Zero uncovered PRD acceptance criteria `[ref: PRD/requirements.md; all F1–F7 ACs]`
  - Success: Build produces dist/ without errors `[ref: SDD/Deployment View]`

- [x] **T5.6 Phase 5 Validation** `[activity: validate]`

  Final gate: run `npm run test`, `npm run typecheck`, `npm run build` from `modules/satori/`. All pass. Review `ac-coverage.md` — zero gaps. Commit satori submodule. Update `docs/XDD/specs/005-memory-mcp/README.md` — mark plan completed.
