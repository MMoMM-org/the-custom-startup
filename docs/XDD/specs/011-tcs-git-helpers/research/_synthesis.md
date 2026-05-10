# Research Synthesis — `tcs-git-helpers` (Pre-PRD)

**Date:** 2026-05-08
**Sources:** 5 research lenses (requirements, technical, security, performance, integration). Full reports in this directory: `requirements.md`, `technical.md`, `security.md`, `performance.md`, `integration.md`.

This document distills cross-cutting findings, resolves conflicts, locks decisions for PRD, and tracks deferred questions. It is the input to `xdd-prd`.

---

## 1. Conflicts Resolved (locked for PRD)

### C1 — `worktree-exit-guard` event choice (§6.2.4 of brainstorm)

| Researcher | Position | Evidence |
|---|---|---|
| technical | `WorktreeRemove` primary, `SessionEnd` advisory fallback | docs say WorktreeRemove exists |
| integration | **`PreToolUse:ExitWorktree`** | Boucle's `worktree-guard` uses it; `ExitWorktree` is in this session's deferred-tool list (verified native tool); docs explicitly mark `WorktreeRemove` and `SessionEnd` as **non-blockable** |

**Resolution:** Lock **`PreToolUse:ExitWorktree`**. Integration's evidence is concrete. Brainstorm §6.2.4 + §9 #7 to be amended in PRD.

### C2 — `mergeMethod` cross-check (brainstorm §7.4)

`gh pr view --json mergeMethod` returns `Unknown JSON field: "mergeMethod"` (verified gh 2.88.1). Brainstorm has a bug.

**Resolution:** Replace cross-check with merge-commit parent count:
```bash
SHA=$(gh pr view "$N" --json mergeCommit --jq '.mergeCommit.oid')
git rev-list --parents -n 1 "$SHA" | awk '{print NF-1}'   # 1=squash/rebase, 2=merge
```
Primary detector remains `git cherry`; this is advisory cross-check only.

### C3 — Master override `CLAUDE_ALLOW_GIT_BAD_OPS` (§4.2 / §6.2.1)

| Researcher | Position |
|---|---|
| security | Drop entirely OR gate with date-stamp value (`=$(date +%Y-%m-%d)`) — binary master is reflexively settable |
| requirements | Single-shot semantics for ALL overrides (US-OV.1) |

**Resolution (combined):** Keep master override, but apply ALL of:
1. **Single-shot:** consumed on first match (per US-OV.1)
2. **Audit-logged distinctly** in `${CLAUDE_PLUGIN_DATA}/audit/overrides.jsonl` with `master=true` flag
3. **Stderr loud-warning** on every consumption ("⚠ MASTER OVERRIDE — strongly prefer granular `CLAUDE_ALLOW_<X>=1`")
4. **No date-stamp gate** for v1.0 (excessive friction; reconsider for v1.1 if abused)

---

## 2. Decisions Locked for PRD (research-informed defaults)

### D1 — Hook entry-point split (bash hot path, python cold path)

- **Bash:** `block-bad-git-ops.sh`, `pre-edit-branch-check.sh`, `nudge-hook.sh`, `session-start-brief.sh`, `worktree-exit-guard.sh`, all `.githooks/*`, `lib/git_state.sh`, `lib/config_parser.sh`
- **Python:** only `git_status_audit.py` (skill backend, latency-tolerant; ~30ms cold-start unacceptable on hot paths)

### D2 — `${CLAUDE_PLUGIN_DATA}` cache structure

```
${CLAUDE_PLUGIN_DATA}/
├── cache/
│   ├── <repo-hash>-stale-cache.tsv     # SessionStart-readable (header-comment + TSV rows)
│   ├── <repo-hash>-stale-cache.json    # /status --json output (Python writes both)
│   ├── <repo-hash>-pr-state.json       # 60s-TTL push hook cache
│   └── <repo-hash>.lock                # PID-file lock (no flock on bash 3.2)
└── audit/
    └── overrides.jsonl                  # append-only; rotate at 1MB
```

`<repo-hash>` = `sha1sum <<<"$(git rev-parse --show-toplevel)"` first 12 chars.

Hybrid TSV-with-header for stale cache: header `# updated_iso=...` + TSV body. Saves `jq` cold-start on SessionStart hot path (measured savings: 5–10ms).

### D3 — Performance budgets per hook

