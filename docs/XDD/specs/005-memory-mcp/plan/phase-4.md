---
title: "Phase 4: Hooks + Install Flow"
status: pending
version: "1.0"
phase: 4
---

# Phase 4: Hooks + Install Flow

## Phase Context

**GATE**: Read all referenced files before starting this phase.

**Specification References**:
- `[ref: SDD/ADR-5; Satori owns hooks entirely]`
- `[ref: SDD/Hook Registration; install-hooks.sh, hook entries]`
- `[ref: SDD/Directory Map; modules/satori/hooks/ + scripts/]`
- `[ref: SDD/install.sh Changes]`
- `[ref: SDD/ADR-6; session guide format reuses buildResumeSnapshot()]`
- `modules/satori/src/context/session-db.ts` — SessionDB API (hook scripts access this)
- `modules/satori/src/context/snapshot.ts` — buildResumeSnapshot() (PreCompact hook calls this)

**Key Decisions**:
- ADR-5: Satori registers its own hooks via `scripts/install-hooks.sh` — TCS does not touch hooks.json
- ADR-6: PreCompact hook calls existing `buildResumeSnapshot()` — no new snapshot format
- Hook scripts are `.js` files (not TypeScript) — run directly by Node.js without compilation step
- Each hook script checks `.satori/` existence as a guard (but the hook entry itself has the condition too)
- TCS `install.sh` change is a single call to `modules/satori/scripts/install-hooks.sh` — no other changes
- Absolute paths written to hook entries by `install-hooks.sh` using `$(pwd)` or `$REPO_ROOT`

**Dependencies**:
- Phase 3 complete (Satori core must work before hooks make sense to test)
- T4.1, T4.2, T4.3 are independent of each other — all can run in parallel

---

## Tasks

Delivers automatic session capture, pre-compaction flush, session restore, and the installation flow.

- [ ] **T4.1 Hook scripts** `[activity: backend-api]` `[parallel: true]`

  **Prime**: Read `modules/satori/src/context/session-db.ts` and `modules/satori/src/context/snapshot.ts`; read `[ref: SDD/Hook Registration]` and `[ref: SDD/ADR-6]`; read `[ref: PRD/F5; memory routing AC]`

  **Test**:
  - `post-tool-capture.js`: receives tool use JSON via env/stdin; calls `SessionDB.insertEvent()` with type='mcp'; exits 0
  - `post-tool-capture.js`: exits 0 silently when `.satori/` absent (guard)
  - `pre-compact-flush.js`: calls `buildResumeSnapshot()` and `sessionDb.upsertResume()`; exits 0
  - `pre-compact-flush.js`: exits 0 silently when `.satori/` absent
  - `session-start-restore.js`: calls `sessionDb.getResume()`; prints reminder to stdout if resume exists; exits 0

  **Implement**:
  - Create `modules/satori/hooks/post-tool-capture.js` — reads Claude Code PostToolUse payload; inserts event to SessionDB; `.satori/` guard; exits 0 always
  - Create `modules/satori/hooks/pre-compact-flush.js` — calls `buildResumeSnapshot()`; upserts to `session_resume`; `.satori/` guard; exits 0 always
  - Create `modules/satori/hooks/session-start-restore.js` — queries `session_resume` for latest unconsumed; prints context-mode active reminder + restore hint; `.satori/` guard; exits 0 always

  **Validate**: Unit tests for each script with mocked SessionDB; integration test with real `.satori/` dir

  - Success: Really-short-lived state captured via PostToolUse hook `[ref: PRD/F5; memory routing AC]`
  - Success: Session guide flushed before compaction `[ref: PRD/F5; PreCompact AC]`
  - Success: All scripts exit 0 when Satori absent — no errors surfaced to user `[ref: SDD/Error Handling; Satori absent]`

- [ ] **T4.2 install-hooks.sh** `[activity: backend-api]` `[parallel: true]`

  **Prime**: Read `[ref: SDD/Hook Registration]`; understand Claude Code hooks.json format (check `plugins/tcs-helper/hooks/hooks.json` for reference structure); read `[ref: SDD/ADR-5]`

  **Test**:
  - Running `install-hooks.sh` from repo root adds 3 hook entries to `~/.claude/settings.json` (or project hooks.json) with absolute paths
  - Script is idempotent — running twice does not duplicate entries
  - Each entry has correct `condition: "test -d .satori"` guard
  - Script fails gracefully if Satori hooks directory does not exist
  - Script uses bash 3.2 compatible syntax (no `declare -A`, no `[[` if avoidable)

  **Implement**:
  - Create `modules/satori/scripts/install-hooks.sh` — detects hooks.json location; checks for existing entries (idempotent); writes 3 hook entries with absolute `$(pwd)` paths; bash 3.2 compatible

  **Validate**: Manual run from test repo; verify hooks.json contains correct entries; run again to verify idempotency

  - Success: Three hook entries written with absolute paths `[ref: SDD/Hook Registration]`
  - Success: Script idempotent on repeat runs `[ref: SDD/ADR-5]`
  - Success: bash 3.2 compatible (no `declare -A`) `[ref: CON-7]`

- [ ] **T4.3 install.sh context-mode opt-in** `[activity: backend-api]` `[parallel: true]`

  **Prime**: Read current `install.sh` in full; read `[ref: SDD/install.sh Changes]` and `[ref: PRD/F1; install opt-in AC]`

  **Test**:
  - Opt-in prompt appears only when `modules/satori/` exists
  - Selecting Yes calls `modules/satori/scripts/install-hooks.sh` and writes `[context]` block to `satori.toml`
  - Selecting No makes no changes to `satori.toml` and does not call install-hooks.sh
  - `[context]` block written with `db_path`, `session_guide_max_bytes`, `retain_days`
  - If `satori.toml` already has a `[context]` block, it is not duplicated

  **Implement**:
  - Edit `install.sh` — add context-mode opt-in section after Satori submodule check; prompt user; on yes: call `modules/satori/scripts/install-hooks.sh`, append `[context]` block to `satori.toml` if absent

  **Validate**: Manual walkthrough of install.sh yes path and no path

  - Success: Opt-in prompt appears only when Satori present `[ref: PRD/F1; install opt-in AC]`
  - Success: `satori.toml` `[context]` block written with all three fields `[ref: PRD/F1; satori.toml AC]`
  - Success: TCS install.sh contains no Satori-internal logic — only calls Satori's own scripts `[ref: SDD/ADR-5]`

- [ ] **T4.4 Phase 4 Validation** `[activity: validate]`

  Run full test suite. Verify hook scripts exit 0 in isolation (no Satori running). Manual smoke test: run `install.sh` with Satori present, opt in, verify `satori.toml` and hooks.json updated correctly. Verify uninstall.sh prompts for DB removal (both `db.sqlite` and `kb.sqlite`).
