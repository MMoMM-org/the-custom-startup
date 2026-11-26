# Specification: 024-observability-denials-report

## Status

| Field | Value |
|-------|-------|
| **Created** | 2026-11-26 |
| **Current Phase** | SDD |
| **Decomposition tier** | {{DECOMPOSITION_TIER}} |
| **Model tier** | {{MODEL_TIER}} |
| **Last Updated** | 2026-11-26 |

## Documents

| Document | Status | Notes |
|----------|--------|-------|
| requirements.md | completed | Approved 2026-11-26 |
| solution.md | in_progress | |
| plan/ | pending | |

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

## Context

Issue #300 (epic #302): add a denials view to the observability report — TCS hook denies by hook and rule with override usage, harness permission denials, auto-mode classifier blocks and sandbox violations where observable, weekly trend, top repeated denials; explicit empty state; a doc listing what is not observable.

Findings before this spec (to verify in research):

- The recorder (`plugins/tcs-helper/scripts/observability/log_tool.sh`) is PreToolUse-only. PreToolUse hooks run in parallel, so it cannot see another hook's decision. TCS hook denies are stored nowhere; tcs-git-helpers' `overrides.jsonl` holds override consumption, `protect-git-internals` denies and (since #299) ask-guard asks.
- Claude Code hooks: `PermissionDenied` fires only for auto-mode classifier denials (`tool_name`, `tool_input`, `tool_use_id`, `reason`). `PostToolUseFailure` does not fire for permission denials. No event for settings deny rules or rejected prompts. Sandbox violations have no event; they show only in command output.
- Session transcripts (`~/.claude/projects/<enc>/<session>.jsonl`, format documented as internal) carry `tool_result` entries with `is_error: true` and text such as `PreToolUse:<Tool> hook error: <reason>` (TCS denies list `[RULE]` lines), `The user doesn't want to proceed with this tool use…`, `Permission for this action was denied by the Claude Code auto mode classifier…`.
- Report: `scripts/observability/report.py` (multi-source via `sources.py` and `.claude/observability-sources.toml` with `homes`), tests `tests/test_observability_report.py`; prior specs 018, 019, 021.

---
*This file is managed by the xdd-meta skill.*
