---
title: "Phase 3: Awareness Hooks + Status Backend"
status: in_progress
version: "1.0"
phase: 3
---

# Phase 3: Awareness Hooks + Status Backend

## Phase Context

**GATE**: Read all referenced files before starting this phase. Phases 1-2 must be COMPLETE.

**Specification References**:
- `[ref: SDD/§Building Block View — session-start-brief, nudge-hook, git_status_audit.py]`
- `[ref: SDD/§Runtime View Tertiary Flow]` — SessionStart brief sequence with performance trace
- `[ref: SDD/§Architecture Decisions ADR-2, ADR-4]` — Bash/Python split, hybrid TSV+JSON cache
- `[ref: PRD/§Feature M4, M6, M9]` — pre-flight brief, stale branch surfacing, soft nudges
- `[ref: research/performance.md §1, §4]` — Empirical baselines, SessionStart 300ms feasibility
- `[ref: SDD/§Cache Schemas]` — TSV+JSON format

**Key Decisions**:
- **ADR-2**: `git_status_audit.py` is the only Python file (skill backend); session-start-brief.sh and nudge-hook.sh stay pure bash for hot-path performance.
- **ADR-4**: `git_status_audit.py` writes BOTH TSV and JSON sibling files (`<repo-hash>-stale-cache.tsv` + `.json`); session-start-brief.sh reads TSV only (no jq cold-start).
- **CON-2**: SessionStart hook ≤300ms p99 hard limit. Use only local-git + cache-read.
- **M9 nudge-hook MUST stay pure bash** — fires on every Bash command (≤50ms budget).

**Dependencies**:
- Phase 1 COMPLETE (lib/cache.sh provides cache IO; lib/pattern_match.sh provides nudge regex helpers).
- Phase 2 COMPLETE (PreToolUse hooks operational; Phase 3 hooks coexist).

---

## Tasks

This phase implements awareness (SessionStart brief), nudges (PostToolUse), and the on-demand status backend.

- [x] **T3.1 git_status_audit.py (Python skill backend)** `[activity: backend-api]`

  1. Prime: SDD §Building Block View — git_status_audit.py; SDD §Cache Schemas TSV+JSON formats; PRD M4, M6 acceptance criteria; research/integration.md §2 (gh CLI contract for batched query).
  2. Test: Write `tests/python/test_git_status_audit.py` covering: `--brief` mode outputs one-line format matching SDD wireframe; `--cleanup` mode lists stale branches with PR numbers; `--json` mode outputs valid JSON matching schema; `--overrides` mode reads `${CLAUDE_PLUGIN_DATA}/audit/overrides.jsonl` and prints last N events; cache-write produces valid TSV AND valid JSON sibling atomically; batched `gh pr list --state merged --limit 100` is used (NOT per-branch loop) per performance §3.
  3. Implement: Create `scripts/git_status_audit.py` with subcommand modes. Uses `subprocess.run` for git/gh calls; writes cache via atomic mv. Pure stdlib (no third-party dependencies).
  4. Validate: pytest passes; ruff clean; manual: invoke against synthetic repos; verify cache files schema-conformant.
  5. Success: All 4 modes work `[ref: PRD/§/tcs-git-helpers:status modes]`; batched gh call ≤2s p99 even on 50-branch repo `[ref: research/performance.md §7 scenario 9]`.

- [x] **T3.2 session-start-brief.sh** `[activity: backend-api]` `[parallel: true]`

  1. Prime: SDD §Runtime View Tertiary Flow trace; M4 acceptance criteria; ADR-4 TSV format with comment header.
  2. Test: Write `tests/bats/session-start-brief.bats`: brief renders in <300ms p99 across 100 invocations; one-line format matches SDD wireframe; warning marker on protected branch; staleness indicator when cache >24h old; "run /tcs-git-helpers:setup" hint when `.githooks/` absent; NO `gh` calls (mock gh stub fails the test if invoked); cache-empty case renders gracefully (empty stale count, no errors).
  3. Implement: Create `scripts/session-start-brief.sh` using only local git + cache-read. Reads TSV via `head`/`grep -v '^#'`/`wc -l` (NO jq). Sources `lib/cache.sh` for `_read_stale_cache_tsv`.
  4. Validate: bats passes; performance assertion <300ms p99; shellcheck clean; pure bash (no python invocation).
  5. Success: Brief format matches `[ref: SDD/§UI Visualization Brief Layout]`; performance budget met `[ref: CON-2]`; M4 AC1-AC4 all pass.

