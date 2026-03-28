---
phase: 5
title: memory-promote Skill
status: completed
spec: 001-memory-claude
---

# Phase 5 — memory-promote Skill

## Gate

Phase 2 complete. [parallel: true] — can run alongside phases 3 and 4.

## Context

Ref: SDD §3.4 (memory-promote), `docs/concept/tcs-vision.md` Domain Knowledge Lifecycle.

Detects mature domain patterns in `docs/ai/memory/domain.md` and proposes them as skill candidates (analogous to [reflect-skills](https://github.com/BayramAnnakov/claude-reflect/blob/main/commands/reflect-skills.md)). Works primarily with condensed material (domain.md + session summaries). After promotion, replaces the domain.md entry with a pointer to the generated skill.

## Tasks

- [x] Create `plugins/tcs-helper/skills/memory-promote/` directory
- [x] Write `SKILL.md` with:
  - Workflow: read domain.md → analyze for patterns → propose candidates → on approval → ask target scope → generate skill stub + replace with pointer
  - Pattern detection criteria (see SDD §3.4): repeats across sessions, reusable arch pattern, frequently referenced
- [x] Implement pattern detection:
  - Primary: analyse `docs/ai/memory/domain.md` (condensed material, always available)
  - Secondary: check session summaries in `~/.claude/projects/<repo>/` if available (boost confidence)
  - Score entries by repetition + reusability
- [x] Skill candidate proposal format:
  - What pattern was detected
  - Evidence (condensed summary + session count if available)
  - Proposed skill name
  - Confidence: High / Medium / Low
- [x] On user approval:
  - Ask: **global** (`~/.claude/skills/<skill-name>/SKILL.md`) or **repo** (`.claude/skills/<skill-name>/SKILL.md`)
  - Note to user: project-level skills don't exist in Claude Code — only global or repo
  - Generate minimal `SKILL.md` stub with valid frontmatter + `# TODO` placeholder
  - Replace `domain.md` entry with: `→ see skill: <skill-name>`
  - Update memory.md index
- [x] Register skill in plugin.json

## Verification

- [x] Given a domain.md with repeated hexagonal architecture notes, proposes it as skill candidate
- [x] Confidence score reflects evidence quality (domain.md alone = Low, session evidence available = High)
- [x] Skill is generated at user-chosen global or repo path (NOT in tcs-patterns)
- [x] User is informed that project-level skills are not supported
- [x] After approval, domain.md entry is replaced with pointer (not deleted)
- [x] Generated SKILL.md stub has valid frontmatter and placeholder content
- [x] Running on a domain.md with no promotable patterns reports "no candidates found"
