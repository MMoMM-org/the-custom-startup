---
phase: 6
title: tcs-helper:setup Skill
status: pending
spec: 001-memory-claude
---

# Phase 6 — tcs-helper:setup Skill

## Gate

Phases 1–5 complete (especially Phase 2 — setup installs the Phase 2 hooks and Python scripts).

## Context

Ref: SDD §4 (tcs-helper:setup).

One-shot project onboarding. Detects stack, generates `docs/ai/` structure + all CLAUDE.md files, and installs the required hooks via `merge_hooks.py` (built in Phase 2). Designed to be extendable — other skills/plugins register additional hooks through the same merge utility without modifying setup.

## Tasks

- [ ] Create `plugins/tcs-helper/skills/setup/` directory
- [ ] Write `SKILL.md` with:
  - Workflow: detect stack → preview structure → user confirms → generate → install hooks → offer optional extras
  - Implement as code where possible; AI layer only for preview/confirmation interaction
- [ ] Implement stack detection (code):
  - TypeScript/Node → apply `templates/stacks/typescript.md` overrides
  - Go → apply `templates/stacks/go.md` overrides
  - Python → apply `templates/stacks/python.md` overrides
  - Cloudflare Workers → apply `templates/stacks/cloudflare.md`
  - Convex → apply `templates/stacks/convex.md`
  - Fallback → `templates/stacks/generic.md`
  - CI detection: `.github/workflows/`, `.gitlab-ci.yml`, `Jenkinsfile`
- [ ] Implement file generation (code):
  - Create `docs/ai/memory/` directory + all 6 category files
  - Create `docs/ai/memory/memory.md` (index)
  - Create/update root `CLAUDE.md` (non-destructive: add memory section if CLAUDE.md exists)
  - Create `src/CLAUDE.md`, `test/CLAUDE.md`, `docs/CLAUDE.md`, `docs/ai/CLAUDE.md`
- [ ] Implement hook installation (code — calls `merge_hooks.py` from Phase 2):
  - Merge tcs-helper hooks into `~/.claude/settings.json` (additive, duplicates skipped)
  - Set `cleanupPeriodDays: 99999` in settings.json
  - Report which hooks were added vs already present
- [ ] Optional extras (AI — AskUserQuestion after main generation):
  - Create `docs/adr/` directory for Architecture Decision Records
  - Add PostToolUse format-on-save hook for detected stack
  - Show post-setup summary with YOLO=true usage instructions
- [ ] Register skill in plugin.json

## Verification

- [ ] Running setup in a TypeScript repo generates all files with TS-specific content
- [ ] Running setup in a repo that already has CLAUDE.md does NOT overwrite it — adds memory section
- [ ] All 6 category files are created with starter content
- [ ] memory.md index correctly lists all 6 files
- [ ] Root CLAUDE.md after setup is < 100 lines
- [ ] Running setup twice is idempotent (no duplicate content, no duplicate hooks)
- [ ] `cleanupPeriodDays: 99999` is set in `~/.claude/settings.json` after setup
- [ ] All 4 hooks (UserPromptSubmit, SessionStart, PreCompact, PostToolUse/Bash) appear in settings.json
- [ ] Existing hooks in settings.json are preserved (setup does not overwrite)
