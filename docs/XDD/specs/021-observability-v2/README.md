# Specification: 021-observability-v2

## Status

| Field | Value |
|-------|-------|
| **Created** | 2026-10-11 |
| **Current Phase** | PLAN |
| **Decomposition tier** | Incremental |
| **Last Updated** | 2026-10-11 |

## Documents

| Document | Status | Notes |
|----------|--------|-------|
| requirements.md | completed | 8 features (6 Must, 1 Should, 1 Could), 35 acceptance criteria |
| solution.md | completed | 9 ADRs confirmed; reviewed against code |
| plan/ | in_progress | 5 phases, 13 tasks; awaiting validation |

**Status values**: `pending` | `in_progress` | `completed` | `skipped`

**Decomposition tier**: `Direct` (no plan) | `Incremental` (phase plan). Set by the classifier at the decomposition step and confirmed by the user; leave the placeholder until then. Read back by `spec.py --read`, which treats anything it does not recognise as absent.

## Decisions Log

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-10-11 | One spec for #165, #166 and #172 | All three are adapters in the same tcs-helper observability bundle; one registration change, one bundle bump, one report change. Chosen by Marcus over a lean plan or #165-only. |
| 2026-10-11 | #166 stays in scope | Verified interactively: a named dispatch recorded `agent_type: probe-166` (the spawn name). Headless `-p` records the type, so the defect is interactive/teammate-only. |
| 2026-10-11 | Start with PRD; Standard research mode | Four parallel research passes (requirements, technical, security, performance); findings in `research.md`. |
| 2026-10-11 | Git record = program, git subcommand, flag names, override token names and position, agent attribution — never values or the full line, not even in detail mode | No credential scrubbing needed; keeps the 018 promise that consumers' command lines are never recorded. |
| 2026-10-11 | Git scope = every `git` call except a read-only allowlist | Fail-closed: a rare or new mutating verb is recorded without anyone adding it. |
| 2026-10-11 | Typed skill = `kind: skill` with a `route` field (`typed` / `tool`); arguments only as presence, never text | Report counts both routes without new mapping logic. |
| 2026-10-11 | In scope as side findings: records file 0600 / dirs 0700; `args` on the reduced-mode deny list; fast path for the tcs-git-helpers Bash guard | Recording commands raises the sensitivity of the file; `args` was an open 018 recommendation; the guard costs ~60 ms on every non-git Bash call and the new hook adds to it. `sync-docker` check not taken. |
| 2026-10-11 | Supersedes the 018/019 *Won't Have* "no Bash recording" | #172: a destructive git op is otherwise unattributable; bounded by the field rules above. |
| 2026-10-11 | PRD approved; continue to SDD | Brainstorm step skipped: problem, scope and contested choices were settled by the issues, research and the decisions above. |
| 2026-10-11 | SDD: 9 ADRs confirmed; ADR-6 revised to `$(cat)` and extended to the guard's shebang | Independent review against the code found 3 factual, 3 gap, 5 breakage and 5 consistency defects; all fixed. Measured: `read -d ''` is 62 ms at 200 KB vs 6 ms for `cat`. PRD F5 AC2 and F6 AC2 amended to match ADR-1 and ADR-4. |
| 2026-10-11 | Decomposition tier: Incremental | Classifier recommended Incremental (rule 1: 3 new components — log_tool.sh, git_ops.sh, log_expansion.sh; 6 Must features, 35 ACs; no parallel markers). Accepted. |

## Context

Closes three blind spots in the tcs-helper observability bundle (spec-018/019 lineage), each one a mechanism whose use leaves no record:

- **#165** — a typed `/plugin:skill` makes no `Skill` tool call, so `PreToolUse:Skill` never sees it.
- **#166** — an interactively named subagent records its spawn name in `SubagentStart.agent_type`, not its type.
- **#172** — no command is recorded at all, so a destructive git op cannot be attributed to the session or agent that ran it.

Payloads measured on Claude Code 2.1.296 (2026-10-11, probe via `claude -p --settings` plus one interactive named dispatch):

- Typed skill → `UserPromptExpansion` with `expansion_type: slash_command`, `command_name`, `command_args`, `command_source`, `prompt`; then `UserPromptSubmit`. No `PreToolUse:Skill`.
- `PreToolUse` matcher `Agent` → `tool_input` carries `subagent_type`, `name`, `description`, `prompt`, `run_in_background`; payload carries `tool_use_id`. The hooks docs omit `name`.
- `PreToolUse` inside a subagent → payload carries `agent_id` and `agent_type`.
- `SubagentStart` → `agent_id`, `agent_type` only; no parent field.

---
*This file is managed by the xdd-meta skill.*
