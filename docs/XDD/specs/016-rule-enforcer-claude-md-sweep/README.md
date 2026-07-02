# Specification: 016-rule-enforcer-claude-md-sweep

## Status

| Field | Value |
|-------|-------|
| **Created** | 2026-07-02 |
| **Current Phase** | Ready |
| **Last Updated** | 2026-07-02 |

## Documents

| Document | Status | Notes |
|----------|--------|-------|
| requirements.md | completed | 18 acceptance criteria; 3 open questions with working defaults |
| solution.md | completed | 6 ADRs confirmed; 3 new reference files + dual-mode dispatch |
| plan/ | completed | 3 phases, 16 tasks; alignment-validated (20/21 PASS, 1 WARN fixed) |

**Status values**: `pending` | `in_progress` | `completed` | `skipped`

## Decisions Log

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-07-02 | Batch/extraction mode lives in `rule-enforcer` (not `memory-claude-md-optimize`, not a new skill) | The `mechanism-matrix` is the routing brain and already lives here; keeps it Single Source of Truth (DRY). `memory-claude-md-optimize` will hand off to this mode instead of duplicating hook-routing logic. |
| 2026-07-02 | Scan scope = CLAUDE.md **+** memory files (`docs/ai/memory/*`, `~/.claude/`) | Larger enforcement payoff than CLAUDE.md-only; accepts higher false-positive risk mitigated by non-destructive preview + single confirm. |
| 2026-07-02 | Q1 (recurrence) skipped in batch mode; Q2/Q3/Q4 **inferred** non-interactively | Source is a file of already-codified rules — asking 4 questions × N lines is unusable UX. Matches the aihero.dev prompt's scan→confirm→implement shape. |
| 2026-07-02 | PRD approved; 3 open questions resolved with working defaults | Global `~/.claude` scan OFF by default (opt-in via `--scope global`); SM-5 recall bar = 80%; overlapping global-vs-repo rules prefer broader scope but surface at confirm. Deferrable to SDD if design pressure emerges. |
| 2026-07-02 | SDD ADR-1..ADR-6 confirmed | Dual-mode dispatch via flag; Q1-skip/Q2-filter; reuse Step 8 verbatim (Candidate≅TriageState); bare-label Q3 + self-test; dedup live-inspection authoritative; optimizer→batch one-directional pointer. |
| 2026-07-02 | PLAN alignment-validated (20/21 PASS) | All SKILL.md/matrix/optimizer/git-helpers line & structural citations accurate. Fixed 1 WARN: skill-author-on-creation is a memory rule, not a hook → dedup target corrected to ≥2 hook hits; optimizer step names ("Categorize"/"Propose") corrected in T3.1. |

## Context

Extends the existing `tcs-helper:rule-enforcer` skill with a second entry mode: a
batch sweep over `CLAUDE.md` and memory files that extracts deterministically
enforceable instructions, classifies each against the existing
`reference/mechanism-matrix.md` (inferring Q2/Q3/Q4 rather than asking, skipping
Q1), presents one consolidated proposal table, takes a single confirm, then hands
off to the existing author skills (`plugin-dev:hook-development`, `skill-author`,
CI/pre-push template renderers).

Inspired by the aihero.dev prompt "Take the instructions in your CLAUDE.md and
turn them into deterministic Claude Code hooks." Neighbor skill
`memory-claude-md-optimize` (which already sweeps CLAUDE.md to relocate content)
gains a hand-off pointer to this mode so it never learns hook logic.

Design constraint: the mechanism-matrix stays the Single Source of Truth — the
batch mode reuses it, it does not duplicate the (Q3,Q4)→mechanism mapping.

---
*This file is managed by the xdd-meta skill.*
