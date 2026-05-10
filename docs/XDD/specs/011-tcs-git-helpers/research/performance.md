# Performance Research — `tcs-git-helpers` (PRD phase)

**Lens:** Hook-startup overhead, `gh` call cost, cache strategy, compound budgets.
**Empirical baseline measured today on this repo (macOS, bash 3.2, gh 2.88).** Numbers below are real, not estimated unless flagged.

---

## 1. Empirical Baseline (measured)

| Operation | Cold | Warm | Notes |
|---|---:|---:|---|
| `bash -c true` | 3ms | 3ms | macOS bash 3.2 |
| `git rev-parse --abbrev-ref HEAD` | 22ms | — | |
| `git symbolic-ref --short HEAD` | 24ms | — | |
| `git status --porcelain` | 47ms | — | small repo (2 dirty) |
| `git for-each-ref refs/heads/` | 24ms | — | 2 branches |
| `git rev-list --left-right --count @{u}...HEAD` | 15ms | — | ahead/behind |
| `git cherry origin/main HEAD` | 15ms | — | squash-merge detection |
| `python3 -c pass` | 29–35ms | 29–35ms | |
| `jq '.a'` | 6ms | 6ms | |
| `gh --version` | 40ms | 40ms | binary-only |
| **`gh pr list --head … --json …`** | **648ms** | **352ms** | network-bound |
| `.config` parser, 8 keys, bash-3.2 case-based | **3ms** | — | per cross-cutting hint below |
| Composite SessionStart sim (3 git calls + emit) | **58ms** | — | end-to-end |

**SessionStart 58ms measured vs 300ms budget → ~5× headroom**, IF we stay local-only.

---

## 2. Performance Budgets per Component

Budget = target (p50). Limit = SLO (regression past this fails CI).

| Hook / Component | Fires on | Budget p50 | Limit p99 | Measurement |
|---|---|---:|---:|---|
| `session-start-brief.sh` | SessionStart, 1×/session | **150ms** | **300ms** | `time` wrapper → `${CLAUDE_PLUGIN_DATA}/perf.log` |
| `block-bad-git-ops.sh` non-push patterns | PreToolUse Bash, every cmd | **20ms** | **80ms** | bats-core perf test |
| `block-bad-git-ops.sh` **push** (gh-checked) | PreToolUse Bash, ~5–20×/session | **30ms cached / 800ms uncached** | **5000ms** = `timeout 5` | cache-hit ratio ≥80% |
| `pre-edit-branch-check.sh` | Write/Edit, dozens/session | **30ms** | **80ms** | local git only |
| `nudge-hook.sh` (PostToolUse) | every Bash cmd | **15ms** | **50ms** | pure bash regex, NO git/gh |
| `worktree-exit-guard.sh` | PreToolUse:ExitWorktree, 1× | **150ms** | **500ms** | local git only |
| `.githooks/pre-commit` | git commit | **100ms** | **300ms** | per-commit |
| `.githooks/commit-msg` | git commit | **30ms** | **100ms** | regex + 3ms config parse |
| `.githooks/pre-push` (gh-checked) | git push | **800ms** | **5000ms** | timeout 5 |
| `.githooks/post-merge` + cache write | git pull/merge | **2000ms** | **10000ms** | background `&` allowed |

**Compound worst cases:**
- **Edit on a file:** user-global `block-main-edits.sh` (~25ms) + plugin `pre-edit-branch-check.sh` (~30ms) = **~55ms p50**.
- **`git push`:** Claude-side push hook (gh, ~800ms) + `.githooks/pre-push` (gh again, ~800ms) = **~1.6s** if independent. Claude-side hook should write a `${CLAUDE_PLUGIN_DATA}/cache/<repo-hash>-pr-state.json` 60s-TTL entry the `.githooks/pre-push` reads, halving real-world push latency.
- **Every Bash cmd:** `block-bad-git-ops.sh` (20ms) + `nudge-hook.sh` (15ms) = **~35ms** per Bash. Nudge-hook MUST stay pure-bash (no git, no gh).

---

## 3. `gh` Call Inventory

Each call = **300–800ms uncached, network-bound, rate-limited (5000/hr per token, shared globally).**

| Site | Frequency | Call | Cache? |
|---|---|---|---|
| `block-bad-git-ops.sh` push pattern | per `git push` | `gh pr list --head <branch>` | **YES** 60s TTL `<repo>:<branch>` |
| `.githooks/pre-push` | per `git push` | same call | **YES** read same cache or skip if Claude-side already checked |
| `block-bad-git-ops.sh` resume-merged-branch | per `git checkout <existing>` | `gh pr list --head <branch> --state merged` | **YES** 5min TTL per branch |
| `.githooks/post-merge` | per pull/merge | loops local branches → `gh pr list --head <each>` | **CRITICAL** — must use ONE batched `gh pr list --state merged --json headRefName,number,mergedAt --limit 100` (~600ms total vs N×800ms) |
| `git_status_audit.py` for `/status` | on-demand | same batched call | same |
| `--with-branch-protection` | once at setup | `gh api -X PUT …` | n/a |

**Rate-limit math:** 6 MiYo repos × ~20 sessions/day × ~10 push attempts = ~1200 push checks/day. Within 5000/hr budget BUT a non-batched `post-merge` on Kado (currently 6 stale branches) = 6× per pull. Batching is non-negotiable.

---

## 4. SessionStart 300ms Feasibility — VERDICT: feasible

**Empirical proof:** 58ms measured on this repo today.

**Fits in 300ms:**
- bash startup (5ms) + `symbolic-ref` + `status --porcelain` + `rev-list --left-right` (~75ms total) + line-based cache read with `head`/`wc -l` (~3ms) + emit (5ms) = **~90ms p50, ~150ms p99 on busy repos with 50+ branches**.

