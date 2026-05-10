# Specification: 011-tcs-git-helpers

## Status

| Field | Value |
|-------|-------|
| **Created** | 2026-05-08 |
| **Current Phase** | Spec COMPLETE (PRD + SDD + PLAN, validated, all findings addressed); READY for implementation |
| **Last Updated** | 2026-05-09 |

## Documents

| Document | Status | Notes |
|----------|--------|-------|
| requirements.md | completed | 13 features (12 Must + 2 Should) with 38+ Gherkin acceptance criteria; 5 open questions for stakeholder review |
| solution.md | completed | 11 sections + 12 confirmed ADRs; validates clean (15/15 gates pass); EARS acceptance criteria mapped to PRD M1-M12 + S1/S2; bash 3.2 regex constraints verified; cross-references aligned with descriptive section headers |
| plan/ | completed | 6 phase files (plan/README.md + phase-1.md through phase-6.md); 43 tasks; 26 parallel; all PRD AC + SDD components mapped to tasks |

**Status values**: `pending` | `in_progress` | `completed` | `skipped`

## Decisions Log

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-05-08 | Created from brainstorm spec `docs/XDD/ideas/2026-05-08-tcs-git-safety.md` | Brainstorm phase complete with full design, gap-reviewed, ready for PRD |
| 2026-05-08 | Plugin name: `tcs-git-helpers` | Scope broader than just safety: hooks + nudges + best-practices references + GHA branch protection |
| 2026-05-08 | Research mode: Agent Team (5 researchers) | Persistent teammates across PRD/SDD/PLAN; complex domain with cross-perspective conflicts expected |
| 2026-05-08 | Research synthesis complete | 5 lenses (requirements/technical/security/performance/integration) → `research/_synthesis.md`. 3 conflicts resolved (C1: ExitWorktree event; C2: mergeMethod bug; C3: master override semantics). 10+ decisions locked, 15 questions deferred to PRD review or SDD. |
| 2026-05-08 | PRD draft complete (`requirements.md`) | 13 features (M1-M12 must, S1-S2 should), 38+ Gherkin AC, 12 risks, 5 open questions surfaced for Marcus review. Validates clean: zero clarification markers, all template sections complete. |
| 2026-05-09 | OQ1-OQ5 resolved by Marcus | OQ1 bash-only timeout (no coreutils). OQ2 single-coder branch-protection preset (no review requirement). OQ3 references plugin-internal only. OQ4 brief on SessionStart + post-merge. OQ5 P3 soft gate v1.0. PRD updated inline. Ready for SDD. |
| 2026-05-09 | SDD draft complete (`solution.md`) | 12 ADRs total (8 confirmed via PRD/brainstorm/research, 4 pending: ADR-5 single-shot mechanism, ADR-6 push-state cache TTL, ADR-7 audit log rotation, ADR-11 setup-active sentinel env-var). Architecture: plugin-distributed event-driven hooks + repo-side defense in depth. Schemas locked: .config strict-KV parser, audit JSONL, TSV+JSON cache. Performance budgets per hook. EARS acceptance criteria mapped to PRD M1-M12. |
| 2026-05-09 | ADR-5/6/7/11 confirmed by Marcus | All 4 pending ADRs accepted recommended options: env-var+5s sentinel single-shot; 60s shared push-state cache; 1MB→.1/.2 audit rotation; TCS_GIT_HELPERS_SETUP_ACTIVE in subshell. SDD COMPLETE. |
| 2026-05-09 | PLAN complete (6 phases, 43 tasks) | Phase 1 Foundation+Libs (10 tasks, 8 parallel); Phase 2 PreToolUse Hooks (6/3); Phase 3 Awareness+Status backend (5/2); Phase 4 .githooks Templates (6/5); Phase 5 Skills+References+Optional (9/6); Phase 6 Integration+Rollout+E2E (7/2). All tasks linked to PRD AC and SDD components via [ref:] tags. |
| 2026-05-09 | Spec validation pass | Validator found 6 HIGH + 8 MEDIUM + 6 LOW findings. ALL 20 addressed: bash 3.2 regex bug fixed (`\s+`/`\b` → `[[:space:]]+`/`[[:>:]]` empirically verified), TCS_/CLAUDE_ env-var prefix consistency, numerical SDD refs replaced with descriptive headers, PRD §Cross-Repo Rollout section added, EC1-EC8 enumerated, S1/S2 EARS added, M3 override criterion added, "PENDING" residue removed from ADRs, parallel count corrected, M11 "equivalently" tightened. Spec READY for implementation. |

## Context

Brainstorm artifact: `docs/XDD/ideas/2026-05-08-tcs-git-safety.md` (note legacy filename — plugin renamed during brainstorm; ideas-file kept under original name)

Branch: `feat/tcs-git-safety` (legacy; rename to `feat/tcs-git-helpers` deferred to implementation phase)

Brainstorm output included:
- 12 goals, 8 observed failure modes, parking lot
- Architecture: plugin-internal Claude hooks + repo-side `.githooks/` defense in depth
- Gap-reviewed (6 blockers + 5 advisories all addressed inline)
- Spec-reviewer: Approved (2 implementation gotchas fixed inline: bash regex lookahead, gh `--max-time` flag)
- External prior art absorbed: Boucle-framework `git-safe`, `branch-guard`, `worktree-guard`

---
*This file is managed by the xdd-meta skill.*
