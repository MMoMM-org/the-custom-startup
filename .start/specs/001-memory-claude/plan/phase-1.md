---
phase: 1
title: Templates + Directory Structure
status: pending
spec: 001-memory-claude
---

# Phase 1 — Templates + Directory Structure

## Gate

No gates. This is the foundation phase.

**Prerequisite:** `plugins/tcs-helper/` must already exist (it does — tcs-helper is an existing plugin). This phase extends it, not replaces it.

## Context

Ref: SDD §1 (Memory Structure), §2 (CLAUDE.md Design), §4 (setup templates).

This phase creates the template files that `tcs-helper:setup` will use to generate repo memory structures, and documents the target layout. No runtime skills are built here — only the templates and documentation.

## Tasks

- [ ] Create `plugins/tcs-helper/templates/` directory structure
- [ ] Write generic root `CLAUDE.md` template (`templates/claude-root.md`)
  - < 100 lines, routing rules section, @import for memory.md, stack placeholder
- [ ] Write `src/CLAUDE.md` template (`templates/claude-src.md`)
  - TDD rules, SDD contract reference, import conventions placeholder
- [ ] Write `test/CLAUDE.md` template (`templates/claude-test.md`)
  - Test naming, coverage expectations, test data patterns
- [ ] Write `docs/CLAUDE.md` template (`templates/claude-docs.md`)
  - Documentation structure, when to update memory vs create new doc
- [ ] Write `docs/ai/CLAUDE.md` template (`templates/claude-ai.md`)
  - Memory bank maintenance rules, category definitions, when to run which skill
- [ ] Write `docs/ai/memory/memory.md` template (`templates/memory-index.md`)
  - Index format with Critical Documentation section, ≤ 200 line budget notice
- [ ] Write category file templates (one per category, with starter content and guidance comments):
  - `templates/memory-general.md`
  - `templates/memory-tools.md`
  - `templates/memory-domain.md`
  - `templates/memory-decisions.md`
  - `templates/memory-context.md`
  - `templates/memory-troubleshooting.md`
- [ ] Write Scope × Lifetime routing reference (`templates/routing-reference.md`)
  - Table mapping learning types to files; imported by memory-route skill
- [ ] Write stack-specific template overrides in `templates/stacks/` (consumed by Phase 6):
  - `templates/stacks/typescript.md` — strict mode, import order, no `any` types
  - `templates/stacks/go.md` — gofmt, error handling, module conventions
  - `templates/stacks/python.md` — type hints, ruff config, pyproject conventions
  - `templates/stacks/cloudflare.md` — Workers/Pages patterns
  - `templates/stacks/convex.md` — Convex database patterns
  - `templates/stacks/generic.md` — fallback for undetected stacks
- [ ] Update `plugins/tcs-helper/.claude-plugin/plugin.json` to register new templates directory

## Verification

- [ ] All template files exist and are valid markdown
- [ ] CLAUDE.md templates are < 100 lines each
- [ ] memory-index template has the Critical Documentation section, Archive section comment, and ≤ 200 line guidance
- [ ] Routing reference table covers all 6 categories with clear examples
- [ ] All 6 `templates/stacks/` files exist including `generic.md` fallback
