# Specification: 021-observability-v2

## Status

| Field | Value |
|-------|-------|
| **Created** | 2026-10-11 |
| **Current Phase** | Ready |
| **Decomposition tier** | Incremental |
| **Last Updated** | 2026-10-12 |

## Documents

| Document | Status | Notes |
|----------|--------|-------|
| requirements.md | completed | 8 features (6 Must, 1 Should, 1 Could), 35 acceptance criteria |
| solution.md | completed | 9 ADRs confirmed; reviewed against code |
| plan/ | completed | 5 phases, 13 tasks; validated 2026-10-11 |

**Status values**: `pending` | `in_progress` | `completed` | `skipped`

**Decomposition tier**: `Direct` (no plan) | `Incremental` (phase plan). Set by the classifier at the decomposition step and confirmed by the user; leave the placeholder until then. Read back by `spec.py --read`, which treats anything it does not recognise as absent.

## Decisions Log

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-10-11 | One spec for #165, #166 and #172 | All three are adapters in the same tcs-helper observability bundle; one registration change, one bundle bump, one report change. Chosen by Marcus over a lean plan or #165-only. |
| 2026-10-11 | #166 stays in scope | Verified interactively: a named dispatch recorded `agent_type: probe-166` (the spawn name). Headless `-p` records the type, so the defect is interactive/teammate-only. |
| 2026-10-11 | Start with PRD; Standard research mode | Four parallel research passes (requirements, technical, security, performance); findings in `research.md`. |
| 2026-10-11 | Git record = git subcommand, flag names, override token names and position, agent attribution — never values or the full line, not even in detail mode | No credential scrubbing needed; keeps the 018 promise that consumers' command lines are never recorded. |
| 2026-10-11 | Git scope = every `git` call except a read-only allowlist | Fail-closed: a rare or new mutating verb is recorded without anyone adding it. |
| 2026-10-11 | Typed skill = `kind: skill` with a `route` field (`typed` / `tool`); arguments only as presence, never text | Report counts both routes without new mapping logic. |
| 2026-10-11 | In scope as side findings: records file 0600 / dirs 0700; `args` on the reduced-mode deny list; fast path for the tcs-git-helpers Bash guard | Recording commands raises the sensitivity of the file; `args` was an open 018 recommendation; the guard costs ~60 ms on every non-git Bash call and the new hook adds to it. `sync-docker` check not taken. |
| 2026-10-11 | Supersedes the 018/019 *Won't Have* "no Bash recording" | #172: a destructive git op is otherwise unattributable; bounded by the field rules above. |
| 2026-10-11 | PRD approved; continue to SDD | Brainstorm step skipped: problem, scope and contested choices were settled by the issues, research and the decisions above. |
| 2026-10-11 | SDD: 9 ADRs confirmed; ADR-6 revised to `$(cat)` and extended to the guard's shebang | Independent review against the code found 3 factual, 3 gap, 5 breakage and 5 consistency defects; all fixed. Measured: `read -d ''` is 62 ms at 200 KB vs 6 ms for `cat`. PRD F5 AC2 and F6 AC2 amended to match ADR-1 and ADR-4. |
| 2026-10-11 | Decomposition tier: Incremental | Classifier recommended Incremental (rule 1: 3 new components — log_tool.sh, git_ops.sh, log_expansion.sh; 6 Must features, 35 ACs; no parallel markers). Accepted. |
| 2026-10-11 | Git record gains `action`: a sub-verb from a closed list (stash pop/drop/push, worktree remove, …) | Spec validation: `stash pop` and `stash push` were indistinguishable, so the #156 case could not be told apart from harmless use. Closed list keeps CON-13. |
| 2026-10-11 | Executor fallback records subcommand, action and overrides only; `flags: (executor)` | Spec validation: removing quotes inside `bash -c` can turn a message word into a flag. |
| 2026-10-11 | Spec validation: 0 FAIL, 37 WARN across completeness, alignment and coverage; all addressed | Fast path tests the command value only; global options, wrappers, openers and newline separators specified; overrides count only with `=1`; one PR for the whole feature (the bundle-version gate is range-based); manual steps marked. |
| 2026-10-11 | `override_first` is per command: every record of a command carries the first-position override name | T1.3 found that an override before a read-only or non-git clause (`CLAUDE_ALLOW_RESET_HARD=1 true && git reset --hard`) passes the guard but left no trace in any record. Chosen by Marcus over first-record-only and per-clause. `overrides` stays per clause. |
| 2026-10-11 | Executor fallback: a separate-value global option makes the subcommand `?` | T1.3: quote removal split `-C 'my dir'` and put `dir` in subcommand position, a value leak (CON-13). |
| 2026-10-11 | Executor fallback: subcommand only from a closed list of git command names, else `?` | T1.3: a separator inside a nested quote (`bash -c "git commit -m 'wip; git tok'"`) made a fake clause and put `tok` in the record. Chosen by Marcus over parsing the payload recursively: provably closed, same principle as `action`; costs `?` for aliases behind `bash -c` and a possible false-positive `?` record. |
| 2026-10-12 | Subcommand only from the closed list of git command names in both modes, else `?` | T1.3's fourth review round still found value fragments in the subcommand slot (`git -C my\ dir push` recorded `dir`). Chosen by Marcus over tokenizer fixes alone: the field is provably closed whatever syntax is missed. Costs alias names (`git co` records `?`). Tokenizer fixes (`\ `, `${…}`, `<( )`) ship too, so records and flags stay correct. |
| 2026-10-12 | Parse cap with an `(oversize)` marker record | T1.3 code review measured the decoder at 105 s for an 87 KB payload and the parse at 25 s for a 20 KB quoted message. Above the cap one value-free `? (oversize)` record is written when a free-standing `git` word is present. Chosen by Marcus over a silent cap and no cap. |
| 2026-10-12 | The guard's quadratic `_strip_quoted` is fixed in this spec (T1.5), both copies | Measured 3.2 s at 10 KB in the production guard. Chosen by Marcus over a separate issue; parity keeps the two copies equal. |
| 2026-10-12 | Parse cap 4096 bytes | Measured after T1.3/T1.5 made every step linear: a 15 KB command still cost up to ~1.3 s with dense shell syntax. At 4 KB the worst case is ~0.4 s and typical commands stay far below. Chosen by Marcus over 16 KB and 8 KB. |
| 2026-10-12 | T1.2 extracted the guard's inline executor test into `_has_shell_executor` (pattern_match.sh) | A pure refactor so the parity test can call both sides; behaviour unchanged, guard suite green. Recorded as Extra by the Phase 1 drift check. |
| 2026-10-12 | Git record budget 30 ms added (was 15 ms); fork-free writer fast path | T2.2 measured 42 ms added on macOS: ~20 ms writer forks (`_observability_prepare_field`), ~12 ms `git rev-parse` via the xcrun shim, ~6 ms source and parse. Chosen by Marcus: a fork-free writer path for short printable-ASCII values (helps every adapter) and a 30 ms budget, because the recorder runs in parallel with the guard. `rev-parse` stays (no builtin repo walk). |
| 2026-10-12 | `_observability_field` made linear (bisect) in the shared writer | T2.1 measured ~37 s for a key behind a 200 KB Agent prompt; fixed once in logwrite.sh rather than per adapter (single source of truth), differential-tested against the old function. |
| 2026-10-12 | A Skill tool call with an empty `skill` value writes no record | A truncated or drifted payload would otherwise add `skill=""` rows that pollute firing counts (CON-9: nothing rather than something wrong). Dispatches with an empty `subagent_type` are still recorded; the report ignores them (ADR-8). |
| 2026-10-12 | Report: uncreditable decided at the coverage join, not in `firing_events` | T4.1: `firing_events` has no inventory, so it cannot tell a spawn name from an inventory name. The reader sees the same result; the SDD's Complex Logic sentence was amended. Phase 4 drift check, accepted by Marcus. |
| 2026-10-12 | Report: an agent name any dispatch carried as `subagent_type` is never uncreditable | T4.1: an unnamed dispatch of a personal agent would otherwise be called a possible spawn name; it is listed as not in inventory instead. |
| 2026-10-12 | Report: bare and qualified records of one skill both credit it; a typed bare name never does | T4.1: before, a bare tool record beside a qualified one was left as unmatched (F4 AC1: both routes count). T4.1 review: a typed bare `/test` was summed into a plugin skill's `typed=` when a tool record shared the bare name; fixed. |
| 2026-10-12 | Report: unknown `route` values yield no firing; malformed or unhashable fields drop the record, never abort | T4.1/T4.2: matches the module's posture that unknown is excluded, never folded in. T4.1 review found a `TypeError` regression on unhashable fields; fixed. |
| 2026-10-12 | Report: per-route counts and the uncreditable list render in single-source and union coverage only; identical git operations collapse to one line with `(N records)` | T4.1/T4.2; F4 AC1 and AC3 are satisfied (the operations are still listed, with a count). Recorded as Extra by the Phase 4 drift check. |
| 2026-10-12 | Report: the matching-rule text states the settled rule; the spec-018 "confirmed at T3.6 … until then" wording is removed | 018 T3.6 closed 2026-09-08 (`05c838d`); found stale by the Phase 4 drift check. Chosen by Marcus along with four optional T4.2 review cleanups. |
| 2026-10-12 | Guard fast path tests the payload from `"command":"` to its end, not the command value alone | T5.1: cutting at the next `"` lets an escaped quote end the value early (`echo \"x\" && git reset --hard` would skip the guard). The superset only costs speed when a later field contains `git`/`gh`. Pinned by the escaped-quote test. |
| 2026-10-12 | Guard bats helper `_run_hook_with_cmd` emits compact JSON (`jq -nc`) | T5.1 spec review: the pretty-printed payloads never reached the fast path, so "every existing deny test still denies" was vacuous. Now the whole deny corpus runs on the real wire shape; a `*gh*`-only mutant fails 75 of 167. |
| 2026-10-12 | T5.1 validation: the `*git*`-only mutant is caught by "a gh command still reaches jq", not by the `gh api` deny test | Every `gh api` deny pattern contains `git/refs`, so that test cannot fail under the mutant. Perf warm-up runs inside the test (run 0 discarded), not in `setup()`, matching the SDD's "median of 20 after one warm-up". |
| 2026-10-12 | E2E probe (`scripts/observability/e2e_probe.sh`) commits with `probe-msg-<nonce>`, not `x` | A one-letter message cannot be searched for in the privacy scan. Probe passed 19/19 live three times; the interactive named dispatch (manual step, Marcus) recorded `dispatch name=probe-166` and `agent agent_type=probe-166`, deduped by the report. |
| 2026-10-12 | Release: tcs-helper 4.4.0 (feature), tcs-git-helpers 2.2.39 (patch); `plugin.json` left to the auto-bump on merge | Versions come from the top CHANGELOG heading (`auto-bump-versions.sh`). `origin/main` merged into the branch (Marcus) so the changelog-sync gate sees the bot's 2.2.38. |

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
