---
title: "Phase 6: Integration, Rollout & E2E Validation"
status: completed
version: "1.0"
phase: 6
---

# Phase 6: Integration, Rollout & E2E Validation

## Phase Context

**GATE**: Read all referenced files before starting this phase. Phases 1-5 must be COMPLETE.

**Specification References**:
- `[ref: PRD/§Cross-Repo Rollout]` — Wave 1 TCS dogfood → Wave 2 Kado migration → Wave 3 other MiYo repos → Waves 4-5 optional GHA + branch-protection
- `[ref: PRD/§Success Metrics]` — Adoption, engagement, quality, business impact KPIs
- `[ref: SDD/§Quality Requirements]` — Performance budgets to verify end-to-end
- `[ref: SDD/§Risks and Technical Debt]` — Implementation gotchas to test
- `[ref: research/performance.md §7]` — 10 worst-case scenarios for E2E test matrix

**Key Decisions**:
- TCS itself is dogfood phase 1 — the plugin must validate against this very repo first.
- Kado is the real migration test (existing `.githooks/` overlay).
- Other MiYo repos (Hakobi, Tomo, Kokoro, Kouzou, Seigyo, Hashi) follow same pattern as Kado but with less overlap risk.
- User-global `~/.claude/hooks/block-main-edits.sh` is NOT retired — kept as universal baseline.
- PR/branch rename `feat/tcs-git-safety` → `feat/tcs-git-helpers` happens AT END of Phase 6 (right before merge).

**Dependencies**:
- Phases 1-5 COMPLETE (full plugin functional with skills + templates + references).

---

## Tasks

This phase validates the plugin end-to-end against real repos and real-world scenarios.

- [x] **T6.1 E2E Test Suite (synthetic-repo dogfood)** `[activity: validate]`

  1. Prime: research/performance.md §7 worst-case scenarios; SDD §Risks Implementation Gotchas; PRD §Feature M1-M12 acceptance criteria.
  2. Test: This task IS the test creation — write `tests/e2e/dogfood.sh` shell script driving `claude --plugin-dir plugins/tcs-git-helpers` through scripted flows:
     - Scenario 1: clean repo, install plugin, run setup, verify `.githooks/` files written with version markers, `core.hooksPath` set, no auto-commit
     - Scenario 2: triggers M1 (create branch with closed PR, attempt push → blocked, set override → allowed)
     - Scenario 3: triggers M2 (create commit on feature branch without PR, attempt new branch → blocked)
     - Scenario 4: triggers M3 (squash-merge a branch, attempt checkout → blocked)
     - Scenario 5: triggers M7 (10 destructive patterns each → blocked, override → allowed once)
     - Scenario 6: triggers M8 (worktree with uncommitted changes, attempt exit → blocked)
     - Scenario 7: large repo with 500 branches → SessionStart still <300ms
     - Scenario 8: rate-limited gh → fail-open with warning
     - Scenario 9: `post-merge` on Kado-style repo with stale-merged branches → batched gh call works
     - Scenario 10: bash 3.2 compat — synthetic repo run with `bash --version 3.2` (or simulate)
  3. Implement: Create comprehensive E2E test driver. Each scenario emits PASS/FAIL with timing. Aggregate report.
  4. Validate: All 10 scenarios pass; performance budgets honored; cascading-denial scenarios show all matched rules.
  5. Success: All M1-M12 + S1, S2 AC verified end-to-end; performance regressions caught.

- [x] **T6.2 TCS Itself — Phase 1 Rollout** `[activity: integration]`

  1. Prime: PRD §Cross-Repo Rollout Wave 1; SDD §Implementation Boundaries (must-preserve list); current state of TCS repo.
  2. Test: Run `/tcs-git-helpers:setup` against TCS itself (this very repo); verify all 4 `.githooks/*` files written with markers; `core.hooksPath` set; no Husky/lefthook/etc. conflicts present (clean install).
  3. Implement: Execute the setup flow on TCS. Manual review of resulting `.githooks/` diff. If `_outbox/` or other repo-specific exclusions needed, populate `.githooks/exclude-paths`.
  4. Validate: Subsequent commits on TCS exercise pre-commit + commit-msg; subsequent pushes exercise pre-push; no spurious denials in routine work.
  5. Success: TCS plugin self-protected; no regressions; `/tcs-git-helpers:status` reports "Plugin version: v1.0.0 ✓ installed in this repo: v1.0.0".

