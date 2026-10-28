# Specification: 022-model-tier-classification

## Status

| Field | Value |
|-------|-------|
| **Created** | 2026-10-28 |
| **Current Phase** | Ready |
| **Decomposition tier** | Incremental |
| **Last Updated** | 2026-10-28 |

## Documents

| Document | Status | Notes |
|----------|--------|-------|
| requirements.md | completed | 6 Must-Have features, 27 acceptance criteria (AC-1.1 … AC-6.4) |
| solution.md | completed | 7 ADRs confirmed (ADR-3, ADR-5 amended after validation); 27 EARS criteria traced 1:1 |
| plan/ | completed | 4 phases, 15 tasks |

**Status values**: `pending` | `in_progress` | `completed` | `skipped`

**Decomposition tier**: `Direct` (no plan) | `Incremental` (phase plan). Set by the classifier at the decomposition step and confirmed by the user; leave the placeholder until then. Read back by `spec.py --read`, which treats anything it does not recognise as absent.

## Decisions Log

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-10-28 | Spec created from issue #158 | Model tier classification alongside the decomposition tier, with a frontier rung and a safe fallback when Fable is unavailable |
| 2026-10-28 | #158 open questions answered | Three tiers (routine, hard, frontier); spec-level row plus per-task `[model:]` override; cost sentence in the classifier's confirmation question; auto-escalate up to opus at max effort, always ask before fable |
| 2026-10-28 | PRD approved; phase → SDD | Rule 3 accepted: confirming `frontier` at classification is the consent for that spec's planned fable dispatches; escalations to fable ask at the time |
| 2026-10-28 | SDD approved: ADR-1 to ADR-7 confirmed | Model tier as second classifier axis in one step-6 call; depth signals high_risks/novel_pattern/adr_count; one ladder in implement/reference/model-ladder.md; escalation on evidence; spike first on observing the model that ran |
| 2026-10-28 | Decomposition tier: Incremental | Classifier recommended Incremental (6 Must-Have features, 25 acceptance criteria, 1 new component; rule 1 via feature_count >= 2). Accepted. |
| 2026-10-28 | Spec validation: 6 FAIL, 21 WARN; fixes applied | Ladder moved to `xdd/reference/model-ladder.md` (dispatcher at its line budget, owns no references); step-6 model question in prose (CON-8 test counts the tool name, already used by the Finalize gate); fable failure: planned task → opus@max, escalated task → BLOCKED, fable off for the run; consecutive review-failure count resets on escalation and caps at the highest reachable rung (bounds the 4f/4g loop); absent tier keeps today's selection, escalation follows the ladder; override reason from free text; AC numbering, test files per task, bats path dropped |

## Context

Source: GitHub issue #158 (context, proposal sketch, three Fable-unavailability cases, four open questions).

---
*This file is managed by the xdd-meta skill.*
