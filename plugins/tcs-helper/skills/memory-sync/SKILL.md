---
name: memory-sync
description: "Use when memory files may be out of sync with CLAUDE.md imports, the memory.md index may be stale, or after adding or removing memory category files. Triggers on: sync memory, check memory structure, memory out of sync."
user-invocable: true
argument-hint: "[--fix]"
allowed-tools: Read, Write, Edit, Bash
---

## Persona

**Active skill: tcs-helper:memory-sync**

Audit the memory bank structure and report (or fix) synchronization issues.

## Interface

```
CheckResult {
  id: string
  status: OK | WARN | ERROR
  message: string
  autoFixable: boolean
}

State {
  results: CheckResult[]
  fix: boolean    // --fix flag
}
```

## Constraints

**Always:**
- Report clearly even when everything is OK.

**Never:**
- Modify memory content — only add missing structural entries.
- Delete entries from memory.md — that is memory-cleanup's job.
- Add `@` imports for files that are not strictly needed on every session start.

## Workflow

### 1. Gather state

```bash
# List category files in docs/ai/memory/ (excluding archive/ and the non-category files)
find docs/ai/memory -maxdepth 1 -name '*.md' \
  ! -name 'memory.md' ! -name 'routing-reference.md' | sort
# Size the bank in bytes — entries are single long lines, so line counts mislead
wc -c docs/ai/memory/*.md
# Check CLAUDE.md for @imports
grep '@docs/ai/memory' CLAUDE.md
```

### 2. Run checks

**Check 1: CLAUDE.md has @import for memory.md**
- Read CLAUDE.md — look for `@docs/ai/memory/memory.md`
- If missing: WARN — "CLAUDE.md is missing @docs/ai/memory/memory.md import"
- If `--fix`: add `@docs/ai/memory/memory.md` to the Memory & Context section

**Check 2: Audit each @ import**
- For each `@` line in CLAUDE.md: verify the file exists
- Flag broken @imports (file doesn't exist)
- Note: additional @imports beyond memory.md should be justified — report them for review

**Check 3: memory.md lists all category files**
- Read docs/ai/memory/memory.md
- Compare listed files against files found in Step 1
- WARN for each file in filesystem but not in index (orphan)
- WARN for each file in index but not in filesystem (stale entry)
- Two files are never orphans: `memory.md` (it *is* the index) and `routing-reference.md`
  (routing metadata consumed by `/memory-add`, not session content). The Step 1 glob already
  excludes both — do not reintroduce them by globbing `*.md` unfiltered.

**Check 4: No routing rules in memory.md**
- Read docs/ai/memory/memory.md
- If it contains lines matching routing patterns (→ general.md, → tools.md, etc.): WARN

**Check 5: memory bank size budget**

Measure bytes, not lines. Entries are single long lines, so a line count says nothing about
cost — a 14-line file and a 36-line file here differ by 8 KB.

- Sum `wc -c` across the category files (excluding `memory.md` and `archive/`)
- If ≥ 24 KB: ERROR — "memory bank over budget (N KB) — run /memory-cleanup"
- If ≥ 16 KB: WARN — "memory bank approaching budget (N/24 KB)"
- Otherwise: OK

Calibration: a bank of entries written in canonical form lands around 6 KB. 16 KB means prose
has crept back in; 24 KB is roughly where the bank was before it was first compressed.

**Check 6: entry form**

```bash
awk '/^- \*\*/ && length($0) > 250 {print FILENAME":"FNR"  "length($0)" chars"}' docs/ai/memory/*.md
```

- WARN for each entry over 250 characters, naming file, line, and length
- Recommend `/memory-cleanup`, which owns the compression workflow — memory-sync only reports

### 3. Report

```
memory-sync report:
  ✓ @import present in CLAUDE.md
  ✓ All 6 category files listed in memory.md
  ✓ No orphaned files
  ✓ Routing rules in CLAUDE.md (not memory.md)
  ⚠ Bank: 18.2/24 KB — approaching budget
  ⚠ Form: 3 entries over 250 chars (tools.md:26 1104, general.md:7 892, tools.md:18 861)
    → run /memory-cleanup
```

If issues found and `--fix` passed: apply auto-fixable items (missing @import only); flag manual items.


