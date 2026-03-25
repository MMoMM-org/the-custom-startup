---
phase: 5
title: memory-promote Skill
status: pending
spec: 001-memory-claude
---

# Phase 5 — memory-promote Skill

## Gate

Phase 2 complete. [parallel: true] — can run alongside phases 3 and 4.

## Context

Ref: SDD §3.4 (memory-promote), `docs/concept/tcs-vision.md` Domain Knowledge Lifecycle.

Detects mature domain patterns in `docs/ai/memory/domain.md` and proposes them as `tcs-patterns` skill candidates. Uses the reflect-skills analysis mechanism internally. After promotion, replaces the domain.md entry with a pointer to the skill.

## Tasks

- [ ] Create `plugins/tcs-helper/skills/memory-promote/` directory
- [ ] Write `SKILL.md` with:
  - Workflow: read domain.md → analyze for patterns → propose candidates → on approval → generate skill stub + replace with pointer
  - Pattern detection criteria (see SDD §3.4): repeats across sessions, reusable arch pattern, frequently referenced
- [ ] Implement pattern detection using reflect-skills analysis:
  - Read `docs/ai/memory/domain.md`
  - Cross-reference with session history (via reflect-skills scan of `~/.claude/projects/`)
  - Score entries by repetition + reusability
- [ ] Skill candidate proposal format:
  - What pattern was detected
  - Evidence (how many times seen, in which sessions)
  - Proposed skill name and plugin location (tcs-patterns or tcs-workflow)
  - Confidence: High / Medium / Low
- [ ] On user approval:
  - Generate minimal SKILL.md stub in correct plugin
  - Replace `domain.md` entry with: `→ see [tcs-patterns:skill-name](link)`
  - Update memory.md index
- [ ] Register skill in plugin.json

## Verification

- [ ] Given a domain.md with repeated hexagonal architecture notes, proposes tcs-patterns:hexagonal as candidate
- [ ] Confidence score reflects evidence quality (1 session = Low, 5+ sessions = High)
- [ ] After approval, domain.md entry is replaced with pointer (not deleted)
- [ ] Generated SKILL.md stub has valid frontmatter and placeholder content
- [ ] When tcs-patterns is not installed, stub is generated in `docs/ai/memory/promoted-skills/` with a migration note
- [ ] Running on a domain.md with no promotable patterns reports "no candidates found"
