---
name: memory-cleanup
description: "Use when the memory bank is growing too large, entries have drifted into prose, or near-duplicate entries have accumulated. Run monthly for routine maintenance."
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
  operation: archive | prune | consolidate | compress | evict
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
- Audit form alongside age — an entry that is current but written as prose is still a defect.
- Update memory.md index after any file change.
- Skip changes when `--dry-run` is set; report what would change instead.

**Never:**
- Delete historical decisions — only archive if explicitly superseded and user confirms.
- Remove TODOs or roadmap items.
- Act without user review.
- Drop an actionable claim while compressing — only provenance comes out.
- Delete an evicted entry instead of relocating it.

## Workflow

### 1. Scan all category files

Read all 6 category files in `docs/ai/memory/`. Build a list of candidates for each operation:

**Troubleshooting candidates:** entries containing "resolved" or "Status: resolved"
**Context candidates:** entries with a date older than 14 days (check date comments `<!-- YYYY-MM-DD -->`)
**Duplicate candidates:** entries in domain.md or general.md with highly similar meaning

**Compress candidates** — entries over the 250-character budget:

```bash
awk '/^- \*\*/ && length($0) > 250 {print FILENAME":"FNR"  "length($0)" chars"}' docs/ai/memory/*.md
```

Propose every oversized entry regardless of age. Judge each against
`memory-add/reference/category-formats.md`; take out provenance — verification dates and
methods, incident history, surplus pointers — and nothing else.

**Evict candidates** — entries that are not memory at all. Per
`memory-add/reference/category-formats.md` § "What is not an entry at all":

| Signal | Actually is | Move to |
|---|---|---|
| Qualifies or corrects a neighbouring entry | A clause of that entry | Merge into it |
| Reads as a how-to or a reusable pattern | Skill or test-suite material | A skill, or the tests' README |
| Describes another project's approach | Provenance | `docs/about/sources.md` |

Name the destination in the proposal.

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

**Compress:** Show the rewritten entry beside the original and the character count of each.
The user approves the wording, not just the operation.

**Evict:** Append to the destination named in step 2, then remove from the source file. If the
destination does not exist, ask before creating it.

### 4. Update index

After any changes: update `memory.md` last-updated dates for modified files.

### 5. Report

```
memory-cleanup complete:
  - troubleshooting.md: 2 entries archived → archive/2026-03/
  - context.md: 1 stale entry pruned
  - domain.md: 1 duplicate consolidated
  - tools.md: 4 entries compressed, 1 evicted → docs/about/sources.md
  bank: 6.1 KB across 6 files (was 21.4 KB), largest entry 240 chars
```

