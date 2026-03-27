---
name: memory-cleanup
description: "Use when the memory bank is growing too large, memory.md approaches 200 lines, or near-duplicate entries have accumulated. Run monthly for routine maintenance."
user-invocable: true
argument-hint: "[--dry-run]"
allowed-tools: Read, Write, Edit, Bash
---

## Persona

**Active skill: tcs-helper:memory-cleanup**

Review and prune the memory bank. Always show candidates to the user before any changes.

## Interface

```
Candidate {
  file: string
  entry: string
  operation: archive | prune | consolidate
  approved: boolean
}

State {
  candidates: Candidate[]
  dryRun: boolean    // --dry-run flag
}
```

## Constraints

**Always:**
- Show candidates before acting — no silent changes.
- Use archive not delete for resolved troubleshooting.
- Update memory.md index after any file change.
- Skip changes when `--dry-run` is set; report what would change instead.

**Never:**
- Delete historical decisions — only archive if explicitly superseded and user confirms.
- Remove TODOs or roadmap items.
- Act without user review.

## Workflow

### 1. Scan all category files

Read all 6 category files in `docs/ai/memory/`. Build a list of candidates for each operation:

**Troubleshooting candidates:** entries containing "resolved" or "Status: resolved"
**Context candidates:** entries with a date older than 14 days (check date comments `<!-- YYYY-MM-DD -->`)
**Duplicate candidates:** entries in domain.md or general.md with highly similar meaning

### 2. Present candidates

For each non-empty candidate list:

> "Found N candidates in troubleshooting.md to archive (Status: resolved):
> 1. [entry text]
> 2. [entry text]
> Archive all / Select / Skip"

**Preservation rules — never propose these for removal:**
- Entries containing "TODO" or "ROADMAP"
- Entries in decisions.md (archive only if explicitly superseded)
- Any entry the user chose to keep in a previous run

### 3. Execute approved operations

**Archive:** Move entry to `docs/ai/memory/archive/YYYY-MM/{filename}` (create file if needed, append if exists). Remove from source file.

**Prune:** Delete entry from source file (only for explicitly stale context entries the user approved).

**Consolidate duplicates:** Show both entries, ask user which wording to keep. Write winner, remove loser.

### 4. Update index

After any changes: update `memory.md` last-updated dates for modified files.

### 5. Report

```
memory-cleanup complete:
  - troubleshooting.md: 2 entries archived → archive/2026-03/
  - context.md: 1 stale entry pruned
  - domain.md: 1 duplicate consolidated
  memory.md: 87 lines (was 134 before cleanup)
```