- [ ] **T6.3 Kado Migration — Phase 2 Rollout** `[activity: integration]`

  1. Prime: PRD §Cross-Repo Rollout Wave 2; existing `MiYo/Kado/.githooks/{pre-commit,commit-msg}`; ADR-10 conflict policy; M10 AC for "existing-no-marker" path.
  2. Test: Write `tests/e2e/kado-migration.sh` (or document procedure if interactive): backup `Kado/.githooks/` → run `/tcs-git-helpers:setup` → verify per-file diff prompts → migrate `_outbox/` exception from hardcode in pre-commit to `.githooks/exclude-paths` → confirm install → run Kado's existing tests/CI to ensure no regression.
  3. Implement: Execute migration on Kado. Auto-detect `_outbox/` hardcode and propose moving to `.githooks/exclude-paths` (or document the manual step if auto-detect deemed too brittle).
  4. Validate: Kado's existing tests pass post-migration; the 6 known stale-merged branches surface in `/tcs-git-helpers:status --cleanup`; can be deleted; subsequent commit/push flow works.
  5. Success: Kado migrated successfully; M11 defense-in-depth verified (`.githooks/` work both with and without plugin); 6 stale branches cleaned up.

- [ ] **T6.4 Other MiYo Repos — Phase 3 Rollout** `[activity: integration]` `[parallel: true]`

  1. Prime: PRD §Cross-Repo Rollout Wave 3 (Hakobi, Tomo, Kokoro, Kouzou, Seigyo, Hashi); each has less overlap risk than Kado.
  2. Test: For each repo: run `/tcs-git-helpers:setup`; verify clean install (or per-file prompts if existing `.githooks/`); confirm baseline behavior unchanged.
  3. Implement: Execute setup across the 6 repos. Document any per-repo exclusion paths needed.
  4. Validate: Each repo's existing tests/CI pass; no spurious denials; SessionStart brief renders correctly per repo.
  5. Success: 8/8 repos (TCS + 7 MiYo) have plugin enabled per PRD adoption KPI `[ref: PRD/§Cross-Repo Rollout]`.

- [x] **T6.5 Documentation Polish + CHANGELOG Finalization** `[activity: documentation]` `[parallel: true]`

  1. Prime: Phases 1-5 deliverables; PRD §Vision; SDD §Glossary.
  2. Test: Manual review.
  3. Implement: Finalize `plugins/tcs-git-helpers/README.md` (final user-facing overview); finalize `CHANGELOG.md` (v1.0.0 entry summarizing all features); update top-level TCS repo `README.md` to mention `tcs-git-helpers` alongside other plugins; ensure `references/INDEX.md` is complete.
  4. Validate: README guides a new user from install → first denial → recovery; CHANGELOG matches plugin.json version.
  5. Success: User-facing docs ready for v1.0.0 release.

- [x] **T6.6 Branch Rename + PR Creation** `[activity: integration]`

  1. Prime: PRD §Open Questions OQ11 (rename deferred to implementation); current branch state `feat/tcs-git-safety`; PRD §Brainstorm Live Incident Captured (the very pattern we're fixing).
  2. Test: Verify branch is clean; all commits committed; all tests pass.
  3. Implement: Rename branch `git branch -m feat/tcs-git-safety feat/tcs-git-helpers`; force-push if already remote (safe — single contributor); open PR via `gh pr create` with title following Conventional Commits (`feat(tcs-git-helpers): introduce git workflow discipline plugin`); body summarizes Phases 1-6 deliverables.
  4. Validate: PR opens successfully; CI runs (if any).
  5. Success: PR ready for review/merge; branch name aligned with plugin name.

- [x] **T6.7 Phase 6 Final Validation** `[activity: validate]`

  Run complete suite (all bats + pytest + E2E); verify:
  - All M1-M12 + S1, S2 acceptance criteria green ✓ (bats exit 0, E2E 10/10, verify-tcs-rollout 7/7)
  - 12/12 ADRs implemented per SDD ✓ (CHANGELOG attestation)
  - Performance budgets honored on real repos ✓ (E2E S7 ≤300ms, TCS dogfood pass)
  - 10 worst-case scenarios pass ✓ (E2E 10/10 in ~34s)
  - All 8 repos protected — **1/8 (TCS only); 7 deferred** — T6.3 (Kado) + T6.4 (6 other MiYo repos) deferred to post-publish per Marcus ("no tests against external repos without publishing the plugin first")
  - Documentation complete ✓ (T6.5)
  - PR ready for merge ✓ (PR #11: feat/tcs-git-helpers → main)

  Success: Plugin v1.0.0 ready for v1.0.0 marketplace publish + downstream rollout. T6.3/T6.4 to follow in a separate post-publish session.

---

## Deliverables

- `plugins/tcs-git-helpers/tests/e2e/dogfood.sh` (synthetic-repo end-to-end driver)
- `plugins/tcs-git-helpers/tests/e2e/kado-migration.sh` (real-repo migration driver, optional auto-form)
- TCS itself, Kado, and 6 other MiYo repos with plugin installed and `.githooks/` deployed
- Finalized `plugins/tcs-git-helpers/README.md` + `CHANGELOG.md`
- Updated top-level TCS `README.md`
- PR opened from `feat/tcs-git-helpers` against main
- All tests pass; documentation complete; rollout audit-trail recorded.
