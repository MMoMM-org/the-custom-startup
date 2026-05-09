---
title: "Phase 4: Repo-side .githooks/ Templates"
status: in_progress
version: "1.0"
phase: 4
---

# Phase 4: Repo-side `.githooks/` Templates

## Phase Context

**GATE**: Read all referenced files before starting this phase. Phases 1-3 must be COMPLETE.

**Specification References**:
- `[ref: SDD/§Building Block View — templates/githooks/*]`
- `[ref: SDD/§Architecture Decisions ADR-3, ADR-12]` — config parser, single-coder branch protection (Phase 5 uses)
- `[ref: PRD/§Feature M5, M6, M11]` — Conventional Commits, stale-branch surfacing, defense in depth
- `[ref: PRD/§Feature M1]` — pre-push hook for closed-PR detection
- `[ref: research/integration.md §2]` — gh CLI exit code truth table for pre-push degraded mode
- `[ref: SDD/§.githooks/.config Schema]`

**Key Decisions**:
- **CON-3**: pre-push uses pure-bash `(cmd) & sleep 5; kill $!` for timeout (no `coreutils timeout` dependency).
- **M11**: All `.githooks/*` files include `# tcs-git-helpers: vX.Y.Z` first-line marker.
- **M11**: Templates work standalone — they source `lib/config_parser.sh` from the plugin path IF available, fallback to defaults if not (defense-in-depth: works without plugin).
- **ADR-12**: pre-commit's `TCS_PROTECTED_BRANCHES` defaults to `main|master|production|release`.

**Dependencies**:
- Phase 1 COMPLETE (lib/config_parser.sh used by templates).
- Phase 3 COMPLETE (post-merge updates the cache that session-start-brief.sh reads).

---

## Tasks

This phase produces the four `.githooks/*` template files installed into target repos by the Phase 5 setup skill. Templates work standalone (defense-in-depth M11) and use the same `.config` schema as plugin-side hooks.

- [ ] **T4.1 templates/githooks/pre-commit** `[activity: backend-api]` `[parallel: true]`

  1. Prime: Existing `MiYo/Kado/.githooks/pre-commit` (baseline); SDD §Repo-side `.githooks/` Templates — `pre-commit` (generalized exclusion list); ADR-12 protected-branches list.
  2. Test: Write `tests/bats/githooks_pre_commit.bats` covering: blocks commits to main/master/production/release by default; allows commits to feature branches; secret patterns (env files, credentials, keys, ssh keys) blocked; exclusion list (read from `.githooks/exclude-paths`) bypasses block; `TCS_PROTECTED_BRANCHES` from `.config` overrides default; `TCS_ALLOW_AMEND_ON_PROTECTED=1` allows `--amend` on protected; version marker `# tcs-git-helpers: v1.0.0` is line 1.
  3. Implement: Create `templates/githooks/pre-commit`. Sources `lib/config_parser.sh` if `${CLAUDE_PLUGIN_ROOT}` set, else uses hard-coded defaults. Writes `# tcs-git-helpers: v1.0.0` as first line.
  4. Validate: bats passes; shellcheck clean; ≤300ms p99 per commit.
  5. Success: Inherits Kado's behavior + `.config`-configurable per ADR-12 `[ref: PRD/M5/AC1, M11/AC1]`.

- [ ] **T4.2 templates/githooks/pre-push** `[activity: backend-api]` `[parallel: true]`

  1. Prime: SDD §Repo-side `.githooks/` Templates — `pre-push`; M1 acceptance criteria; integration §2 gh truth table; CON-3 bash-only timeout.
  2. Test: Write `tests/bats/githooks_pre_push.bats`: blocks push when `gh pr list --head <branch>` returns CLOSED or MERGED; allows push when no PR or OPEN; degraded mode when `gh` not installed (exit 0 with stderr warn); `CLAUDE_ALLOW_PUSH_TO_CLOSED_PR=1` env-var allows (override prefix is consistent across plugin and `.githooks/` per M12 contract — single audit/sentinel namespace); reads `${CLAUDE_PLUGIN_DATA}/cache/<repo-hash>-pr-state.json` if present (within 60s TTL) AND ${CLAUDE_PLUGIN_DATA} set, else makes own gh call; bash-only timeout fires after 5s if gh hangs (`(cmd) & sleep 5; kill $!`); version marker present.
  3. Implement: Create `templates/githooks/pre-push`. Inline cache-read for plugin coexistence (ADR-6). Bash-only timeout pattern. Standalone fallback to direct gh call when no plugin cache.
  4. Validate: bats passes; shellcheck clean; ≤5000ms p99 (timeout); cache-hit case ≤30ms.
  5. Success: M1 AC1-AC5 all pass `[ref: PRD/M1]`; ADR-6 cache dedup works; CON-3 satisfied.

