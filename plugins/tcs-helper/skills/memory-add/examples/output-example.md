# /memory-add — Example Output

## Input
Running after a session where:
1. User corrected "no, use fd not find — it's faster and respects .gitignore"
2. User said "remember: UserRepository must return null for unknown email lookups, never throw"
3. User said "we decided to use hexagonal architecture for this project"

## Output

```
📋 Processing 3 learnings from queue...

Classifying...
  1. "no, use fd not find" → tools.md (tool correction)
  2. "remember: UserRepository must return null" → domain.md (explicit domain rule)
  3. "decided to use hexagonal architecture" → decisions.md (architecture decision)

Checking for duplicates...
  1. tools.md — no existing entry for fd/find ✓
  2. domain.md — no existing entry for UserRepository ✓
  3. decisions.md — no existing entry for hexagonal ✓

Writing...
  ✓ docs/ai/memory/tools.md — 1 entry added
  ✓ docs/ai/memory/domain.md — 1 entry added
  ✓ docs/ai/memory/decisions.md — 1 entry added
  ✓ docs/ai/memory/memory.md — index updated (3 files)

Done. 3 learnings routed, 0 skipped, 0 unclassified.
Queue cleared.
```
