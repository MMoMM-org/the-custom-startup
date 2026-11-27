# Specification: 025-security-baseline

## Status

| Field | Value |
|-------|-------|
| **Created** | 2026-11-27 |
| **Current Phase** | Initialization |
| **Decomposition tier** | {{DECOMPOSITION_TIER}} |
| **Model tier** | {{MODEL_TIER}} |
| **Last Updated** | 2026-11-27 |

## Documents

| Document | Status | Notes |
|----------|--------|-------|
| requirements.md | pending | |
| solution.md | pending | |
| plan/ | pending | |

**Status values**: `pending` | `in_progress` | `completed` | `skipped`

**Decomposition tier**: `Direct` (no plan) | `Incremental` (phase plan). Set by the classifier at the decomposition step and confirmed by the user; leave the placeholder until then. Read back by `spec.py --read`, which treats anything it does not recognise as absent.

**Model tier**: `routine` | `hard` | `frontier`. The classifier recommends it at the decomposition step and the user confirms it; leave the placeholder until then. `spec.py --read` treats anything it does not recognise as absent.

## Decisions Log

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-11-27 | Spec created from issue #298 | Issue marks the skill as feature-sized, requiring /xdd before implementation |
| 2026-11-27 | Start with PRD; Standard research mode | Default path; three parallel research agents (settings docs, repo patterns, machine inventory) |
| 2026-11-27 | Scope: solo first — audit reads all scopes incl. managed; setup writes user/project/local only | ~8 keys are managed-only; managed-settings templates deferred (record in declined.md with reopen condition) |
| 2026-11-27 | Profile-aware baseline (host vs container) | Container entrypoint uses --dangerously-skip-permissions under YOLO=true; bypass mode there is a reported, accepted exception and setup never writes disableBypassPermissionsMode in that profile |
| 2026-11-27 | Sandbox: check dependencies before offering to enable | Linux needs bubblewrap + socat (absent in the container); setup enables sandbox / failIfUnavailable only when deps are present; never enableWeakerNestedSandbox |
| 2026-11-27 | Setup may write user, project and local settings, each behind a shown diff and explicit yes | Broad/stale allows live mostly in settings.local.json; deny rules belong user-wide |

## Context

Issue #298: a `tcs-helper` skill that audits and sets up a Claude Code security baseline
(sandbox, credential-path `permissions.deny`, `disableBypassPermissionsMode`, broad allows,
MCP allowlist, WebFetch domain coverage). Two modes: **audit** (gap report) and **setup**
(reviewed baseline, never silent). Source: an enterprise guide to securing coding agents,
ch. 4 (permissions, sandboxing) and ch. 5 (policy table, baseline vs locked).

Open questions: solo dev machines only vs managed-settings templates for teams; interaction
with the per-repo container home setup; macOS vs Linux sandbox availability.

---
*This file is managed by the xdd-meta skill.*
