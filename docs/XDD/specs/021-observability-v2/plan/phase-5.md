---
title: "Phase 5: Guard fast path and end-to-end validation"
status: in_progress
version: "1.0"
phase: 5
---

# Phase 5: Guard fast path and end-to-end validation

## Phase Context

**GATE**: Read all referenced files before starting this phase.

**Specification References**:
- `[ref: SDD/Acceptance Criteria/F7]`, `[ref: SDD/ADR-6]`
- `[ref: SDD/Quality Requirements]` — performance, security, reliability, correctness
- `[ref: PRD/Success Metrics]`
- `plugins/tcs-git-helpers/scripts/block-bad-git-ops.sh` (:57-61), `plugins/tcs-git-helpers/scripts/lib/pattern_match.sh` (every `PATTERN_*` needs `git` or `gh`)
- memory `reference_hook-payloads-measured-2-1-296` — probe method

**Key Decisions**:
- ADR-6: the guard moves to `#!/bin/bash`; fast path right after `$(cat)`, before `jq`.
- The guard's verdict is not part of any record (PRD Won't Have).

**Dependencies**: T5.1 none. T5.2 and T5.3 need Phases 1–4.

---

## Tasks

Removes the guard's per-call cost on non-git commands, then proves the whole feature against a real Claude Code session.

- [ ] **T5.1 Guard fast path** `[activity: backend]` `[parallel: true]` `[component: tcs-git-helpers]`

  1. Prime: guard entry (:57-61), every `PATTERN_*` constant (all require `git` or `gh`) `[ref: SDD/ADR-6]` `[ref: SDD/Acceptance Criteria/F7]`
  2. Test (in `plugins/tcs-git-helpers/tests/bats/block-bad-git-ops.bats`): a non-git, non-gh command allows with no `jq` invocation (PATH stub counting calls), also with a `cwd` containing `github`; every existing deny test still denies; `gh api … DELETE` still denies; a perf case for the non-git path ≤ 5 ms at the median via `_perf_budget` (tcs-git-helpers `lib/helpers.bash`; warm in `setup()`)
  3. Implement: shebang `#!/bin/bash`; right after `INPUT=$(cat)`, test the command value only — `_cmd_tail="${INPUT#*\"command\":\"}"` then `case "$_cmd_tail" in *git*|*gh*) ;; *) exit 0 ;; esac`
  4. Validate: `bats --recursive plugins/tcs-git-helpers/tests/bats` green with plan count checked; shellcheck clean; mutate the case to `*git*` only and the `gh api` test fails
  5. Success: `[ref: PRD/F7 AC1, AC2]`

- [ ] **T5.2 End-to-end probe in a real session** `[activity: validate]`

  1. Prime: probe method (`claude -p --settings` in a scratch repo) and README § Context
  2. Test: install the bundle into a scratch home, register a scratch repo, enable recording; in headless runs: type a plugin skill with args, let the model call a skill, dispatch a named and an unnamed subagent that each run `git status` and `git commit --allow-empty -m "x"`, run `CLAUDE_ALLOW_RESET_HARD=1 git reset --hard` from the main session; type an unresolved `/nonexistent-skill` (expect no record, F1 AC4); then, manually, in one interactive session dispatch a named subagent (this step cannot be scripted; record the result in the PR). Expected: typed and tool `skill` records with routes; `dispatch` records with type and name; `git` records only for `commit` and `reset`, each with the right caller; `override_first: CLAUDE_ALLOW_RESET_HARD`; `git stash pop` (if exercised) with `action: pop`; the interactive SubagentStart record (spawn name) deduped by the report; a scan of `events.jsonl` finds none of the message, the paths or any value
  3. Implement: a reproducible probe script under the spec directory or `scripts/observability/` (no new runtime dependency), and fixes for whatever the probe finds (each with a regression test)
  4. Validate: the probe passes twice from a clean scratch state; the report over the probe's records shows the expected coverage and git section
  5. Success: `[ref: PRD/Success Metrics/Quality]`; `[ref: SDD/Quality Requirements]`

- [ ] **T5.3 Release readiness** `[activity: validate]`

  1. Prime: CHANGELOG conventions (root `[Unreleased]`, per-plugin next version), docs-sync map
  2. Test: full pytest; full bats for every plugin with the TAP plan check; perf suite; the three CI gates
  3. Implement: CHANGELOG entries for tcs-helper (h2, re-run setup), tcs-git-helpers (guard fast path) and the root; close-out notes for #165, #166, #172
  4. Validate: all green locally; CI green on the PR
  5. Success: every PRD acceptance criterion of F1–F7 is checked off in requirements.md with the task that proved it (F8 deferred); the Adoption, Engagement and Business Impact metrics are post-release and manual — noted in the PR, not gated

- [ ] **T5.4 Phase Validation** `[activity: validate]`

  - Confirm the plan's traceability table holds against the merged tests; run xdd-meta finalize after merge.