| Hook | p50 budget | p99 limit | Mandate |
|---|---:|---:|---|
| `session-start-brief.sh` | **150ms** | 300ms | local-only, NO `gh`, cache-read-only |
| `block-bad-git-ops.sh` non-push | 20ms | 80ms | bash regex only |
| `block-bad-git-ops.sh` push | 30ms (cached) / 800ms (uncached) | 5000ms (=`timeout 5`) | 60s TTL cache, batch with `.githooks/pre-push` |
| `pre-edit-branch-check.sh` | 30ms | 80ms | local git only |
| `nudge-hook.sh` | 15ms | 50ms | **pure bash, NO git, NO gh** |
| `worktree-exit-guard.sh` | 150ms | 500ms | local git only (`git cherry`) |
| `.githooks/pre-commit` | 100ms | 300ms | per-commit |
| `.githooks/commit-msg` | 30ms | 100ms | regex + 3ms config parse |
| `.githooks/pre-push` | 800ms | 5000ms | reads Claude-side cache when present |
| `.githooks/post-merge` | 2000ms | 10000ms | background-friendly; **must batch gh call** |

Empirical baseline measured today: SessionStart simulation 58ms, leaving 5× headroom on 300ms.

### D4 — `gh` call deduplication

Claude-side push hook writes `${CLAUDE_PLUGIN_DATA}/cache/<repo-hash>-pr-state.json` with 60s TTL. `.githooks/pre-push` reads this cache before making its own `gh` call. Halves real-world push latency.

`post-merge` MUST use single batched call: `gh pr list --state merged --json headRefName,number,mergedAt --limit 100`. Per-branch loops are forbidden (rate-limit and latency).

### D5 — `.config` parser implementation (bash 3.2 compatible)

Use `printf -v` for assignment-by-name (no `eval`, no `source`). Allowlist-keys-only via case glob. Strict regex `^[A-Z_][A-Z0-9_]*=.*$` per line. Comments stripped. Unknown keys logged + skipped. Bundled implementation sketch in `technical.md` §5.3. Per-commit cost measured at 3ms — no memoization needed.

### D6 — Single-shot override semantics (US-OV.1)

Mechanism: hook reads env var, if set → consumes (allows operation), unsets via `unset` before exiting. Subsequent calls re-deny. Caveat: `unset` only affects the hook's process; the env var remains in Claude's parent context. So "consumed" really means "logged, allowed once, asked to be re-set per attempt."

For true one-shot: hook also writes a sentinel to `${CLAUDE_PLUGIN_DATA}/cache/override-consumed-<env-var>` and refuses re-consumption within 5s window. Crude but effective against reflexive double-tap.

### D7 — Audit log format (US-OV.2)

JSONL append-only at `${CLAUDE_PLUGIN_DATA}/audit/overrides.jsonl`:
```json
{"ts":"2026-05-08T14:23:11Z","repo":"/path/to/repo","branch":"feat/foo","hook":"block-bad-git-ops","env_var":"CLAUDE_ALLOW_PUSH_TO_CLOSED_PR","master":false,"command":"git push origin feat/foo","pattern":"git\\s+push\\b"}
```
Rotate at 1MB → `.1`/`.2`. Audit-write failure does NOT block the underlying hook decision (US-OV.2 AC4).

### D8 — Block edits to git internals (security §5)

Add new PreToolUse:Edit|Write|NotebookEdit hook (or extend `pre-edit-branch-check.sh`) to deny edits to `.githooks/*`, `.git/config`, `.git/hooks/*` UNLESS `TCS_GIT_HELPERS_SETUP_ACTIVE=1` is set in env. Setup skill exports this in a `(subshell)` block to prevent leakage.

`git config core.hooksPath ...` goes via Bash hook, not Edit hook — `block-bad-git-ops.sh` adds a guarded pattern that allows it ONLY when sentinel is set.

### D9 — Conflict detection on setup (integration §5)

Setup aborts (does not proceed) when detecting:
- Husky (any version) — `.husky/_/` files OR `package.json` references
- lefthook — `lefthook.yml`/`.lefthook.yml`
- pre-commit framework (Python) — `.pre-commit-config.yaml`
- simple-git-hooks — `package.json` reference
- Custom `core.hooksPath` ≠ `.githooks` (already set to something else)

Setup warns (proceeds with confirmation) when detecting:
- Files in `.git/hooks/` that are not `.sample`
- GHA workflows referencing other PR-title checkers (only if `--with-gha`)

Reference: `references/migrating-from-husky.md` (NEW).

### D10 — Token scope check before `--with-branch-protection`

Setup parses `gh auth status` token scopes. Matrix:
- Missing `repo` → block, prompt `gh auth refresh -s repo`
- `repo` only → proceed silently
- `repo` + excessive (e.g., `admin:org`, `delete_repo`, `admin:repo_hook`) → warn + interactive confirm
- `repo` + `workflow` → silent if `--with-gha`; soft single-line warn otherwise

Reference: `references/gh-token-hygiene.md` (NEW).

---

## 3. Personas Locked (from requirements)

- **P1 Claude (the Agent)** — primary protected entity; forgetful actor whose mistakes hooks block
- **P2 Marcus (the Operator)** — installer, override-holder, recoverer
- **P3 Future TCS Adopter** — secondary v1.0 ("shouldn't break"), first-class v1.1+