**Does NOT fit — must be deferred/async:**
- Any `gh` call (350–800ms).
- Per-branch `git cherry` loops (15ms × N → 750ms for 50 branches).
- `git_status_audit.py` (Python adds 29ms cold-start before doing any work).

**Mandate:** `session-start-brief.sh` MUST be pure bash, local-git-only, cache-read-only. Cache is populated out-of-band by `post-merge` and `/tcs-git-helpers:status`. `git_status_audit.py` belongs on the on-demand skill path and on `post-merge` (background-friendly), NEVER on SessionStart.

---

## 5. Cache Design Recommendations

**Path:** `${CLAUDE_PLUGIN_DATA}/cache/<repo-hash>-stale-cache.json`.
- `<repo-hash>` = `sha1sum <<<"$(git rev-parse --show-toplevel)"` first 12 chars.

**Format — recommend hybrid:** line-based TSV with `# key=value` header for SessionStart-read; the writer (Python script) emits both this and a `.json` sibling for the skill's `--json` output.

```
# tcs-git-helpers stale cache v1
# updated_iso=2026-05-08T14:23:11Z
# default_branch=main
feat/old-thing	38	2026-04-12T10:00:00Z
fix/another-thing	40	2026-04-15T09:00:00Z
```

Reasons:
- `wc -l` for count (~1ms), `awk` for fields, NO `jq` on SessionStart path (saves 5–10ms cold).
- Header-comment trick keeps it valid bash-grep-parseable while remaining human-readable.

**TTL & freshness:**
- Read regardless of age (per brainstorm §7.3) — never block SessionStart on cache miss.
- Report `(cache stale: 3d old)` if `now - updated_iso > 24h`.
- Invalidation: `post-merge` rewrites; `/status` rewrites; `pre-push success` does NOT touch (different cache).
- **Separate cache for PR-state-by-branch** (push hook): `${CLAUDE_PLUGIN_DATA}/cache/<repo-hash>-pr-state.json`, 60s TTL, atomic `mv tmp final`.

**Concurrency:** lockfile `${CLAUDE_PLUGIN_DATA}/cache/<repo-hash>.lock`. macOS bash 3.2 has no `flock` builtin — use PID-file with `kill -0` liveness check; auto-reclaim if stale >5min. Reads never lock (atomic `mv` ensures consistent state).

---

## 6. `.config` Parser Cost (cross-cutting hint addressed)

Security-researcher flagged config-parser cost in commit-msg per-commit path. **Measured: 3ms for the bash-3.2 case-based parser, 3ms for regex-per-line — both negligible vs the 30ms commit-msg budget.**

**Verdict:** No memoization needed. Caching parsed config in `$TMPDIR` would add risk (stale config after `.config` edit, cross-session pollution, cleanup) for ~3ms savings. Just parse once at script start. Important constraint: `lib/config_parser.sh` must use the case-based form (`case "$ALLOWED" in *" $k "*)`) — bash 3.2 macOS default has no associative arrays (`declare -A`), confirmed by today's test.

---

## 7. Worst-Case Scenarios for PLAN Test Matrix

1. **Large repo:** 500+ branches. `git for-each-ref` scales linearly — measure SessionStart at {2, 50, 200, 500} branches. Expected 100ms+ at 500.
2. **Slow network:** simulate 2s lat to api.github.com. Verify `timeout 5 gh ...` returns at 5s and **fails open** with stderr warning (§7.2).
3. **GitHub down / DNS failure:** `gh pr list` non-zero in <1s — confirm no retries.
4. **Rate-limited gh:** `gh api rate_limit` shows 0 remaining. Graceful degradation to "allow with warning."
5. **Cold cache (first session in repo):** empty/missing cache file → SessionStart <300ms with empty stale-count, NEVER blocks on `gh`.
6. **Cache contention:** two Claude sessions in worktrees of same repo run `post-merge` concurrently. PID-file lock must serialize.
7. **`git cherry` on 1000-commit branch:** O(commits) — verify <500ms even at scale.
8. **Compound trigger:** Edit on a file → user-global hook + plugin hook → total compound <100ms.
9. **`post-merge` on repo with 50 stale-merged branches:** must complete <10s using batched gh call (NOT 50× sequential).
10. **macOS bash 3.2 quirks:** verify no `declare -A`, `mapfile`, `${var,,}`, `readarray`. CI matrix should include `bash --version 3.2` runner.

---

## 8. Open Performance Questions for Marcus

1. **`gh` call dedup across the two push hooks** (Claude-side §6.2.1 + `.githooks/pre-push` §6.3.2). Recommend (a) Claude-side writes 60s-TTL cache; `.githooks/pre-push` reads it — halves push latency. Alternative (b) accept doubled cost as belt-and-suspenders.
2. **PostToolUse nudge-hook fire-rate ceiling.** §6.6 fires on EVERY Bash cmd. At 15ms × hundreds/session = 5–10s cumulative session overhead. Acceptable, or add 60s same-nudge dedup?
3. **`gh pr list --limit 1` correctness.** Brainstorm uses `--limit 1` in §6.3.2; if a branch has both an open and closed PR (rare), result picks first sort-order, possibly wrong one. Trade-off: ~50ms saved vs occasional false allow.
4. **`git_status_audit.py` rewrite to bash?** Saves 29ms startup but loses JSON ergonomics. Only worth it if it ends up on a frequent-fire path (currently it does not — keep Python).
5. **Telemetry.** Should hooks log own runtime to `${CLAUDE_PLUGIN_DATA}/perf.log` for regression detection in production, or test-harness only?
