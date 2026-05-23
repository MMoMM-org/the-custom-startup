---
title: "Phase 2: M2 — Tool-Input Override Scanning"
status: completed
version: "1.0"
phase: 2
---

# Phase 2: M2 — Tool-Input Override Scanning

## Phase Context

**GATE**: Read all referenced files before starting this phase.

**Specification References**:
- `[ref: PRD/Feature M2; lines: 150-175]` — M2 user story, acceptance criteria
- `[ref: PRD/Feature M2 details; lines: 240-278]` — business rules + edge cases (rule 2 anchoring; rule 5 stdin single-read)
- `[ref: SDD/Building Block View; lines: 295-322]` — CCCO + STIFO components
- `[ref: SDD/Interface Specifications; lines: 385-395]` — `_scan_tool_input_for_override` signature
- `[ref: SDD/Implementation Examples; lines: 450-471]` — regex construction pseudocode
- `[ref: SDD/Complex Logic; lines: 633-653]` — updated `_check_and_consume_override` algorithm
- `[ref: SDD/Runtime View Path A sub-path; lines: 531-557]` — sequence diagram for inline-override flow
- `[ref: SDD/Acceptance Criteria; lines: 1027-1076]` — M2-AC1..4 + M2-AC-REGEX

**Key Decisions**:
- **ADR-2**: Reuse `CMD` global already parsed by `block-bad-git-ops.sh:60`; no new stdin reads `[ref: SDD/ADR-2]`
- **ADR-3**: Regex anchored to `^${env_var}=1[[:space:]]+` — start-of-command, whitespace-terminated; prevents mid-command bypass and `CLAUDE_ALLOW_FOO=10` false-positives `[ref: SDD/ADR-3]`
- **ADR-4**: `CLAUDE_ALLOW_GIT_BAD_OPS` (master override) is also scannable via the same anchored pattern `[ref: SDD/ADR-4]`
- **ADR-6**: `_check_and_consume_override <rule>` signature frozen — internal logic only `[ref: SDD/ADR-6]`
- **ADR-7**: Stdin cache strategy — `CMD` global, no temp file, no memoization machinery `[ref: SDD/ADR-7]`

**Dependencies**:
- None. Phase 2 may execute in parallel with Phase 1 (disjoint files: `override.sh` only here).

---

## Tasks

Phase 2 delivers the M2 capability: `_check_and_consume_override` recognizes `CLAUDE_ALLOW_<RULE>=1` prepended to the Bash tool's command string (in addition to the existing shell-env path). Two implementation tasks plus a Python parity task (CON-2), then phase validation.

- [x] **T2.1 `_scan_tool_input_for_override` helper in `lib/override.sh`** `[activity: backend-api]` `[parallel: true]` `[ref: SDD/Implementation Examples; lines: 450-471]` `[ref: SDD/Interface Specifications; lines: 385-395]`

  1. **Prime**: Read `plugins/tcs-git-helpers/scripts/lib/override.sh` end-to-end. Internalize the existing `_check_and_consume_override` body (lines 66–153) — env-var check at 83–91, sentinel check, audit/consume tail. Read `[ref: SDD/Implementation Examples; lines: 456-471]` for the regex construction.
  2. **Test (RED)** — add cases to `plugins/tcs-git-helpers/tests/bats/test_override.bats`:
     - Match: `CMD="CLAUDE_ALLOW_PUSH_TO_CLOSED_PR=1 git push"` + arg `CLAUDE_ALLOW_PUSH_TO_CLOSED_PR` → returns 0.
     - Match (master): `CMD="CLAUDE_ALLOW_GIT_BAD_OPS=1 git push"` + arg `CLAUDE_ALLOW_GIT_BAD_OPS` → returns 0 (per ADR-4).
     - No match — empty CMD: `CMD=""` → returns 1, no error output (CON-5).
     - No match — unset CMD: `unset CMD` → returns 1, no error output.
     - No match — mid-command (M2-AC-REGEX): `CMD="git push && CLAUDE_ALLOW_PUSH_TO_CLOSED_PR=1 foo"` → returns 1.
     - No match — shell-quoting trick (M2 PRD edge case): `CMD="git push' && CLAUDE_ALLOW_PUSH_TO_CLOSED_PR=1; '"` → returns 1.
     - No match — `=10` false-positive guard: `CMD="CLAUDE_ALLOW_FOO=10 git push"` + arg `CLAUDE_ALLOW_FOO` → returns 1 (`[[:space:]]+` after `=1` rejects this).
     - No match — leading whitespace before token: `CMD=" CLAUDE_ALLOW_PUSH_TO_CLOSED_PR=1 git push"` → returns 1 (regex anchored to `^`).
  3. **Implement (GREEN)**: Add `_scan_tool_input_for_override <env_var>` to `lib/override.sh`. Body per `[ref: SDD/Implementation Examples; lines: 457-470]`: guard on `[ -z "${CMD:-}" ]` → return 1; construct `pattern="^${env_var}=1[[:space:]]+"`; `[[ "$CMD" =~ $pattern ]] && return 0; return 1`. Bash 3.2 only (CON-1). No I/O, no side effects.
  4. **Validate**: All eight BATS scenarios pass; `shellcheck scripts/lib/override.sh` clean. Re-running the existing override tests (env-var path) shows zero regressions.
  5. **Success**:
     - [x] Returns 0 only when CMD starts with `^${env_var}=1[[:space:]]+` `[ref: SDD/Interface Specifications; lines: 390-395]`
     - [x] CON-5 honored — empty/unset CMD returns 1 with no stderr `[ref: SDD/Constraints; lines: 57-60]`
     - [x] ADR-3 anchoring blocks all four bypass scenarios (mid-command, quoting trick, `=10`, leading whitespace) `[ref: PRD/Feature M2 edge cases; lines: 270-278]`

