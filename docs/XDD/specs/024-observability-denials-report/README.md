# Specification: 024-observability-denials-report

## Status

| Field | Value |
|-------|-------|
| **Created** | 2026-11-26 |
| **Current Phase** | Ready |
| **Decomposition tier** | Incremental |
| **Model tier** | hard |
| **Last Updated** | 2026-11-26 |

## Documents

| Document | Status | Notes |
|----------|--------|-------|
| requirements.md | completed | Approved 2026-11-26 |
| solution.md | completed | Approved 2026-11-26 |
| plan/ | completed | Incremental tier; 3 phases, 11 tasks |

**Status values**: `pending` | `in_progress` | `completed` | `skipped`

**Decomposition tier**: `Direct` (no plan) | `Incremental` (phase plan). Set by the classifier at the decomposition step and confirmed by the user; leave the placeholder until then. Read back by `spec.py --read`, which treats anything it does not recognise as absent.

**Model tier**: `routine` | `hard` | `frontier`. The classifier recommends it at the decomposition step and the user confirms it; leave the placeholder until then. `spec.py --read` treats anything it does not recognise as absent.

## Decisions Log

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-11-26 | Spec before implementation for #300 | Investigation showed TCS hook denies are recorded nowhere and the only broad source is the session transcript (internal format, retroactive, every session): data source and privacy need a decision first. User chose spec over direct implementation. |
| 2026-11-26 | Data source: session transcripts, read narrowly | Only source that sees TCS hook denies, prompt rejections and classifier blocks. Extract category, hook, rule, tool, timestamp, version only; never prompt, input or path text. Narrows spec 021's Won't Have "transcript join" for this purpose; unknown shapes count as unclassified. Rejected: PermissionDenied adapter in addition (classifier already recognisable in transcripts), hooks-only (from-now-on only, misses prompt rejections). |
| 2026-11-26 | Opt-in: per source in .claude/observability-sources.toml | `denials = true` per source (untracked config); without it the section reports "not enabled". Keeps transcript reading a deliberate per-repo choice, like recording. Rejected: a --denials flag (not durable, easy to apply to every source). |
| 2026-11-26 | Default period 28 days with weekly trend, adjustable | Covers the guide's two-week baseline with headroom; full history costs about a minute and mixes old wordings. |
| 2026-11-26 | Override usage per rule, count only | A rule overridden often is a rule-fix candidate; the `command` field of overrides.jsonl is never rendered (CON-13). |
| 2026-11-26 | Subagent transcripts counted, shown separately | Most "permission to use … denied" and worktree blocks come from subagents and mean something different from main-session friction. |
| 2026-11-26 | SDD ADRs 1-8 confirmed | ADR-1 new module denials.py; ADR-2 invalid `denials` value is a config schema error like every other key (PRD F1 AC3 amended); ADR-3 read project dirs whose name starts with the encoded repo root, then filter lines by cwd; ADR-4 ordered classification table; ADR-5 dedupe per transcript file and tool_use_id; ADR-6 override counts from tcs-git-helpers overrides.jsonl, env_var and ts only; ADR-7 --denials-weeks / --denials-since, Monday weeks; ADR-8 hook owner table. |
| 2026-11-26 | Decomposition tier: Incremental | Classifier recommended Incremental (7 Must features, 31 acceptance criteria, 1 new component denials.py; sources.py and report.py modified). Accepted. |
| 2026-11-26 | Model tier: hard | Classifier recommended hard (change_type=feature, 2 high-impact risks, no new pattern, 8 ADRs). Accepted. |
| 2026-11-26 | Plan complete; spec Ready | 3 phases (read and classify; aggregate and render; integrate, docs, real-data validation), 11 tasks; F9 deferred. |
| 2026-11-26 | Phase 1 drift: `sandbox: network` confidence is low | PRD Rule 6 and F2 AC govern over the SDD table's medium; SDD, code and test aligned. |
| 2026-11-26 | Phase 1 drift: `oldest_ts` source | `ScanResult.oldest_ts` is the earliest valid top-level timestamp on any line of the file, regardless of period; `DenialsSummary.oldest_ts` is their minimum. |
| 2026-11-26 | Phase 1 drift: SDD data models | Added `LocateResult` and `ScanResult`; `Period` (both ends inclusive, aware UTC) moved to Phase 1, T2.2 adds only `period_from_args`. |

## Context

Issue #300 (epic #302): add a denials view to the observability report — TCS hook denies by hook and rule with override usage, harness permission denials, auto-mode classifier blocks and sandbox violations where observable, weekly trend, top repeated denials; explicit empty state; a doc listing what is not observable.

Findings before this spec (to verify in research):

- The recorder (`plugins/tcs-helper/scripts/observability/log_tool.sh`) is PreToolUse-only. PreToolUse hooks run in parallel, so it cannot see another hook's decision. TCS hook denies are stored nowhere; tcs-git-helpers' `overrides.jsonl` holds override consumption, `protect-git-internals` denies and (since #299) ask-guard asks.
- Claude Code hooks: `PermissionDenied` fires only for auto-mode classifier denials (`tool_name`, `tool_input`, `tool_use_id`, `reason`). `PostToolUseFailure` does not fire for permission denials. No event for settings deny rules or rejected prompts. Sandbox violations have no event; they show only in command output.
- Session transcripts (`~/.claude/projects/<enc>/<session>.jsonl`, format documented as internal) carry `tool_result` entries with `is_error: true` and text such as `PreToolUse:<Tool> hook error: <reason>` (TCS denies list `[RULE]` lines), `The user doesn't want to proceed with this tool use…`, `Permission for this action was denied by the Claude Code auto mode classifier…`.
- Report: `scripts/observability/report.py` (multi-source via `sources.py` and `.claude/observability-sources.toml` with `homes`), tests `tests/test_observability_report.py`; prior specs 018, 019, 021.

---
*This file is managed by the xdd-meta skill.*
