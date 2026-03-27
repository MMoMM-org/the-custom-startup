---
phase: 4
title: memory-cleanup Skill
status: pending
spec: 001-memory-claude
---

# Phase 4 — memory-cleanup Skill

## Gate

Phase 2 complete. [parallel: true] — can run alongside phases 3 and 5.

## Context

Ref: SDD §3.3 (memory-cleanup).

Reduces token load over time. Archives resolved troubleshooting, prunes stale context, deduplicates entries. Follows centminmod cleanup workflow with preservation rules.

## Tasks

- [ ] Create `plugins/tcs-helper/skills/memory-cleanup/` directory
- [ ] Write `SKILL.md` with:
  - Workflow: scan → identify candidates → present for review → archive/prune → update index
  - Preservation rules (never delete todos, roadmaps, or historical decisions)
- [ ] Implement cleanup operations:
  - `troubleshooting.md`: entries with "resolved" marker → `docs/ai/memory/archive/YYYY-MM/`
  - `context.md`: entries older than 2 weeks without update → flag for user decision
  - `domain.md` + `general.md`: identify near-duplicates (similar meaning) → consolidate
  - `decisions.md`: entries describing superseded decisions → mark, offer to archive
- [ ] Human-in-the-loop: always present candidates before acting; no silent deletions
- [ ] Archive path: `docs/ai/memory/archive/YYYY-MM/filename.md`
- [ ] Register skill in plugin.json

## Verification

- [ ] Resolved troubleshooting entry is moved to archive, not deleted
- [ ] Stale context entry is flagged to user, not automatically removed
- [ ] Duplicate entries are surfaced for user to choose which to keep
- [ ] memory.md index is updated after cleanup
- [ ] Running cleanup on a clean repo reports "nothing to clean"
- [ ] No entries are silently deleted without user confirmation
