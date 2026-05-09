---
title: "Phase 2: Claude-side PreToolUse Hooks"
status: completed
version: "1.0"
phase: 2
---

# Phase 2: Claude-side PreToolUse Hooks

## Phase Context

**GATE**: Read all referenced files before starting this phase. Phase 1 must be COMPLETE.

**Specification References**:
- `[ref: SDD/§Building Block View — block-bad-git-ops/pre-edit-branch-check/protect-git-internals/worktree-exit-guard]` — component responsibilities
- `[ref: SDD/§Runtime View Primary Flow]` — push-to-closed-PR sequence
- `[ref: SDD/§Runtime View Secondary Flow]` — worktree-exit guard sequence
- `[ref: SDD/§Architecture Decisions ADR-1, ADR-9, ADR-11]` — ExitWorktree event, git cherry detection, setup-active sentinel
- `[ref: PRD/§Feature M1, M2, M3, M7, M8]` — push-to-closed-PR, branch creation, squash resume, destructive ops, worktree exit
- `[ref: PRD/§Feature M11]` — defense in depth (these hooks must fail safely)
- `[ref: research/security.md §5]` — Hook-bypass surface inventory
- `[ref: research/integration.md §3]` — gh CLI exit code truth table

**Key Decisions**:
- **ADR-1**: `worktree-exit-guard.sh` registers on `PreToolUse:ExitWorktree` (blockable native tool).
- **ADR-9**: Squash-merge detection uses `git cherry origin/<default> <branch>` primary; `git rev-list --parents` is advisory.
- **ADR-11**: `protect-git-internals.sh` checks `TCS_GIT_HELPERS_SETUP_ACTIVE=1` env-var; deny edits to `.githooks/*`/`.git/config`/`.git/hooks/*` outside setup context.
- **CON-9**: All regex patterns MUST use `[[:space:]]+` (NEVER `\s+`); word boundaries use `[[:>:]]` (NEVER `\b`).
- **EC2 (PRD)**: Cascading denials — emit ALL matched rules in one denial, not first-match-only.

**Dependencies**:
- Phase 1 COMPLETE (all `lib/*` modules functional with bats coverage).

---

## Tasks

This phase implements the four PreToolUse hooks that constitute the inner-ring enforcement. Each script sources `lib/*` modules and emits `permissionDecision` JSON via stdout per Claude Code hook contract.

- [x] **T2.1 block-bad-git-ops.sh** `[activity: backend-api]`

  1. Prime: SDD §Implementation Examples block-bad-git-ops dispatcher; PRD M1, M2, M3, M7 acceptance criteria; SDD §Hook Decision Matrix (state bypass).
  2. Test: Write `tests/bats/block-bad-git-ops.bats` covering, for each of the 14+ destructive patterns: positive match → deny with permissionDecision JSON containing rule name + reference link + override env-var name; negative match → exit 0; with override env-var set → allow with audit-logged consumption; bypass-during-rebase/merge/cherry-pick/bisect/detached-HEAD → exit 0 with stderr bypass message; cascading denials when 2+ rules match → both reported in single denial response (EC2). Also: `gh` truth-table cases for push pattern (CLOSED → deny, OPEN → allow, no-PR → allow, exit 4 → fail-open with warning, timeout → fail-open).
  3. Implement: Create `scripts/block-bad-git-ops.sh` per SDD §Implementation Examples skeleton. Sources `lib/git_state`, `lib/pattern_match`, `lib/override`, `lib/cache`, `lib/audit_log`. `_emit_permission_decision_deny` formats cascading denial JSON.
  4. Validate: bats passes; shellcheck clean; performance check ≤80ms p99 for non-push patterns; ≤5000ms p99 with timeout for push.
  5. Success: All M7 patterns deny by default `[ref: PRD/M7/AC1]`; all granular overrides work single-shot `[ref: PRD/M7/AC2 + ADR-5]`; master override emits warning `[ref: PRD/M7/AC3]`; gh fail-open verified `[ref: SDD/§gh Exit Code Truth Table]`.

- [x] **T2.2 pre-edit-branch-check.sh** `[activity: backend-api]` `[parallel: true]`

  1. Prime: `~/.claude/hooks/block-main-edits.sh` (reference shape); SDD §Building Block View — pre-edit-branch-check; M11 AC3 (coexistence with user-global hook).
  2. Test: Write `tests/bats/pre-edit-branch-check.bats`: deny on edit to file on main/master (matches user-global hook semantics); gitignored paths exempt; `CLAUDE_ALLOW_MAIN_EDITS=1` env-var allows; squash-merge orphan detection emits warning (NOT deny — non-main edits are recoverable); state-bypass cases (rebase etc.) skip checks.
  3. Implement: Create `scripts/pre-edit-branch-check.sh` augmenting (not replacing) user-global hook. Adds: warning when current branch is squash-merge orphan via `lib/git_state._is_branch_dangerously_merged`. Reuses denial JSON format from existing user-global hook.
  4. Validate: bats passes; shellcheck clean; ≤80ms p99 (local-git only).
  5. Success: deny on main/master `[ref: PRD/M11/AC3]`; gitignore exempt; warning on orphan branch `[ref: SDD/§Building Block View — pre-edit-branch-check]`.

