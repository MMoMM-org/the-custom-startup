---
title: "tcs-git-helpers — Implementation Plan"
status: draft
version: "1.0"
---

# Implementation Plan

## Validation Checklist

### CRITICAL GATES (Must Pass)

- [x] All `[NEEDS CLARIFICATION: ...]` markers have been addressed
- [x] All specification file paths are correct and exist
- [x] Each phase follows TDD: Prime → Test → Implement → Validate
- [x] Every task has verifiable success criteria
- [x] A developer could follow this plan independently

### QUALITY CHECKS (Should Pass)

- [x] Context priming section is complete
- [x] All implementation phases are defined with linked phase files
- [x] Dependencies between phases are clear (no circular dependencies)
- [x] Parallel work is properly tagged with `[parallel: true]`
- [x] Activity hints provided for specialist selection `[activity: type]`
- [x] Every phase references relevant SDD sections
- [x] Every test references PRD acceptance criteria
- [x] Integration & E2E tests defined in final phase
- [x] Project commands match actual project setup

---

## Output Schema

### PLAN Status Report

| Field | Value |
|-------|-------|
| specId | 011-tcs-git-helpers |
| title | tcs-git-helpers — Git Workflow Discipline Plugin |
| status | DRAFT |
| phases | 6 phases, all DEFINED |
| totalTasks | 43 tasks |
| parallelTasks | 26 tasks marked [parallel: true] |
| specReferences | 60+ ref tags (PRD/SDD section/line links) |
| clarificationsRemaining | 0 |

---

## Specification Compliance Guidelines

### How to Ensure Specification Adherence

1. **Before Each Phase**: Read referenced PRD/SDD sections; verify ADRs apply
2. **During Implementation**: Reference specific SDD sections in each task; cite PRD AC for tests
3. **After Each Task**: Run validation per task's `Validate` step
4. **Phase Completion**: Run phase validation task before moving to next phase

### Deviation Protocol

When implementation requires changes from the specification:
1. Document the deviation with clear rationale in the phase file
2. Obtain Marcus's approval before proceeding
3. Update SDD when the deviation improves the design
4. Record all deviations in this plan for traceability

## Metadata Reference

- `[parallel: true]` — Tasks that can run concurrently within their phase
- `[ref: PRD/M*]` or `[ref: SDD/§N]` — Links to specifications
- `[activity: type]` — Activity hint for specialist agent selection. Used types:
  - `domain-modeling` (lib/ modules)
  - `backend-api` (hook scripts, skills)
  - `integration` (gh CLI, hooks.json registration)
  - `documentation` (README, references, CHANGELOG)
  - `validate` (phase-end verification)
  - `test-fixtures` (corpus files, synthetic repos)

### Success Criteria Format

```markdown
- Success: [Criterion] `[ref: PRD/AC-X.Y]`
```

---

## Context Priming

*GATE: Read all files in this section before starting any implementation.*

**Specification**:

- `docs/XDD/specs/011-tcs-git-helpers/requirements.md` — Product Requirements (M1-M12, S1-S2, 38+ Gherkin AC)
- `docs/XDD/specs/011-tcs-git-helpers/solution.md` — Solution Design (12 ADRs, schemas, flows)
- `docs/XDD/specs/011-tcs-git-helpers/research/_synthesis.md` — Research synthesis (3 conflicts resolved, 10 decisions locked)
- `docs/XDD/specs/011-tcs-git-helpers/research/{requirements,technical,security,performance,integration}.md` — per-lens findings
- `docs/XDD/ideas/2026-05-08-tcs-git-safety.md` — Brainstorm artifact (original design, gap-review)
- `docs/ai/external/claude/hooks.md` — Cached Claude Code hooks reference

**Reference Implementations**:

- `~/.claude/hooks/block-main-edits.sh` — PreToolUse Edit/Write hook reference shape
- `/Volumes/Moon/Coding/MiYo/Kado/.githooks/{pre-commit,commit-msg}` — Existing baseline templates
- `plugins/tcs-helper/{hooks/hooks.json, .claude-plugin/plugin.json}` — Plugin layout reference

**Key Design Decisions** (from SDD §Architecture Decisions):

