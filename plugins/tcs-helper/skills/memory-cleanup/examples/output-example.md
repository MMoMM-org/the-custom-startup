# /memory-cleanup — Example Output

## Input
Running cleanup on a repo where:
1. `docs/ai/memory/context.md` has 3 entries older than 14 days
2. `docs/ai/memory/troubleshooting.md` has a resolved issue from last sprint
3. `docs/ai/memory/decisions.md` has a superseded decision (replaced by a newer ADR)
4. `docs/ai/memory/tools.md` has entries that drifted into prose

## Output

```
🧹 Scanning docs/ai/memory/ for cleanup candidates...

context.md — 3 stale entries (>14 days):
  [2026-02-10] "working on auth refactor" → archive (resolved, >14d)
  [2026-02-12] "debugging token expiry" → archive (resolved, >14d)
  [2026-02-14] "paused on middleware" → archive (resolved, >14d)

troubleshooting.md — 1 resolved issue:
  "SQLite WAL mode breaking tests" → archive (marked resolved)

decisions.md — 1 superseded entry:
  "Use REST for internal APIs" → archive (superseded by ADR-007: gRPC)

tools.md — 2 entries over the 250-char budget → compress:

  L26 (1104 chars) "CLAUDE_PLUGIN_ROOT / CLAUDE_PLUGIN_DATA are harness-spawned only…"
    → **`CLAUDE_PLUGIN_ROOT`/`CLAUDE_PLUGIN_DATA` reach only harness-spawned plugin
      code.** Not git-spawned hooks (`core.hooksPath`), not Bash-tool subprocesses.
      `CLAUDECODE=1` and `CLAUDE_CODE_SESSION_ID` do propagate. → Git-hook code must
      self-derive its paths. [spec-012]
      (280 chars — dropped: verification date/method, harness-context enumeration)

  L23 (912 chars) "Perf tests with caching/dedup must reset state per iteration…"
    → **Clear dedup and cache artifacts at the top of every perf-test iteration**, or vary
      the key. Otherwise iterations 2..N measure the early-exit path, not the trigger
      path. [spec-011 T3.3]
      (218 chars — dropped: the 33ms/34ms incident narrative)

tools.md — 1 entry that is not memory → evict:
  L10 "Boucle-framework as prior art for git-safety hooks" — absorbed provenance
    → docs/about/sources.md

active.md — 2.7/2.5 KB, over budget → demote the weakest admission case:
  "A CLI stub must apply --jq itself" — fails the breadth test; stub authoring
  only. → docs/ai/memory/tools.md

Approve compressions individually? [all / select / skip]
> all

Actions:
  ✓ Archived 5 entries to docs/ai/memory/archive/2026-02/
  ✓ Compressed 2 entries in tools.md
  ✓ Evicted 1 entry → docs/about/sources.md
  ✓ Demoted 1 entry from active.md → tools.md (layer now 2.4/2.5 KB)
  ✓ Removed archived entries from source files
  ✓ Updated docs/ai/memory/memory.md index

Done. 5 archived, 2 compressed, 1 evicted, 1 demoted, 0 deleted.
bank: 6.1 KB across 6 files (was 21.4 KB), largest entry 240 chars
```

Note that compressions are approved by wording, not just by operation — the user sees the
rewrite next to the original. A compression that drops an actionable claim is worse than the
bloat it removes, and only the user can spot that.