- [x] **T2.3 protect-git-internals.sh** `[activity: backend-api]` `[parallel: true]`

  1. Prime: SDD §Implementation Examples ADR-11 sentinel logic; security.md §5 (block edits to .githooks/* etc.).
  2. Test: Write `tests/bats/protect-git-internals.bats`: edit to `<repo>/.githooks/pre-commit` denied when `TCS_GIT_HELPERS_SETUP_ACTIVE` unset; same edit allowed when set to `1`; edits to `.git/config`, `.git/hooks/foo`, `<repo>/.githooks/.config` follow same pattern; edits OUTSIDE these paths always allowed (hook returns exit 0 without touching tool_input).
  3. Implement: Create `scripts/protect-git-internals.sh` checking `tool_input.file_path` against the sensitive-path patterns. Registers alongside `pre-edit-branch-check.sh` on Edit/Write/NotebookEdit (both fire; aggregate semantics).
  4. Validate: bats passes; shellcheck clean; ≤80ms p99.
  5. Success: All sensitive-path edits denied without sentinel `[ref: ADR-11]`; sentinel allows during setup `[ref: SDD/§Implementation Examples — Block edits to git internals]`.

- [x] **T2.4 worktree-exit-guard.sh** `[activity: backend-api]` `[parallel: true]`

  1. Prime: SDD §Runtime View Secondary Flow worktree-exit; M8 acceptance criteria; ADR-1; research/integration.md §3.
  2. Test: Write `tests/bats/worktree-exit-guard.bats`: deny when working tree dirty (`git status --porcelain` non-empty); deny when untracked files present; deny when unmerged commits exist (`git cherry origin/<base> <branch>` has `+` lines); deny when unpushed commits exist; one denial response includes ALL four checks summary; `CLAUDE_ALLOW_WORKTREE_EXIT_WITH_CHANGES=1` allows once with override consumed; subsequent attempts re-deny.
  3. Implement: Create `scripts/worktree-exit-guard.sh` performing the four checks via `lib/git_state` helpers. Cascading denial format. Sources `lib/override` and `lib/audit_log`.
  4. Validate: bats passes; shellcheck clean; ≤500ms p99 (allows for `git cherry` on typical branches).
  5. Success: All 4 checks fire `[ref: PRD/M8/AC1, AC2]`; override single-shot works `[ref: PRD/M8/AC3 + ADR-5]`.

- [x] **T2.5 Hook Registration Update** `[activity: integration]`

  1. Prime: SDD §Plugin Layout hooks/hooks.json shape; T1.1's stub hook registration.
  2. Test: bats test asserting `hooks.json` registers exactly 4 PreToolUse entries (Bash matcher → block-bad-git-ops.sh; Edit|Write|NotebookEdit matcher → pre-edit-branch-check.sh AND protect-git-internals.sh; ExitWorktree matcher → worktree-exit-guard.sh) and (Phase 3 stubs) one SessionStart and one PostToolUse:Bash.
  3. Implement: Update `plugins/tcs-git-helpers/hooks/hooks.json` to register all Phase 2 hooks pointing to `${CLAUDE_PLUGIN_ROOT}/scripts/<name>.sh`. Multiple hooks per matcher are listed in array (per Claude Code aggregation semantics).
  4. Validate: bats passes; `claude --plugin-dir` loads cleanly; `/reload-plugins` works.
  5. Success: All 4 PreToolUse hooks fire on respective tool invocations `[ref: SDD/§External Interfaces inbound]`.

- [x] **T2.6 Phase 2 Validation** `[activity: validate]`

  Run all Phase 2 bats tests + shellcheck. Manual check via `claude --plugin-dir`:
  - Trigger each hook with synthetic repo from `tests/fixtures/repos/`
  - Verify denial messages match SDD format (≤15 lines, 4-part structure)
  - Verify override env-vars work single-shot per ADR-5
  - Verify performance budgets per SDD §Quality Requirements

  Success: All 4 PreToolUse hooks functional; M1, M2, M3, M7, M8 acceptance criteria fully met.

---

## Deliverables

- `plugins/tcs-git-helpers/scripts/block-bad-git-ops.sh`
- `plugins/tcs-git-helpers/scripts/pre-edit-branch-check.sh`
- `plugins/tcs-git-helpers/scripts/protect-git-internals.sh`
- `plugins/tcs-git-helpers/scripts/worktree-exit-guard.sh`
- Updated `plugins/tcs-git-helpers/hooks/hooks.json` registering all 4 PreToolUse hooks
- `plugins/tcs-git-helpers/tests/bats/{block-bad-git-ops,pre-edit-branch-check,protect-git-internals,worktree-exit-guard}.bats`
- All shellcheck-clean and bats-passing; performance budgets met.
