# /memory-cleanup — Example Output

## Input
Running cleanup on a repo where:
1. `docs/ai/memory/context.md` has 3 entries older than 14 days
2. `docs/ai/memory/troubleshooting.md` has a resolved issue from last sprint
3. `docs/ai/memory/decisions.md` has a superseded decision (replaced by a newer ADR)

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

Actions:
  ✓ Archived 5 entries to docs/ai/memory/archive/2026-02/
  ✓ Removed archived entries from source files
  ✓ Updated docs/ai/memory/memory.md index

Done. 5 entries archived, 0 deleted, 0 skipped.
```
