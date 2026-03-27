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
# List all .md files in docs/ai/memory/ (excluding archive/)
find docs/ai/memory -maxdepth 1 -name '*.md' | sort
# Count lines in memory.md
wc -l docs/ai/memory/memory.md
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

**Check 4: No routing rules in memory.md**
- Read docs/ai/memory/memory.md
- If it contains lines matching routing patterns (→ general.md, → tools.md, etc.): WARN

**Check 5: memory.md line budget**
- If line count ≥ 200: ERROR — "memory.md at budget limit"
- If line count ≥ 160: WARN — "memory.md approaching budget (N/200 lines)"
- Otherwise: OK

### 3. Report

```
memory-sync report:
  ✓ @import present in CLAUDE.md
  ✓ All 6 category files listed in memory.md
  ✓ No orphaned files
  ✓ Routing rules in CLAUDE.md (not memory.md)
  ⚠ memory.md: 164/200 lines — approaching budget
```

If issues found and `--fix` passed: apply auto-fixable items (missing @import only); flag manual items.


