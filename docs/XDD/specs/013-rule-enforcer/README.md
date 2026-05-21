# Specification: 013-rule-enforcer

## Status

| Field | Value |
|-------|-------|
| **Created** | 2026-05-21 |
| **Current Phase** | Ready (implement-ready) |
| **Last Updated** | 2026-05-21 |

## Documents

| Document | Status | Notes |
|----------|--------|-------|
| requirements.md | completed | 7 Must Have + 2 Should Have + 2 Could Have features with Gherkin ACs; 4 blocking open questions resolved (Q1/Q8/Q9/Q12), 4 defaulted in PRD, 3 deferred to SDD |
| solution.md | completed | 8 ADRs confirmed by Marcus 2026-05-21: ADR-1 matrix in reference/, ADR-2 standalone pre-push, ADR-3 no persistence v1, ADR-4 python3 hook, ADR-5 markdown trigger-phrases, ADR-6 no analytics v1, ADR-7 M6 preview+confirm+Write, ADR-8 append to existing hooks.json |
| plan/ | completed | 3 phases, 13 tasks total (Phase 1: 3 tasks + validation; Phase 2: 5 tasks + validation; Phase 3: 5 tasks + validation). All PRD ACs mapped to tasks. Parallel opportunities marked. Ready for /implement. |

**Status values**: `pending` | `in_progress` | `completed` | `skipped`

## Decisions Log

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-05-21 | Spec scaffolded as 013-rule-enforcer | Brainstorm complete in `docs/XDD/ideas/2026-05-21-rule-enforcer.md`; user chose "Full enforcer with intercept" + "Spec-first via XDD" path |
| 2026-05-21 | Trigger context | Repeated-violation pattern: `feedback_no-manual-marketplace-sync.md` was violated within 10 days of being written, leading to PR #28 catch-up. The memory rule didn't prevent the bug; mechanization (PR #29 auto-bumper) did. This spec generalizes the "mechanize-vs-memorize" decision. |
| 2026-05-21 | PRD complete | 4 blocking open questions resolved by Marcus: Q1 `/enforce-rule` slash command; Q8 hook opt-out (on by default); Q9 hybrid scope (inline scaffolding for 2 templates + hand-off for the rest); Q12 1-trigger-phrase threshold for v1. 4 questions defaulted in PRD. 3 questions deferred to SDD (Q5 matrix location, Q10 pre-push integration, Q11 override memory). |
| 2026-05-21 | Live test case folded into spec | During PRD phase, surfaced a 3rd violation pattern: docs (CHANGELOG / xdd.md / plugins/tcs-workflow/README.md) were not updated when Finalize step (PR #27) and auto-bumper (PR #29) shipped. Fixed in commit `5834976`. This becomes Feature M7's 2nd Acceptance Criterion. |
| 2026-05-21 | SDD complete, all 8 ADRs confirmed | Architecture pattern: router skill + content-injection hook. Direct precedent in `capture_learning.py` (same plugin, same UserPromptSubmit event). Inline scaffold templates for 2 established patterns (CI auto-bump, pre-push docs-gate); hand-off via Skill tool for everything else. Hook in python3, never blocks (graceful degradation per CON-4). |
| 2026-05-21 | PLAN complete | 3 phases, 13 tasks. Phase 1 (Intercept Hook Foundation): T1.1 trigger-phrases ref+lib, T1.2 hook script, T1.3 registration. Phase 2 (Triage Skill + Hand-offs): T2.1 skill scaffold, T2.2 matrix ref, T2.3 4-question workflow, T2.4 hand-offs, T2.5 examples. Phase 3 (Templates + Self-test + Docs): T3.1 CI template, T3.2 pre-push template, T3.3 self-test fixtures, T3.4 E2E, T3.5 docs. Spec is implement-ready. |

## Context

**Brainstorm artifact:** `docs/XDD/ideas/2026-05-21-rule-enforcer.md` (comprehensive — problem, design sketch, mechanism matrix, intercept hook design, 9 open questions for PRD, related skills, scope estimate)

**Scope per user pick:** Full enforcer with intercept (skill + UserPromptSubmit hook for trigger phrases). Spec-first XDD flow.

**Related skills:** `tcs-helper:skill-author`, `tcs-helper:agent-author`, `tcs-helper:memory-add`, `plugin-dev:hook-development`, `tcs-git-helpers`.

**Home:** `plugins/tcs-helper/skills/rule-enforcer/` (Meta-Tools cluster alongside skill-author, agent-author, memory-add).

---
*This file is managed by the xdd-meta skill.*
