# memory-sync — Example Outputs

## OK case
```
memory-sync report — 2026-03-25
  ✓ @import: @docs/ai/memory/memory.md present in CLAUDE.md
  ✓ Index: all 6 category files listed, no orphans
  ✓ Routing rules: in CLAUDE.md only
  ✓ Budget: 87/200 lines
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

## Budget warning
```
memory-sync report — 2026-03-25
  ✓ @import: present
  ✓ Index: in sync
  ⚠ Budget: 173/200 lines — approaching limit. Run /memory-cleanup to prune.
1 warning.
```