- [x] **T3.3 nudge-hook.sh** `[activity: backend-api]` `[parallel: true]`

  1. Prime: SDD §Building Block View — nudge-hook; M9 acceptance criteria; PRD §Feature M9 trigger map.
  2. Test: Write `tests/bats/nudge-hook.bats`: trigger map cases (after `git checkout -b X` → "verify base"; after `gh pr create` → "verify PR title"; after `gh pr merge` → "/tcs-git-helpers:status --cleanup"; after `git rebase` → "verify history"; after `git stash pop` → "verify .orig cleanup"); nudge fires only on exit-status 0 (failed command → no nudge); 60s same-nudge dedup per repo via cache file `${CLAUDE_PLUGIN_DATA}/cache/<repo-hash>-nudge-<rule>` (timestamp-based); pure bash (NO git calls, NO gh calls); ≤50ms p99.
  3. Implement: Create `scripts/nudge-hook.sh` parsing JSON stdin (`tool_name`=Bash, `tool_input.command`, exit_status). Regex match against trigger map; emit stderr nudge with reference path; check dedup cache.
  4. Validate: bats passes; performance assertion <50ms p99; shellcheck clean; verify NO `git` or `gh` invocations.
  5. Success: All trigger map entries verified `[ref: PRD/§Feature M9]`; dedup window prevents spam `[ref: PRD OQ9]`; failed-command nudge suppression works `[ref: PRD/M9/AC4]`.

- [ ] **T3.4 Hook Registration Update for Phase 3** `[activity: integration]`

  1. Prime: T2.5 hooks.json (Phase 2 registrations); SDD §Plugin Layout.
  2. Test: bats test asserting hooks.json now includes SessionStart matcher `startup|resume|clear|compact` → session-start-brief.sh; PostToolUse:Bash → nudge-hook.sh; existing Phase 2 entries preserved.
  3. Implement: Update `plugins/tcs-git-helpers/hooks/hooks.json` to add Phase 3 hook entries.
  4. Validate: bats passes; `claude --plugin-dir` loads; manual: SessionStart brief appears at session boot.
  5. Success: SessionStart and PostToolUse fire `[ref: SDD/§External Interfaces inbound]`.

- [ ] **T3.5 Phase 3 Validation** `[activity: validate]`

  Run all Phase 3 tests (bats + pytest) + shellcheck + ruff. Manual check:
  - Open `claude --plugin-dir` in a fresh repo; verify brief appears <300ms
  - Run `git checkout -b test-branch`; verify nudge fires
  - Verify nudge dedup: same `git checkout -b X` twice within 60s → only first nudges
  - Run `/tcs-git-helpers:status` (skill stub OK in this phase) and verify cache populates correctly
  - Verify TSV and JSON cache files are atomically written (no partial states)

  Success: M4, M6, M9 acceptance criteria met; performance budgets honored.

---

## Deliverables

- `plugins/tcs-git-helpers/scripts/git_status_audit.py`
- `plugins/tcs-git-helpers/scripts/session-start-brief.sh`
- `plugins/tcs-git-helpers/scripts/nudge-hook.sh`
- Updated `plugins/tcs-git-helpers/hooks/hooks.json` (SessionStart + PostToolUse entries)
- `plugins/tcs-git-helpers/tests/python/test_git_status_audit.py`
- `plugins/tcs-git-helpers/tests/bats/{session-start-brief,nudge-hook}.bats`
- All linters and tests pass; SessionStart <300ms verified.
