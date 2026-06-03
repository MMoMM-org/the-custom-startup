# Specification: 015-tcs-git-helpers-no-verify-sibling-flag-false-positive

## Status

| Field | Value |
|-------|-------|
| **Created** | 2026-06-01 |
| **Current Phase** | Implemented |
| **Last Updated** | 2026-06-03 |

## Documents

| Document | Status | Notes |
|----------|--------|-------|
| requirements.md | completed | 3 features (Must), 9 ACs; Won't-have scoped to common separators |
| solution.md | completed | 3 ADRs confirmed; per-clause matching, PATTERN_NO_VERIFY unchanged |
| plan/ | completed | 2 phases, 5 tasks (T1.2 parallel); validate PASS (no drift) |

**Status values**: `pending` | `in_progress` | `completed` | `skipped`

## Decisions Log

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-06-01 | Spec scaffolded | NO_VERIFY rule false-positive confirmed empirically against v2.2.3 `lib/pattern_match.sh`; not a missing-update issue |
| 2026-06-01 | Fix via Branch + Spec | User chose full XDD route over minimal-fix or update-only options |
| 2026-06-01 | PRD approved | Won't-have kept scoped to common shell separators; no full shell-grammar parser |
| 2026-06-01 | SDD ADRs confirmed | ADR-1 per-clause matching; ADR-2 PATTERN_NO_VERIFY unchanged; ADR-3 separator set &&/\|\|/\|/;/&/newline, pure-bash split |
| 2026-06-01 | PLAN completed + validated | 2 phases, 5 tasks; drift-check PASS against live pattern_match.sh:85 / block-bad-git-ops.sh:458 |
| 2026-06-03 | Implementation complete | `_match_no_verify` per-clause helper (commits a5bcfac, aaa4f70); spec-compliance + code-quality PASS; bats lib 55/55 + dispatcher 103/103, e2e dogfood 10/10; 0 regressions (24 failures pre-existing, verified vs base 00931a0); CHANGELOG 2.2.4; plugin.json auto-bump on merge |

## Context

**Confirmed bug** (verified against `plugins/tcs-git-helpers/scripts/lib/pattern_match.sh` v2.2.3):

```
PATTERN_NO_VERIFY='git[[:space:]]+commit.*(--no-verify|-n[[:>:]])'
```

The unbounded `.*` bridges from `git commit` to any later `-n` token belonging to a
**sibling subcommand** in the same command string (e.g. `git commit -m "done" && echo -n ok`,
`git commit ...; head -n 5`). Bash does not set `REG_NEWLINE`, so `.` also matches `\n` —
newline-separated compound commands match too. The v2.2.0 `_strip_quoted` helper only
neutralizes `-n` **inside** a quoted `-m "..."` message; it does not stop `.*` bridging to
an unquoted sibling-command flag.

**Goal**: NO_VERIFY must match `-n` / `--no-verify` only when the flag genuinely belongs to
the `git commit` invocation, not to a chained sibling command (separators `;`, `&&`, `||`,
`|`, newline).

**Must preserve**: genuine `git commit --no-verify` and `git commit -n` still DENY;
`-n` inside the message body still allowed.

**Source to fix**: `plugins/tcs-git-helpers/scripts/lib/pattern_match.sh` (+ bats tests under
`plugins/tcs-git-helpers/tests/`). Related precedent: spec `014-tcs-git-helpers-rules-fix`.

---
*This file is managed by the xdd-meta skill.*