- [ ] **T4.3 templates/githooks/commit-msg** `[activity: backend-api]` `[parallel: true]`

  1. Prime: Existing `MiYo/Kado/.githooks/commit-msg` (length-only baseline); SDD §Repo-side `.githooks/` Templates — `commit-msg`; M5 acceptance criteria; ADR-3 config parser.
  2. Test: Write `tests/bats/githooks_commit_msg.bats`: enforces Conventional Commits regex `^(feat|fix|docs|style|refactor|test|chore|perf|revert|build|ci)(\([a-z0-9._-]+\))?!?: .+`; type allowlist from `TCS_ALLOWED_COMMIT_TYPES`; `TCS_REQUIRE_SCOPE=1` makes scope mandatory; merge commits excluded (`MERGE_HEAD` exists OR subject begins `Merge branch …` / `Merge pull request …`); `[skip-format-check]` in subject allows; existing length validation preserved (`TCS_MAX_SUBJECT_LENGTH` default 90); ≤30ms p99 per commit including config-parse cost.
  3. Implement: Create `templates/githooks/commit-msg`. Sources `lib/config_parser.sh` (or fallback defaults). Two-step validation: length first, then format.
  4. Validate: bats passes; shellcheck clean; ≤100ms p99.
  5. Success: M5 AC1-AC4 all pass `[ref: PRD/M5]`; merge-commit exclusion correct; override visible in `git log` per AC4.

- [ ] **T4.4 templates/githooks/post-merge** `[activity: backend-api]` `[parallel: true]`

  1. Prime: SDD §Repo-side `.githooks/` Templates — `post-merge`; M6 acceptance criteria; research/performance.md §3 (batched gh call mandate).
  2. Test: Write `tests/bats/githooks_post_merge.bats`: after `git pull` or merge, queries `gh pr list --state merged --head <each-branch>` BUT BATCHED (single call with `--limit 100`); outputs suggestion list to stderr (NOT stdout, NOT blocking); updates `${CLAUDE_PLUGIN_DATA}/cache/<repo-hash>-stale-cache.tsv`+`.json` atomically; if `gh` unavailable, exits 0 silently (degraded mode); does NOT iterate per-branch with separate gh calls; works whether `${CLAUDE_PLUGIN_DATA}` set (plugin) or not (degraded — only outputs to stderr, no cache); ≤10s p99 even on 50-branch repo.
  3. Implement: Create `templates/githooks/post-merge`. Single batched `gh pr list --state merged --json headRefName,number,mergedAt --limit 100`. JSON parsed via `jq -r` or pure shell (jq cold-start tolerable here, not on hot SessionStart path). Cache writes via `lib/cache.sh._write_stale_cache` if available, else skip.
  4. Validate: bats passes; shellcheck clean; ≤10s p99 on 50-branch fixture.
  5. Success: M6 AC1-AC3 all pass `[ref: PRD/M6]`; batching honored per performance research; cache-update integration with brief works.

- [ ] **T4.5 templates/githooks/.config.example + exclude-paths** `[activity: documentation]` `[parallel: true]`

  1. Prime: SDD §.githooks/.config Schema; ADR-3 allowed keys.
  2. Test: Manual check (no automated test for examples).
  3. Implement: Create `templates/githooks/.config.example` with all 8 allowed keys commented out, each with description and example value (e.g. `# TCS_PROTECTED_BRANCHES=main|master|develop` with comment explaining); create `templates/githooks/exclude-paths.example` empty file with header comment "One pattern per line; anchored to repo root; glob style".
  4. Validate: Manual review; uncommenting each key produces a valid `.config` that parses.
  5. Success: Examples explain each key clearly; new repos can copy-rename to start configuring `[ref: SDD/§.githooks/.config Schema]`.

