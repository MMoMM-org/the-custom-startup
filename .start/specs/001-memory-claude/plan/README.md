---
spec: 001-memory-claude
document: plan
status: pending
---

# Implementation Plan — Memory + CLAUDE.md System (M2)

## Goal

Build the file-based memory system for TCS repos: `docs/ai/memory/` structure, modular CLAUDE.md templates, and four tcs-helper skills (memory, memory-sync, memory-cleanup, memory-promote) plus the setup onboarding skill. `/memory` replaces claude-reflect for TCS repos.

## Architecture Summary

Skills in `plugins/tcs-helper/skills/`. Templates in `plugins/tcs-helper/templates/`. No new plugin infrastructure needed — tcs-helper already exists.

## Phases

- [ ] [Phase 1: Templates + Directory Structure](phase-1.md)
- [ ] [Phase 2: memory Skill (capture + routing)](phase-2.md)
- [ ] [Phase 3: memory-sync Skill](phase-3.md)
- [ ] [Phase 4: memory-cleanup Skill](phase-4.md)
- [ ] [Phase 5: memory-promote Skill](phase-5.md)
- [ ] [Phase 6: tcs-helper:setup Skill](phase-6.md)

## Dependencies

- Phase 2 requires Phase 1 complete (templates define the target structure for routing)
- Phases 3, 4, 5 can be built in parallel after Phase 2
- Phase 6 (setup) requires Phases 1–5 complete (setup generates the structures all other skills maintain)

## Notes

- tcs-helper plugin already exists at `plugins/tcs-helper/`
- claude-reflect is NOT a dependency — `/memory` absorbs its functionality; existing queue files are compatible
- All skills follow TCS SKILL.md format with YAML frontmatter
