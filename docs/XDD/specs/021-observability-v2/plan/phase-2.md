---
title: "Phase 2: Adapters"
status: pending
version: "1.0"
phase: 2
---

# Phase 2: Adapters

## Phase Context

**GATE**: Read all referenced files before starting this phase.

**Specification References**:
- `[ref: SDD/Implementation Examples/log_tool.sh fast path]`
- `[ref: SDD/Interface Specifications/Application Data Models]` — `skill` (route, args_present, source), `dispatch`, `git`
- `[ref: SDD/Runtime View]` — primary flow, error handling
- `[ref: SDD/Architecture Decisions; ADR-1, ADR-6, ADR-7, ADR-8, ADR-9]`
- `[ref: README/Context]` — measured payloads (2.1.296)
- `plugins/tcs-helper/scripts/observability/log_skill.sh`, `log_instructions.sh` — adapter conventions (relative `source`, drain on failure, exit 0, no stdout/stderr)

**Key Decisions**:
- ADR-6: `#!/bin/bash`; disabled → `cat >/dev/null; exit 0`; enabled → `_payload="$(cat)"`; a Bash payload whose command value has no `git` exits before any `source`.
- ADR-8: dispatch records never carry `tool_input.prompt`; `description` only as `detail:description`.
- ADR-7: typed records only for `expansion_type: slash_command`; `command_args` text never recorded.
- Caller fields are `caller`, `caller_agent_type`, `caller_agent_id` on both `dispatch` and `git`.

**Dependencies**: Phase 1 (writer, `git_ops.sh`).

---

## Tasks

Delivers the three recording paths: tool-route skills and dispatches, git commands with their caller, and typed skills.

- [ ] **T2.1 `log_tool.sh`: dispatch, fast path, skill and dispatch records** `[activity: backend]`

  1. Prime: fast-path example, data models, measured Agent payload (`subagent_type`, `name`, `description`, `prompt`, `tool_use_id`; `agent_id`/`agent_type` inside a subagent) `[ref: SDD/Implementation Examples]` `[ref: SDD/ADR-1, ADR-6, ADR-8]`
  2. Test: Skill payload → `skill` record with `route: tool`; Agent payload, named and unnamed → `dispatch` with `subagent_type`, `name` (empty when unnamed), `tool_use_id`, `caller`; inside a subagent → `caller: subagent` with `caller_agent_type`/`caller_agent_id`; a canary in `prompt` never appears; `description` appears only with detail on; non-git Bash payload → no record and no `source` (assert via a stub that would record being sourced), also when `cwd` contains `github`; disabled → no record, stdin drained; malformed, empty and 200 KB payloads → exit 0, empty stdout/stderr; other tool names → nothing; a perf case for the non-git path within `_perf_budget_ms` (copy `_perf_budget_ms`/`_now_ms` into this suite as the other observability suites do; warm the fixture in `setup()`; realistic `cwd`)
  3. Implement: `plugins/tcs-helper/scripts/observability/log_tool.sh` per the fast-path example; Skill and Agent branches via `_observability_field`; Bash branch hands off to T2.2
  4. Validate: `plugins/tcs-helper/tests/bats/observability-tool.bats` green; shellcheck clean; mutate the gate order (source before the substring test) and the perf or sourcing test fails
  5. Success: `[ref: PRD/F1 AC2]`; `[ref: PRD/F2 AC1, AC2, AC4]`; `[ref: SDD/Acceptance Criteria/F1, F2]`; non-git cost within CON-7 `[ref: SDD/Quality Requirements]`

- [ ] **T2.2 Git records from `log_tool.sh`** `[activity: backend]`

  1. Prime: primary flow and error handling `[ref: SDD/Runtime View]`; T1.3's parse output; `_observability_toplevel=` usage in `log_instructions.sh`
  2. Test: `git reset --hard` from the main session → one `git` record with `subcommand: reset`, `flags: --hard`, `caller: main`, `tool_use_id`; same inside a subagent → `caller: subagent` plus both caller fields; `CLAUDE_ALLOW_RESET_HARD=1 git reset --hard` → `overrides`, `override_first: CLAUDE_ALLOW_RESET_HARD`, value absent; a compound command with three git calls (one read-only) → two records; `git status` alone → nothing; no git → nothing; `git stash pop` → `action: pop`; a guard-denied `git reset --hard` with no override (guard registered alongside, as in a real session) is recorded; `git_ops.sh` missing → no git record, exit 0, skill/dispatch paths unaffected; the T1.3 secrets corpus end to end leaves no value in `events.jsonl` in reduced and detail mode; `git rev-parse` runs at most once per payload (count via a PATH stub)
  3. Implement: in `log_tool.sh`'s Bash branch, `source git_ops.sh` (guarded), decode, parse, resolve the toplevel once, one `_observability_write kind=git …` per parsed line
  4. Validate: `observability-git.bats` end-to-end cases green; perf case for one git record within 15 ms × slack; shellcheck clean
  5. Success: `[ref: PRD/F3 AC1, AC2, AC3, AC4, AC5, AC10]`; end to end `[ref: PRD/F3 AC6, AC7, AC8, AC9]`; `[ref: SDD/Acceptance Criteria/F3]`

- [ ] **T2.3 `log_expansion.sh`: typed skills** `[activity: backend]` `[parallel: true]`

  1. Prime: measured `UserPromptExpansion` payloads (`command_name` qualified for plugins: `tcs-issues:issue`; `command_source: plugin`/`projectSettings`) `[ref: README/Context]` `[ref: SDD/ADR-7]`
  2. Test: `slash_command` with args → `skill` record, `route: typed`, `skill` = `command_name`, `args_present: yes`, `source` recorded, no `command_args` or `prompt` text in reduced or detail mode (canary); without args → `args_present: no`; `expansion_type: mcp_prompt` → nothing; missing `command_name` → nothing; a 200 KB expanded prompt stays within the adapter budget; disabled, malformed, empty → exit 0, silent
  3. Implement: `plugins/tcs-helper/scripts/observability/log_expansion.sh` following `log_skill.sh`'s conventions (`#!/usr/bin/env bash`, CON-2 holds for it) except the read: use `$(cat)`, not `IFS= read -r -d ''` (ADR-6; the expansion payload carries the whole expanded prompt)
  4. Validate: `plugins/tcs-helper/tests/bats/observability-expansion.bats` green; shellcheck clean; mutate the `expansion_type` filter and a test fails
  5. Success: `[ref: PRD/F1 AC1, AC3, AC4]`; `[ref: SDD/Acceptance Criteria/F1]`

- [ ] **T2.4 Phase Validation** `[activity: validate]`

  - Run all observability bats suites and the parity suite; shellcheck every new script; confirm no adapter writes to stdout/stderr or exits non-zero on the malformed-payload corpus.
