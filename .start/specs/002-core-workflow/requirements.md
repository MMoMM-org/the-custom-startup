---
spec: 002-core-workflow
document: requirements
status: placeholder — specify in dedicated session
---

# PRD — Core Workflow Rebuild (M1)

## Summary

Renames `tcs-start` → `tcs-workflow` and absorbs the best skills from obra/superpowers, citypaul/.dotfiles, and centminmod into the core workflow plugin.

## Key Deliverables

### Plugin Rename
- `tcs-start` → `tcs-workflow` across all files, manifests, docs
- Migration path for existing users (backward-compat aliases or clear upgrade guide)

### New Skills
- `tcs-workflow:tdd` — RED-GREEN-REFACTOR iron law (from superpowers:test-driven-development)
- `tcs-workflow:verify` — evidence-before-claims gate (from superpowers:verification-before-completion)
- `tcs-workflow:receive-review` — respond to code review with rigor (from superpowers:receiving-code-review)
- `tcs-workflow:parallel-agents` — explicit parallel dispatch (from superpowers:dispatching-parallel-agents)
- `tcs-workflow:guide` — orientation skill: when to use each skill (from superpowers:using-superpowers pattern)
- `tcs-helper:git-worktree` — isolated branch workspaces (from superpowers:using-git-worktrees)
- `tcs-helper:finish-branch` — merge/PR/discard decision (from superpowers:finishing-a-development-branch)

### Enhanced Existing Skills
- `tcs-workflow:brainstorm` — add spec-review subagent loop (from superpowers:brainstorming)
- `tcs-workflow:debug` — add iron-law anti-shortcut discipline (from superpowers:systematic-debugging)
- `tcs-workflow:review` — add dispatch pattern with BASE_SHA/HEAD_SHA (from superpowers:requesting-code-review)
- `tcs-workflow:implement` — add fresh-subagent-per-task + two-stage review (from superpowers:subagent-driven-development)
- `tcs-workflow:specify-plan` — add explicit RED/GREEN/REFACTOR/MUTATE steps per task (from citypaul planning)

### TDD+SDD Integration
- Every PLAN task must include RED/GREEN/REFACTOR steps anchored to an SDD contract
- `tcs-workflow:implement` enforces TDD before dispatching each task
- See `docs/concept/tdd-sdd-integration.md` for full design

## Reference

- `docs/concept/overlap-analysis.md` — complete absorption table for all sources
- `docs/concept/tcs-vision.md` — plugin architecture and workflow diagram
- `docs/concept/tdd-sdd-integration.md` — TDD+SDD integration design
