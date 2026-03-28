# /memory-promote — Example Output

## Input
Running promotion scan on a repo where:
1. `docs/ai/memory/domain.md` has a UserRepository null-return rule that appeared in 3 sessions
2. `docs/ai/memory/tools.md` has a "use fd not find" entry confirmed across 2 sessions
3. `docs/ai/memory/general.md` has a one-off note about a conference call

## Output

```
🔍 Scanning docs/ai/memory/ for promotion candidates...

Frequency analysis:
  domain.md — "UserRepository must return null for unknown lookups" (3 sessions) ✓ candidate
  tools.md — "use fd not find — respects .gitignore" (2 sessions) ✓ candidate
  general.md — "on call with client Thu" (1 session, ephemeral) → skip

Promotion candidates:
  1. "UserRepository null-return rule" → promote to docs/ai/patterns/domain-rules.md
  2. "use fd not find" → promote to ~/.claude/includes/memory-preferences.md (global tool pref)

? Promote "UserRepository null-return rule" to docs/ai/patterns/domain-rules.md? [Y/n]
✓ Promoted

? Promote "use fd not find" to ~/.claude/includes/memory-preferences.md? [Y/n]
✓ Promoted

Done. 2 entries promoted, 1 skipped (ephemeral), 0 errors.
Source entries marked as promoted in domain.md and tools.md.
```