---

## 4. New References Needed (added to brainstorm §6.1 list)

- `references/destructive-ops.md` — already in brainstorm; expanded to cite Boucle URLs
- `references/migrating-from-husky.md` — NEW (D9 conflict detection)
- `references/gh-token-hygiene.md` — NEW (D10 token scope)
- `references/best-practices.md` — already in brainstorm; landing page

---

## 5. Test Matrix for PLAN (worst-case scenarios)

From performance §7:

1. Large repo (500+ branches) — SessionStart at {2, 50, 200, 500} branches
2. Slow network (2s lat to api.github.com) — `timeout 5 gh` returns at 5s, fails open
3. GitHub down / DNS failure — `gh pr list` non-zero <1s, no retries
4. Rate-limited gh — graceful degradation
5. Cold cache (first session) — empty cache, no `gh` blocking
6. Cache contention (concurrent worktree sessions) — PID-file lock serializes
7. `git cherry` on 1000-commit branch — <500ms
8. Compound trigger (Edit) — user-global + plugin hook compound <100ms
9. `post-merge` on 50 stale-merged branches — <10s with batched gh
10. macOS bash 3.2 quirks — no `declare -A`, `mapfile`, `${var,,}`, `readarray`

---

## 6. Open Questions for Marcus (deferred to PRD review or SDD)

Consolidated from all 5 lenses; deduplicated. Numbered for tracking.

### Critical — Marcus must answer before PRD finalization
1. **`timeout(1)` not on macOS by default.** Bundle bash-only fallback (`(cmd) & sleep 5; kill $!`) OR document `brew install coreutils` requirement? *(Integration #1, Technical #5, Performance implicitly)*

### Important — affect PRD scope but defaultable
2. **P3 (Future TCS Adopter) v1.0 acceptance gate?** Recommend v1.0 = "shouldn't break for P3", v1.1 = "first-class onboarding". *(Requirements #7)*
3. **Branch-protection preset** for `--with-branch-protection`. Recommend: PR-required + ≥1 review + dismiss-stale + no-force-push + no-deletions + require-up-to-date. *(Brainstorm §9 #8, Integration #3)*
4. **References installed into target repo** OR plugin-internal only? Recommend: plugin-internal (single source of truth). *(Brainstorm §12 OQ2, Requirements #5)*
5. **Brief cadence** — SessionStart only, or also after `post-merge`? Recommend: SessionStart + after `post-merge` (free; cache already updated). *(Requirements #6)*

### Defer to SDD/PLAN — not PRD-blocking
6. Husky/lefthook policy — abort + migration doc confirmed (D9). *(Integration #6, locked)*
7. Single-shot mechanism implementation specifics — covered in D6.
8. Multi-account `gh` — `gh auth status --hostname <host>` before branch-protection. *(Integration #5, defer)*
9. Telemetry / `perf.log` — recommend test-harness only for v1.0. *(Performance #5)*
10. PostToolUse nudge dedup window. Recommend: 60s same-nudge dedup. *(Performance #2)*
11. `PostToolUse:Bash` JSON includes exit status — runtime probe in PLAN. *(Technical #2)*
12. PR/branch rename timing — defer to implementation phase. *(Technical #4)*

### Nice-to-have / open for v1.1
13. `.git-safe` allowlist file (Boucle). Defer to v1.1 confirmed.
14. AI commit-message generation. Out of scope confirmed.
15. Cross-repo orchestration skill. Out of scope confirmed.

---

## 7. PRD-Writer Brief (input for `xdd-prd`)

The PRD should produce `requirements.md` with:

1. **Personas:** as in §3.
2. **Goals G1–G12:** structured per `requirements.md` lens (US-G1.1, US-G2.1, ..., US-OV.1, US-OV.2). Use the user-story → acceptance-criteria format from `requirements.md`.
3. **Non-goals:** §3 of brainstorm + §6 of this synthesis (defer items).
4. **Constraints:**
   - Bash 3.2 compatibility (macOS default)
   - SessionStart ≤300ms hard limit
   - `gh` fail-open (never block on network)
   - No vendoring of Boucle source — re-implement
   - Plugin lifecycle = trust signal (disable plugin = waive Claude-side protection; `.githooks` defense in depth)
5. **Acceptance / success metrics:** measurable per-goal (e.g., "G7 verifies all destructive patterns from §6.2.1 emit `permissionDecision: deny` with reference link").
6. **Edge cases as user-facing requirements:** EC1–EC8 from `requirements.md`.
7. **Critical decisions to surface for Marcus's review:** §6 critical/important items above.

The brainstorm spec (`docs/XDD/ideas/2026-05-08-tcs-git-safety.md`) is the source-of-truth ground; PRD restates and resolves conflicts/decisions per this synthesis.

---

**End synthesis. Ready for `xdd-prd`.**
