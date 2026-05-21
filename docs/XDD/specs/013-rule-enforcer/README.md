# Specification: 013-rule-enforcer

## Status

| Field | Value |
|-------|-------|
| **Created** | 2026-05-21 |
| **Current Phase** | PRD |
| **Last Updated** | 2026-05-21 |

## Documents

| Document | Status | Notes |
|----------|--------|-------|
| requirements.md | pending | PRD phase entered; brainstorm artifact ready as input |
| solution.md | pending | — |
| plan/ | pending | — |

**Status values**: `pending` | `in_progress` | `completed` | `skipped`

## Decisions Log

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-05-21 | Spec scaffolded as 013-rule-enforcer | Brainstorm complete in `docs/XDD/ideas/2026-05-21-rule-enforcer.md`; user chose "Full enforcer with intercept" + "Spec-first via XDD" path |
| 2026-05-21 | Trigger context | Repeated-violation pattern: `feedback_no-manual-marketplace-sync.md` was violated within 10 days of being written, leading to PR #28 catch-up. The memory rule didn't prevent the bug; mechanization (PR #29 auto-bumper) did. This spec generalizes the "mechanize-vs-memorize" decision. |

## Context

**Brainstorm artifact:** `docs/XDD/ideas/2026-05-21-rule-enforcer.md` (comprehensive — problem, design sketch, mechanism matrix, intercept hook design, 9 open questions for PRD, related skills, scope estimate)

**Scope per user pick:** Full enforcer with intercept (skill + UserPromptSubmit hook for trigger phrases). Spec-first XDD flow.

**Related skills:** `tcs-helper:skill-author`, `tcs-helper:agent-author`, `tcs-helper:memory-add`, `plugin-dev:hook-development`, `tcs-git-helpers`.

**Home:** `plugins/tcs-helper/skills/rule-enforcer/` (Meta-Tools cluster alongside skill-author, agent-author, memory-add).

---
*This file is managed by the xdd-meta skill.*
