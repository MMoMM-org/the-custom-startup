---
spec: 001-memory-claude
document: plan
status: pending
---

# Implementation Plan — Memory + CLAUDE.md System (M2)

## Goal

Build the file-based memory system for TCS repos: `docs/ai/memory/` structure, modular CLAUDE.md templates, Python hook infrastructure (based on claude-reflect), and four tcs-helper skills (memory-add, memory-sync, memory-cleanup, memory-promote) plus the setup onboarding skill.

## Architecture Summary

Skills in `plugins/tcs-helper/skills/`. Templates in `plugins/tcs-helper/templates/`. No new plugin infrastructure needed — tcs-helper already exists.

## Phases

- [ ] [Phase 1: Templates + Directory Structure](phase-1.md)
- [ ] [Phase 2: memory-add Skill + Python Infrastructure](phase-2.md)
- [ ] [Phase 3: memory-sync Skill](phase-3.md)
- [ ] [Phase 4: memory-cleanup Skill](phase-4.md)
- [ ] [Phase 5: memory-promote Skill](phase-5.md)
- [ ] [Phase 6: tcs-helper:setup Skill](phase-6.md)

## Dependencies

- Phase 2 requires Phase 1 complete (templates define the target structure for routing)
- Phases 3, 4, 5 can be built in parallel after Phase 2
- Phase 6 (setup) requires Phase 2 complete (setup installs Phase 2's hooks via merge_hooks.py)

## Notes

- tcs-helper plugin already exists at `plugins/tcs-helper/`
- Python scripts and hooks are based on claude-reflect's architecture; queue format is compatible
- Phase 6 (setup) installs the hooks from Phase 2 — no manual wiring needed
- All skills follow TCS SKILL.md format with YAML frontmatter; code-first where possible
