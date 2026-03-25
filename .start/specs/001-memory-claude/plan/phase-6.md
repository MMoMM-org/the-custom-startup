---
phase: 6
title: tcs-helper:setup Skill
status: pending
spec: 001-memory-claude
---

# Phase 6 — tcs-helper:setup Skill

## Gate

Phases 1–5 complete. Setup generates the structures that all other memory skills maintain.

## Context

Ref: SDD §4 (tcs-helper:setup).

One-shot project onboarding. Detects stack, generates `docs/ai/` structure + all CLAUDE.md files from Phase 1 templates. Optionally configures hooks and detects relevant tcs-patterns.

## Tasks

- [ ] Create `plugins/tcs-helper/skills/setup/` directory
- [ ] Write `SKILL.md` with:
  - Workflow: detect stack → preview structure → user confirms → generate → offer optional extras
  - Stack detection: package.json, go.mod, Cargo.toml, pyproject.toml, composer.json
  - CI detection: .github/workflows/, .gitlab-ci.yml, Jenkinsfile
- [ ] Implement stack detection logic:
  - TypeScript/Node → apply `templates/stacks/typescript.md` overrides
  - Go → apply `templates/stacks/go.md` overrides
  - Python → apply `templates/stacks/python.md` overrides
  - Cloudflare Workers → apply `templates/stacks/cloudflare.md`
  - Convex → apply `templates/stacks/convex.md`
  - Fallback → generic templates
- [ ] Implement generation:
  - Create `docs/ai/memory/` directory + all 6 category files
  - Create `docs/ai/memory/memory.md` (index)
  - Create/update root `CLAUDE.md` (non-destructive: add memory section if CLAUDE.md exists)
  - Create `src/CLAUDE.md`, `test/CLAUDE.md`, `docs/CLAUDE.md`, `docs/ai/CLAUDE.md`
- [ ] Optional extras (AskUserQuestion after main generation):
  - Create `docs/adr/` directory for Architecture Decision Records
  - Add PostToolUse format-on-save hook for detected stack
  - Install relevant tcs-patterns (if tcs-patterns plugin available)

> **Hook integration decision (SDD §6 open decision — resolved):** SessionEnd hook wiring for `memory-route` is **excluded from Phase 6 scope**. Rationale: wiring a SessionEnd hook requires claude-reflect's hook infrastructure to be present, and automating hook installation from within a skill invocation introduces a mandatory external dependency. Phase 6 (setup) instead outputs post-setup instructions that tell the user to wire the hook manually if claude-reflect is installed. Hook automation is deferred to a future phase or handled by claude-reflect's own setup.
- [ ] Register skill in plugin.json

## Verification

- [ ] Running setup in a TypeScript repo generates all files with TS-specific content
- [ ] Running setup in a repo that already has CLAUDE.md does NOT overwrite it — adds memory section
- [ ] All 6 category files are created with starter content
- [ ] memory.md index correctly lists all 6 files
- [ ] Root CLAUDE.md after setup is < 100 lines
- [ ] Running setup twice is idempotent (no duplicate content)
