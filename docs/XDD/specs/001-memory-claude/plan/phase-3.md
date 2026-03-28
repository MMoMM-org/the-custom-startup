---
phase: 3
title: memory-sync Skill
status: completed
spec: 001-memory-claude
---

# Phase 3 — memory-sync Skill

## Gate

Phase 2 complete. [parallel: true] — can run alongside phases 4 and 5.

## Context

Ref: SDD §3.2 (memory-sync).

Keeps `@imports` and index entries synchronized. Ensures routing rules stay in CLAUDE.md (not memory.md). Warns when approaching 200-line budget.

## Tasks

- [x] Create `plugins/tcs-helper/skills/memory-sync/` directory
- [x] Write `SKILL.md` with:
  - Workflow: scan → verify imports → check budget → report
  - Fix mode: auto-fix missing imports, flag routing-rules-in-wrong-file
- [x] Implement checks:
  - Root CLAUDE.md has `@docs/ai/memory/memory.md`
  - All category files listed in `memory.md` index
  - No orphaned files in `docs/ai/memory/` (not in index)
  - Routing rules not duplicated in `memory.md`
  - `memory.md` line count ≤ 200 (warn at 160, error at 200)
- [x] Write `examples/output-example.md` — sample sync reports: OK case, missing @import case, orphaned file case, budget warning case
- [x] Register skill in plugin.json

## Verification

- [x] Detects missing `@import` in CLAUDE.md and offers to fix
- [x] Detects orphaned memory file (exists but not in index) and offers to add
- [x] Detects routing rules in memory.md and warns to move to CLAUDE.md
- [x] Reports "OK" when everything is in sync
- [x] Correctly counts lines in memory.md and warns when approaching budget
