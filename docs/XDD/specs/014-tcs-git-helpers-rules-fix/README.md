# Specification: 014-tcs-git-helpers-rules-fix

## Status

| Field | Value |
|-------|-------|
| **Created** | 2026-05-22 |
| **Current Phase** | Implemented |
| **Last Updated** | 2026-05-23 |

## Documents

| Document | Status | Notes |
|----------|--------|-------|
| requirements.md | completed | M1 + M2 (Must), S1 (Should); 8 ACs |
| solution.md | completed | 9 ADRs confirmed; CON-1..7 + 13 sections |
| plan/ | completed | 3 phases, 11 tasks (4 parallel); validate PASS |

**Status values**: `pending` | `in_progress` | `completed` | `skipped`

## Decisions Log

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-05-22 | Scaffold spec 014 | Two real rule defects surfaced during spec/013 implementation — branch-level workflow needs both squash-merge-trap nuance + inline-env-var override support for Claude PreToolUse hooks |
| 2026-05-22 | Pre-decided fix for Problem 1: ahead-of-merged check | Block only when `HEAD == merged commit SHA`; allow when `HEAD` is ahead (implies new PR will be opened). Preserves squash-merge-trap protection without false positives on legitimate follow-up work. |
| 2026-05-22 | Pre-decided fix for Problem 2: tool-input scanning | Extend `_check_and_consume_override` in `scripts/lib/override.sh` to also scan the Bash tool command string for `CLAUDE_ALLOW_X=1` prefix patterns. Makes the documented override mechanism actually functional for Claude. |
| 2026-05-22 | Mode: Standard parallel | Two well-scoped fixes in a single existing plugin; persistent Agent Team coordination unnecessary. |
| 2026-05-22 | ADR-7/8/9 confirmed | All three proposed ADRs auto-confirmed to their recommended defaults during /xdd 014 review (reuse CMD global; stderr informational note; keep existing deny-message wording). |
| 2026-05-22 | Phase transition: SDD → PLAN | SDD self-validation passed; 9 ADRs confirmed; ready for plan/ generation. |
| 2026-05-22 | PLAN authored: 3 phases (M1, M2, Integration+S1+Release) | Phases 1+2 parallelizable (disjoint files); Phase 3 integrates. 11 tasks total, 4 tagged `[parallel: true]`. All 9 PRD ACs + 7 SDD components + 9 ADRs traceable per coverage validation. |
| 2026-05-22 | Validation: PASS (structural/coverage); 1 path fix applied | Alignment agent caught `plugin.json` location: it lives at `.claude-plugin/plugin.json`, not plugin root. SDD Directory Map + Project Commands + phase-3 T3.3 + plan/README Context Priming updated. |
| 2026-05-22 | Phase transition: PLAN → Ready | All three documents complete and self-consistent; plan executable by `/implement`. |
| 2026-05-23 | /implement 014 kicked off — mode: Agent Team + Strict | Triggered after `/tcs-git-helpers:git-audit --cleanup` hit Defect 2 (inline-override unrecognized) on `refactor/skill-naming-domain-prefix`. Implementation branch: `spec/014-tcs-git-helpers-rules-fix-impl` off origin/main. Phase 1 + Phase 2 marked in_progress for parallel execution (disjoint files per plan dependency analysis); Phase 3 gated. |
| 2026-05-23 | Implementation complete | v2.2.0 release on branch spec/014-tcs-git-helpers-rules-fix-impl (19 commits, head b2d7db6). M1 squash-merge-trap nuance + M2 inline-override scan + S1 wording-lock shipped. Plugin.json 2.1.3 → 2.2.0. 156/156 M1+M2 BATS pass; 68/68 pytest; shellcheck clean; integration test (3 scenarios) green. |

## Context

**Problem 1 — Squash-Merge-Trap blocks legitimate follow-up work**

Location: `plugins/tcs-git-helpers/scripts/block-bad-git-ops.sh:218-267` (`_check_push_to_closed_pr`)

Current behavior: blocks any push when the current branch's GitHub PR state is `CLOSED` or `MERGED`. Does not distinguish between:
- Real squash-merge-trap (HEAD == merged commit, user is about to lose work) → should deny
- Legitimate follow-up work (HEAD ahead of merged commit, user is opening a new PR from the same branch name) → should allow

Surfaced during spec/013 implementation: PR #31 (spec docs) merged, then 28 implementation commits were added on the same branch. The hook denied all push attempts. Workaround was branching fresh (`spec/013-rule-enforcer-impl`).

**Problem 2 — Override mechanism doesn't work from Claude's Bash tool**

Location: `plugins/tcs-git-helpers/scripts/lib/override.sh:66-153` (`_check_and_consume_override`)

Current behavior: reads `CLAUDE_ALLOW_X=1` from the hook's shell environment via `${!env_var:-0}`. PreToolUse hooks fire BEFORE the Bash tool command executes, in Claude Code's process environment — so an inline `CLAUDE_ALLOW_X=1 git push …` never reaches the hook. The deny message advertises this override path but it's only functional when set in the user's shell before launching Claude.

Fix scope: extend `_check_and_consume_override` to also parse the Bash tool's `tool_input.command` field (passed via stdin or env by Claude Code's PreToolUse hook contract) for `CLAUDE_ALLOW_X=1` prefix patterns and accept that as valid override consumption.

**Related auto-memory**: `reference_branch-fresh-after-spec-pr.md` documents the workflow context that surfaced Problem 1; this spec converts that memory rule into a code-level fix so the workflow doesn't have to compensate.

**Stakeholders**: TCS plugin maintainer (Marcus). Consumers: any TCS user with `tcs-git-helpers` installed.

---
*This file is managed by the xdd-meta skill.*
