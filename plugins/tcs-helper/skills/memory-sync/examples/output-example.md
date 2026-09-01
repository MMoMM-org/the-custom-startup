# memory-sync — Example Outputs

## OK case
```
memory-sync report — 2026-03-25
  ✓ @import: @docs/ai/memory/memory.md present in CLAUDE.md
  ✓ Index: all 6 category files listed, no orphans
  ✓ Routing rules: in CLAUDE.md only
  ✓ Bank: 6.1/24 KB
  ✓ Form: all 23 entries ≤ 250 chars
All checks passed.
```

## Missing @import
```
memory-sync report — 2026-03-25
  ✗ @import: @docs/ai/memory/memory.md NOT found in CLAUDE.md
    Fix: add "@docs/ai/memory/memory.md" under "## Memory & Context" in CLAUDE.md
    Run with --fix to apply automatically.
  ✓ Index: all 6 category files listed
  ...
1 issue found.
```

## Budget and form warnings
```
memory-sync report — 2026-03-25
  ✓ @import: present
  ✓ Index: in sync
  ⚠ Bank: 18.2/24 KB — approaching limit.
  ⚠ Form: 3 entries over 250 chars
      tools.md:26    1104 chars
      general.md:7    892 chars
      tools.md:18     861 chars
    → run /memory-cleanup to compress
2 warnings.
```

Bank size and entry form usually fail together: a bank goes over budget because entries drifted
into prose, not because too many were added. Compressing is the fix; pruning is not.

## Broken @import
```
memory-sync report — 2026-03-25
  ✗ @import: @AGENTS.md referenced in CLAUDE.md but the file does not exist
    Fix: create the file, or remove the import line.
  ✓ Index: in sync
1 issue found.
```
