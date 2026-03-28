# /memory-promote — Example Output

## Input
Running after 3 sessions where the same hexagonal architecture pattern kept appearing in domain.md
and in session corrections.

## Output

```
🔍 Gathering evidence from last 14 days...
  Session files found: 4
  domain.md entries: 12

📊 Pattern analysis...

──────────────────────────────────────────────
Candidate: hexagonal-arch
Evidence: domain.md entry + mentioned in 3 sessions
  "Ports and adapters: domain logic goes in core/, adapters in infra/"
  "Never import framework types into domain/ — only pure interfaces"
  "Application services orchestrate, domain models validate"
Confidence: High (3 sessions, clearly reusable)
Proposed skill: hexagonal-arch

? Approve / Skip / Rename? → Approved

? Where should this skill be generated?
  1. Global — ~/.claude/skills/hexagonal-arch/SKILL.md (all sessions)
  2. Repo  — .claude/skills/hexagonal-arch/SKILL.md (this repo only)
→ Global

✓ Generated: ~/.claude/skills/hexagonal-arch/SKILL.md (stub — fill in TODOs)
✓ domain.md updated:
    → see skill: hexagonal-arch (global)

──────────────────────────────────────────────
Candidate: null-return-policy
Evidence: domain.md entry + mentioned in 2 sessions
  "Repository methods return null for not-found — never throw"
Confidence: Medium (2 sessions)
Proposed skill: null-return-policy

? Approve / Skip / Rename? → Skip

──────────────────────────────────────────────
Candidate: legacy-adapter
Evidence: domain.md entry only, 1 session
Confidence: Low — skipping (use --force to override)

──────────────────────────────────────────────

memory-promote complete:
  ✓ Generated: ~/.claude/skills/hexagonal-arch/SKILL.md
  ✓ domain.md entry replaced with pointer
  · Skipped: 1 candidate (user), 1 candidate (low confidence)
```