- [x] **T2.2 Integrate scan into `_check_and_consume_override`** `[activity: backend-api]` `[ref: SDD/Complex Logic; lines: 633-653]`

  1. **Prime**: Re-read existing `_check_and_consume_override` body (`override.sh:66-153`). Note the env-var-first → master-var → sentinel → consume flow. Re-read the updated algorithm at `[ref: SDD/Complex Logic; lines: 633-653]` — the scan is inserted ONLY when env-var path returns no match (M2-AC4 short-circuit).
  2. **Test (RED)** — add or update BATS cases in `test_override.bats`:
     - M2-AC1: Env-var `CLAUDE_ALLOW_PUSH_TO_CLOSED_PR=1` exported in shell, CMD irrelevant → consumed via env-var path (existing behavior, no regression); sentinel written; scan NOT called (verify via stub-spy on `_scan_tool_input_for_override`).
     - M2-AC2: Env-var absent, `CMD="CLAUDE_ALLOW_PUSH_TO_CLOSED_PR=1 git push origin foo"` → consumed via scan path; sentinel written; audit log line appended with `tool_input_truncated` field (first 80 chars of CMD per the SDD audit-log extension).
     - M2-AC3: Env-var absent, CMD empty/unset → no override; sentinel NOT written; function returns 1; no error output (CON-5).
     - M2-AC4: Env-var AND prefix both present → consumed via env-var path; scan never invoked (verified via spy); only one sentinel write.
     - Master-override scan: `CLAUDE_ALLOW_GIT_BAD_OPS=1 git push ...` in CMD with no env-var → consumed via scan path with `OVERRIDE_MASTER=1`; audit log reflects master override.
     - Granular-over-master precedence preserved: when both `CLAUDE_ALLOW_PUSH_TO_CLOSED_PR=1` and `CLAUDE_ALLOW_GIT_BAD_OPS=1` env-vars set, granular wins (existing behavior, no regression).
     - Single-shot double-tap window still fires: two consecutive identical invocations within 5s → second one denied (M2 path does not bypass the sentinel; CON-4).
  3. **Implement (GREEN)**: Edit `_check_and_consume_override` body per `[ref: SDD/Complex Logic; lines: 633-653]`. Order inside the function: (a) reset `OVERRIDE_VAR=""`, `OVERRIDE_MASTER="0"`; (b) env-var check (existing path lines 83–91 — unchanged); (c) NEW — if env-var path returned no match, call `_scan_tool_input_for_override "$env_var"`; on hit, set `OVERRIDE_VAR=$env_var`, `OVERRIDE_MASTER=0`; (d) NEW — if still no match, call `_scan_tool_input_for_override "$master_var"`; on hit, set `OVERRIDE_VAR=$master_var`, `OVERRIDE_MASTER=1`; (e) if still no match, return 1; (f) existing sentinel + audit + consume tail unchanged, except `_audit_log` call adds a `tool_input_truncated` field (first 80 chars of CMD) when the override came from the scan path. Signature unchanged (ADR-6/CON-3).
  4. **Validate**: All M2 BATS cases pass; existing M7 / shell-env override cases pass without modification (regression guard); `shellcheck scripts/lib/override.sh` clean; verify audit-log JSONL still parses as one JSON object per line.
  5. **Success**:
     - [x] M2-AC1 — shell env-var path unchanged; scan not invoked when env-var present `[ref: SDD/Acceptance Criteria; lines: 1027-1034]` `[ref: PRD/AC-M2.1]`
     - [x] M2-AC2 — command-string prefix consumed exactly once; sentinel + audit recorded `[ref: SDD/Acceptance Criteria; lines: 1036-1043]` `[ref: PRD/AC-M2.2]`
     - [x] M2-AC3 — empty/missing CMD falls back to env-var-only without error `[ref: SDD/Acceptance Criteria; lines: 1045-1051]` `[ref: PRD/AC-M2.3]`
     - [x] M2-AC4 — env-var canonical; scan short-circuited when env-var path succeeds `[ref: SDD/Acceptance Criteria; lines: 1053-1059]` `[ref: PRD/AC-M2.4]`
     - [x] CON-3 / ADR-6 honored — `_check_and_consume_override` signature unchanged (verified by all 5+ existing callsites compiling without edits) `[ref: SDD/Constraints; lines: 48-50]`
     - [x] CON-4 honored — 5s double-tap sentinel still fires on scan-path consumption `[ref: SDD/Constraints; lines: 52-55]`

