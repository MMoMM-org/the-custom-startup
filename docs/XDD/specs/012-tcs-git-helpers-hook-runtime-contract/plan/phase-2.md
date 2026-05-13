---
title: "Phase 2: Skill-side drift check + cmd_cleanup refresh"
status: in_progress
version: "1.0"
phase: 2
---

# Phase 2: Skill-side drift check + cmd_cleanup refresh

## Phase Context

**GATE**: Read all referenced files before starting this phase.

**Specification References**:
- `[ref: PRD/Feature 2]` — `--cleanup` reports state matching `git`
- `[ref: PRD/Feature 3]` — plugin-version updates propagate safely
- `[ref: PRD/Feature 4]` — skills depending on hooks check version at invocation time
- `[ref: SDD/ADR-3]` — skills read installed version from `.githooks/tcs-git-helpers-version`
- `[ref: SDD/ADR-4]` — shared `drift_check.{sh,py}` helper
- `[ref: SDD/ADR-5]` — `cmd_cleanup` live-refresh on every invocation
- `[ref: SDD/ADR-8]` — pre-bundle installs treated as `MISSING`
- `[ref: SDD/Implementation Examples / drift-check helper (bash)]`
- `[ref: SDD/Implementation Examples / cmd_cleanup refresh (Bug 1 fix)]`
- `[ref: SDD/Runtime View / Primary Flow: skill drift-check on --cleanup]`

**Key Decisions**:
- Drift check fires at skill-invocation time only (not SessionStart) per CON-5.
- Three-state result: `OK`, `MISSING`, `DRIFT:<installed>`. Caller produces the user-facing message; helper just classifies.
- `cmd_cleanup` always calls `refresh_stale_cache()` when `gh` is authenticated, then reads the (now-fresh) cache. When `gh` is unavailable/unauthenticated, falls back to cache content with a stderr explanation (no longer silently reporting "none").
- `session-start-brief.sh` does NOT perform drift checks — it surfaces stale-count cache value with no prompts (CON-5 — SessionStart is not the drift surface).

**Dependencies**:
- Phase 1 complete: the installed `.githooks/tcs-git-helpers-version` file exists, otherwise drift-check tests have nothing to read.

**What this phase delivers**: Skills that depend on hook state correctly surface drift to the user when the installed bundle is out of date. `/tcs-git-helpers:git-audit --cleanup` reports candidates matching `git branch --merged main` ∩ closed-PR set. The two-month-old Bug 1 ("cleanup says none when reality says six") is closed.

---

## Tasks

- [ ] **T2.1 Bash drift-check helper `drift_check.sh`** `[activity: build-platform]` `[parallel: true]`

  1. **Prime**: Read SDD `[ref: SDD/Implementation Examples / drift-check helper (bash)]` and `[ref: SDD/Internal API Changes / function: drift_check_hook_bundle]`.
  2. **Test**: Write `plugins/tcs-git-helpers/tests/bats/drift-check-sh.bats` covering:
     - When `<repo>/.githooks/tcs-git-helpers-version` is missing → stdout is exactly `MISSING`
     - When file content matches expected → stdout is exactly `OK`
     - When file content differs (e.g., installed=`h1`, expected=`h7`) → stdout is exactly `DRIFT:h1`
     - Helper handles trailing whitespace/CRLF in the version file (trims via `tr -d '[:space:]'`)
     - Helper exits 0 in every case (caller decides action)
     - Helper does not write to stderr
  3. **Implement**: Create `plugins/tcs-git-helpers/scripts/lib/drift_check.sh` with `drift_check_hook_bundle <repo_path> <expected_version>` per SDD wire shape. Pure bash 3.2, read-only.
  4. **Validate**: bats tests pass; `shellcheck` clean.
  5. **Success**:
     - [ ] Three-state contract observed exactly `[ref: SDD/Internal API Changes]`
     - [ ] No side effects (read-only verified by test)

- [ ] **T2.2 Python drift-check helper `drift_check.py`** `[activity: build-platform]` `[parallel: true]`

  1. **Prime**: Read SDD `[ref: SDD/Internal API Changes / function: check_hook_bundle]` and the bash helper from T2.1 for behavior parity.
  2. **Test**: Write `plugins/tcs-git-helpers/tests/python/test_drift_check.py` covering the same three cases (`OK`, `MISSING`, `DRIFT`), plus a parity check that the python helper produces the same classification as the bash helper for the same `(repo_path, expected_version)` inputs across a 10-row table of fixtures.
  3. **Implement**: Create `plugins/tcs-git-helpers/scripts/lib/drift_check.py` exposing `check_hook_bundle(repo_path: Path, expected_version: str) -> DriftResult` where `DriftResult` is a small frozen dataclass with `status: DriftStatus` (enum: `OK | MISSING | DRIFT`) and `installed_version: str | None`.
  4. **Validate**: `pytest tests/python/test_drift_check.py`; verify parity test passes.
  5. **Success**:
     - [ ] Same three-state contract as the bash helper `[ref: SDD/ADR-4]`
     - [ ] Parity table passes (no divergence between bash/python implementations)