- [ ] **T4.6 Phase 4 Validation** `[activity: validate]`

  Run all Phase 4 bats tests + shellcheck. Verify standalone behavior:
  - Set `${CLAUDE_PLUGIN_ROOT}` to empty; run each template — confirms defense-in-depth M11 (templates work without plugin)
  - Set `${CLAUDE_PLUGIN_DATA}` to empty; run pre-push and post-merge — confirms graceful degradation (no cache writes attempted)
  - Verify version marker line 1 in all 4 templates
  - Performance budgets per SDD §Quality Requirements

  Success: All 4 templates standalone-functional; M5, M6, M11 fully met.

---

## Deviations

### D1 — `TCS_ALLOW_AMEND_ON_PROTECTED` removed from `.githooks/pre-commit` template

**Date:** 2026-05-09
**Origin:** T4.1 implementation
**Spec ref:** ADR-12 (solution.md), PRD M11/AC1

**Rationale:** ADR-12 specifies `TCS_ALLOW_AMEND_ON_PROTECTED=1` as a config-file key allowing `--amend` on protected branches. Empirical verification with git 2.50.1 on macOS shows that pre-commit hooks have NO reliable signal to detect `--amend`:
- `GIT_REFLOG_ACTION` is empty (not set by `git commit --amend`)
- `ORIG_HEAD` is absent at pre-commit invocation time (written only AFTER hook success)
- Process-tree walking via `ps` fails (git invokes the hook through a re-exec'd subprocess)

Boucle-framework's `branch-guard` (cited as prior art) is a `PreToolUse:Bash` hook — it sees the literal command string and greps for `--amend` trivially. This is a different architectural layer than `.githooks/pre-commit`.

**Resolution:** Amend-exemption logic moves to (and remains in) the Claude-side `block-bad-git-ops.sh` layer (T2.x), which DOES see the command string. The repo-side `.githooks/pre-commit` template is intentionally stricter (defense-in-depth): it blocks ALL commits to protected branches regardless of amend-ness. Users needing to amend on a protected branch must either (a) use the Claude-side override path, or (b) edit `.githooks/.config` to remove the branch from `TCS_PROTECTED_BRANCHES`, or (c) skip the hook with `git commit --no-verify` (which itself is blocked by block-bad-git-ops without override).

**Updated ADR-12 wording (in solution.md):** Strike "TCS_ALLOW_AMEND_ON_PROTECTED" from the `.config` schema; add note that amend exemption is Claude-side only.

**Approved-by:** Marcus (2026-05-09 in /implement orchestration)

### D2 — `.githooks/pre-push` cache-hit p99 raised from 30ms to ~150ms

**Date:** 2026-05-09  
**Origin:** T4.2 implementation  
**Spec ref:** `solution.md` §Quality Requirements; phase-4.md T4.2 step 4

**Rationale:** The original 30ms p99 cache-hit budget was written for the Claude-side `block-bad-git-ops.sh` hook, which is sourced in-process by Claude Code's hook runner (no bash startup, no subprocess). The repo-side `.githooks/pre-push` template runs as a fork-exec bash subprocess invoked by git itself; bash 3.2 startup on macOS alone is 20-30ms, plus `git rev-parse`, `jq`, and `shasum` calls put the unavoidable floor near ~80-120ms. The 30ms target was misapplied.

**Empirical measurement:** Cache-hit cold p99 on macOS bash 3.2.57 (M-series): ~105ms. Subprocess overhead dominates; jq is unavoidable for cache JSON parsing.

**Updated budget:** `.githooks/pre-push` cache-hit p99 = ~150ms (was 30ms). Cache CORRECTNESS (gh-skip on cache-hit) is verified separately by `test_cache_hit_skips_gh_call` — that test asserts the load-bearing invariant (no gh call on hit), not the wall-clock latency. The 30ms budget remains valid for `block-bad-git-ops.sh` (Claude-side, in-process).

**Impact:** Push latency on a cache hit ~105ms vs the previously claimed 30ms — still well under the 5000ms uncached ceiling. ADR-6 cache dedup (avoiding the ~600-800ms gh round trip) is the load-bearing optimization; this deviation just acknowledges the bash-floor cost.

**Approved-by:** Marcus (2026-05-09 in /implement orchestration)

---

## Deliverables

- `plugins/tcs-git-helpers/templates/githooks/{pre-commit,pre-push,commit-msg,post-merge}`
- `plugins/tcs-git-helpers/templates/githooks/{.config.example,exclude-paths.example}`
- `plugins/tcs-git-helpers/tests/bats/githooks_{pre_commit,pre_push,commit_msg,post_merge}.bats`
- All shellcheck-clean and bats-passing; templates work standalone (without plugin).
