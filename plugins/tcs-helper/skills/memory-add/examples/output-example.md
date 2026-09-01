# /memory-add — Example Output

## Input
Running after a session where:
1. User corrected "no, use fd not find — it's faster and respects .gitignore"
2. User said "remember: UserRepository must return null for unknown email lookups, never throw"
3. The session established, over some back-and-forth, that the hook silently denied every tool
   call because `jq` returned non-zero under `set -e` on malformed JSON — traced through T2.1
   to T2.4 before landing on the fix

## Output

```
📋 Processing 3 learnings from queue...

Classifying...
  1. "no, use fd not find" → tools.md (tool correction)
  2. "remember: UserRepository must return null" → domain.md (explicit domain rule)
  3. "jq exit code under set -e denies the tool call" → tools.md (tool quirk)

Checking for duplicates...
  1. tools.md — no existing entry for fd/find ✓
  2. domain.md — no existing entry for UserRepository ✓
  3. tools.md — no existing entry for jq/set -e ✓

Writing...
  ✓ docs/ai/memory/tools.md — 2 entries added
  ✓ docs/ai/memory/domain.md — 1 entry added
  ✓ docs/ai/memory/memory.md — index updated (2 files)

Done. 3 learnings routed, 0 skipped, 0 unclassified.
Queue cleared.
```

## What was written

Learnings arrive as narrative; entries are not narrative. Each was compressed to the canonical
form before being appended:

```markdown
<!-- 2026-03-25 -->
- **Use `fd`, not `find`** — respects `.gitignore` and is faster on large trees.
- **jq under `set -e` makes a hook fail closed** — a non-zero exit from malformed JSON reads
  to Claude Code as "deny tool call". → Append `2>/dev/null || true` to every jq command
  substitution in a hook meant to fail open. [spec-011 T2.4]
```

The third learning arrived with the whole debugging story attached — which task first shipped
the bug, how it was traced, that T2.4 was immune. None of that reached the entry. `[spec-011
T2.4]` is the lookup key for anyone who needs it, and git blame carries the date.