- [ ] **T2.3 Wire drift check + live refresh into `cmd_cleanup`** `[activity: build-feature]`

  1. **Prime**: Read existing `plugins/tcs-git-helpers/scripts/git_status_audit.py:454-520` (`cmd_cleanup`). Read SDD `[ref: SDD/Implementation Examples / cmd_cleanup refresh (Bug 1 fix)]`.
  2. **Test**: Extend `tests/python/test_git_status_audit.py` covering `cmd_cleanup`:
     - Drift check first: when `.githooks/tcs-git-helpers-version` missing → script exits 1, stderr contains "hooks not installed", no `gh` call attempted
     - Drift check first: when installed != expected → script exits 1, stderr contains both versions and `/tcs-git-helpers:git-setup` suggestion, no `gh` call attempted
     - On OK: `refresh_stale_cache` is called exactly once before the cache read
     - On OK + `gh` unauthenticated: refresh is attempted, fails gracefully, stderr explains, falls back to existing cache content (rather than reporting "none")
     - On OK + `gh` not installed: stderr explains, falls back to existing cache
     - The pre-existing interactive prompt + delete path is preserved end-to-end
  3. **Implement**: Modify `cmd_cleanup` per SDD example: call `check_hook_bundle(repo_path, EXPECTED_HOOK_BUNDLE_VERSION)` first; branch on result; on OK call `refresh_stale_cache(...)` inside a try/except that distinguishes auth-missing from other failures and prints the right stderr line; then read the cache as today. `EXPECTED_HOOK_BUNDLE_VERSION` is read from the plugin's own `templates/githooks/tcs-git-helpers-version` at script startup.
  4. **Validate**: `pytest tests/python/test_git_status_audit.py`; manual: in a real repo with merged-PR branches, run `--cleanup` and confirm candidates list matches `git branch --merged main`.
  5. **Success**:
     - [ ] `--cleanup` reflects live `git`/`gh` reality, not stale cache `[ref: PRD/AC-F2.1]`
     - [ ] Drift `MISSING` and `DRIFT` paths produce distinct, actionable stderr messages `[ref: PRD/AC-F4.1, F4.4]`
     - [ ] Graceful degradation on no-gh / no-auth produces stderr explanation, never silent "none" `[ref: PRD/AC-F2.3]`

- [ ] **T2.4 Wire drift check into other audit modes** `[activity: build-feature]`

  1. **Prime**: Read `cmd_default`, `cmd_brief`, `cmd_json`, and `cmd_overrides` in `git_status_audit.py`. Identify which modes consume the stale-branch cache (default, brief, json — yes; overrides — no).
  2. **Test**: Add cases to `tests/python/test_git_status_audit.py`:
     - `cmd_brief` with `MISSING` drift → silent on drift but the stale-count segment shows `0 stale-merged` rather than nagging (per CON-5, SessionStart is not the drift surface)
     - `cmd_default` and `cmd_json` (when invoked as skills by user) → emit drift prompts in `MISSING`/`DRIFT` cases and exit 1
     - `cmd_overrides` → drift check NOT performed (this mode does not depend on hook state)
  3. **Implement**: Add a shared `_drift_gate(repo_path, *, silent: bool)` helper inside `git_status_audit.py` that calls `check_hook_bundle` and either prints+exits (when `silent=False`) or returns the result for the caller to consult (when `silent=True`, used by the brief). Wire `cmd_default`, `cmd_brief` (silent), `cmd_cleanup` (re-use from T2.3), `cmd_json` to call it appropriately. Leave `cmd_overrides` untouched.
  4. **Validate**: `pytest tests/python/test_git_status_audit.py`; manual: invoke each mode under three drift conditions (OK / MISSING / DRIFT) and confirm output matches expectations.
  5. **Success**:
     - [ ] Skill modes that depend on hook state surface drift inline `[ref: PRD/AC-F4.1]`
     - [ ] Skill modes that do not depend on hook state do not perform the check `[ref: PRD/AC-F4.3]`
     - [ ] Happy path is silent (no drift output when OK) `[ref: PRD/AC-F4.2]`

- [ ] **T2.5 Soften `session-start-brief.sh` for missing-cache case** `[activity: build-platform]` `[parallel: true]`

  1. **Prime**: Read existing `plugins/tcs-git-helpers/scripts/session-start-brief.sh:130-180` (stale-count + cleanup-suggestion blocks). Confirm it does not currently prompt about drift.
  2. **Test**: Extend `tests/bats/session-start-brief.bats` to cover:
     - When `.githooks/tcs-git-helpers-version` is missing → brief still emits, `stale-count` segment shows `0 stale-merged`, no drift prompt line
     - When the cache file is missing → brief still emits, `stale-count` segment shows `0 stale-merged`, no error
     - Existing happy-path tests continue to pass
  3. **Implement**: Update `session-start-brief.sh` so that missing-cache and missing-version both fail-open silently (the brief is a fast-path summary, not a drift surface — CON-5).
  4. **Validate**: bats tests pass; `shellcheck` clean.
  5. **Success**:
     - [ ] SessionStart brief never prompts about drift `[ref: PRD/Q5 resolution; CON-5]`
     - [ ] Brief degrades silently on missing cache / version `[ref: PRD/AC-F5.2 — exit 0 always]`

- [ ] **T2.6 Phase 2 validation + Bug 1 closure** `[activity: validate]`

  1. **Run** `bats plugins/tcs-git-helpers/tests/bats/` and `pytest plugins/tcs-git-helpers/tests/python/` — both green.
  2. **Run** an end-to-end check on a real repo:
     - Install hooks via `/tcs-git-helpers:git-setup`
     - Identify a local branch B already merged on GitHub
     - Run `/tcs-git-helpers:git-audit --cleanup`
     - Confirm B appears in the candidate list
     - Manually edit `.githooks/tcs-git-helpers-version` to a non-matching value
     - Re-run `--cleanup` and confirm drift prompt fires; exit 1
     - Restore the file and confirm cleanup works again
  3. **Cross-reference** every PRD AC row in the README mapping table pointing at Phase 2 has a backing test.
  4. **Success**:
     - [ ] Bug 1 closed: `--cleanup` matches `git branch --merged main` ∩ merged-PR set `[ref: PRD/AC-F2.1]`
     - [ ] Drift scenarios produce the right user-facing prompts `[ref: PRD/AC-F4.1, F4.4]`
     - [ ] No regression in any existing test suite