- **ADR-1**: `PreToolUse:ExitWorktree` for worktree-exit guard (blockable native tool, Boucle pattern)
- **ADR-2**: Bash 3.2 hot-path / Python only for `git_status_audit.py` (avoid 30ms cold-start on SessionStart)
- **ADR-3**: `.config` strict-allowlist parser using `printf -v` (no eval/source)
- **ADR-5**: Override single-shot via env-var consumption + 5s sentinel file
- **ADR-6**: 60s push-state cache shared between Claude-side and `.githooks/pre-push`
- **ADR-7**: Audit log JSONL append-only with 1MB → `.1`/`.2` rotation
- **ADR-9**: `git cherry` primary squash-merge detection; `git rev-list --parents` advisory cross-check
- **ADR-11**: `TCS_GIT_HELPERS_SETUP_ACTIVE` env-var sentinel in subshell for setup-only file edits
- **ADR-12**: Single-coder branch-protection preset (no PR-review-required)

**Implementation Context**:

```bash
# Testing
bats plugins/tcs-git-helpers/tests/bats/*.bats     # Bash unit tests for all hooks + libs
python3 -m pytest plugins/tcs-git-helpers/tests/python/  # Python tests for git_status_audit.py

# Quality
shellcheck plugins/tcs-git-helpers/scripts/**/*.sh \
           plugins/tcs-git-helpers/templates/githooks/*  # Shell linting (no .sh extension on githooks templates — invoke per-file)
ruff check plugins/tcs-git-helpers/scripts/git_status_audit.py  # Python linting

# Local plugin testing during development (DOES NOT install marketplace-style)
claude --plugin-dir plugins/tcs-git-helpers
# Inside session: /reload-plugins to pick up changes; test with /tcs-git-helpers:setup, /tcs-git-helpers:status

# Verification end-to-end (Phase 6)
bash plugins/tcs-git-helpers/tests/e2e/dogfood.sh   # Synthetic-repo flow test
bash plugins/tcs-git-helpers/tests/e2e/kado-migration.sh  # Real repo migration test (Kado)

# Plugin packaging (manual; Marcus initiates marketplace publish)
# Verify .claude-plugin/plugin.json version matches CHANGELOG.md latest entry
```

**Performance Budgets to Honor** (from SDD §Quality Requirements):

| Hook | p50 budget | p99 limit |
|---|---:|---:|
| `session-start-brief.sh` | 150ms | 300ms |
| `block-bad-git-ops.sh` non-push | 20ms | 80ms |
| `block-bad-git-ops.sh` push (cached) | 30ms | 80ms |
| `block-bad-git-ops.sh` push (uncached) | 800ms | 5000ms |
| `pre-edit-branch-check.sh` | 30ms | 80ms |
| `nudge-hook.sh` | 15ms | 50ms |
| `worktree-exit-guard.sh` | 150ms | 500ms |
| `.githooks/pre-commit` | 100ms | 300ms |
| `.githooks/commit-msg` | 30ms | 100ms |

---

## Implementation Phases

Each phase is defined in a separate file. Tasks follow red-green-refactor: **Prime** (understand context), **Test** (red), **Implement** (green), **Validate** (refactor + verify).

> **Tracking Principle**: Track logical units that produce verifiable outcomes. The TDD cycle is the method, not separate tracked items.

- [x] [Phase 1: Plugin Foundation + Shared Libraries](phase-1.md)
- [x] [Phase 2: Claude-side PreToolUse Hooks](phase-2.md)
- [x] [Phase 3: Awareness Hooks + Status Backend](phase-3.md)
- [x] [Phase 4: Repo-side `.githooks/` Templates](phase-4.md)
- [x] [Phase 5: Skills + References + Optional Components](phase-5.md)
- [ ] [Phase 6: Integration, Rollout & E2E Validation](phase-6.md)

---

## Plan Verification

| Criterion | Status |
|-----------|--------|
| A developer can follow this plan without additional clarification | ✅ |
| Every task produces a verifiable deliverable | ✅ |
| All PRD acceptance criteria map to specific tasks | ✅ (M1-M12 → phases 2-5; S1-S2 → phase 5) |
| All SDD components have implementation tasks | ✅ |
| Dependencies are explicit with no circular references | ✅ (Phase 1 → 2 → 3 → 4 → 5 → 6; lib modules within Phase 1 are mostly parallel) |
| Parallel opportunities are marked with `[parallel: true]` | ✅ (26 tasks) |
| Each task has specification references `[ref: ...]` | ✅ |
| Project commands in Context Priming are accurate | ✅ |
| All phase files exist and are linked from this manifest | ✅ |