- [x] **T2.3 Python parity rows in `test_drift_check.py`** `[activity: backend-api]` `[parallel: true]` `[ref: SDD/Constraints; lines: 42-46]`

  1. **Prime**: Read `plugins/tcs-git-helpers/tests/python/test_drift_check.py` to learn the existing parity-row structure (input → expected classification). CON-2 requires bash and Python to agree on regex/classification behavior whenever both implementations exist.
  2. **Test (RED)** — author parity rows in pytest form. Rows mirror the BATS scenarios from T2.1: positive match, master positive match, empty CMD, mid-command bypass, quoting trick, `=10` false-positive, leading-whitespace bypass. Each row asserts that the Python equivalent of `_scan_tool_input_for_override` agrees with bash on whether the prefix matches.
  3. **Implement (GREEN)**: If a Python equivalent helper does not yet exist in the drift-check module, add a minimal Python function `scan_tool_input_for_override(cmd, env_var) -> bool` mirroring the bash regex (`^{env_var}=1\\s+`). If a helper already exists, extend it for the master-override case (ADR-4) if missing. Use `re.match` (Python `re` defaults to start-anchored when using `re.match`; `\\s+` matches `[[:space:]]+` equivalently).
  4. **Validate**: `python -m pytest tests/python/test_drift_check.py` — all rows pass. Run the bash and Python implementations on a shared fixture and confirm identical outputs (parity).
  5. **Success**:
     - [x] CON-2 satisfied — every BATS regex scenario has a corresponding pytest parity row that produces the same classification `[ref: SDD/Constraints; lines: 42-46]`
     - [x] Python helper handles both granular and master env-var names `[ref: SDD/ADR-4; lines: 810-833]`

- [x] **T2.4 Phase 2 Validation** `[activity: validate]`

  - Run all M2 BATS cases (`bats tests/bats/test_override.bats`) — all pass.
  - Run all parity tests (`python -m pytest tests/python/test_drift_check.py`) — all pass.
  - Run the full `tests/bats/` suite — no regressions in env-var override path or sentinel behavior.
  - `shellcheck scripts/lib/override.sh` — clean.
  - Manual smoke: from a Claude session, attempt `CLAUDE_ALLOW_PUSH_TO_CLOSED_PR=1 git push` on a branch that would otherwise hit the deny path; verify it succeeds in one attempt. Verify audit log records `tool_input_truncated`.
  - Verify against PRD M2 ACs (M2-AC1..4) and the M2-AC-REGEX edge case.
