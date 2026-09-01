#!/usr/bin/env bash
# tests/e2e/dogfood.sh — End-to-end dogfood test driver for tcs-git-helpers.
#
# Spec refs:
#   - PRD §Feature M1-M12 acceptance criteria
#   - SDD §Quality Requirements (per-hook performance budgets)
#   - SDD §Risks Implementation Gotchas (bash 3.2 caveats)
#   - research/performance.md §7 (10 worst-case scenarios)
#   - plan/phase-6.md T6.1 (this file's contract)
#
# Purpose:
#   Drive every claim made by the plugin's acceptance criteria against
#   real synthetic git repos and the gh-stub, end-to-end. Each scenario
#   asserts the expected denial / allow / recovery path AND measures
#   wall-clock time so performance regressions are caught alongside
#   functional regressions.
#
# Usage:
#   tests/e2e/dogfood.sh                 # run all 10 scenarios, summary report
#   tests/e2e/dogfood.sh --scenario 5    # run scenario 5 only
#   tests/e2e/dogfood.sh --list          # enumerate scenarios with brief
#   tests/e2e/dogfood.sh --verbose       # surface hook stderr / fixture noise
#
# Exit:
#   0  every scenario PASS
#   1  one or more scenarios FAIL (or unhandled error)
#   2  bad CLI arg
#
# Constraints:
#   - bash 3.2 compatible (CON-1; macOS /bin/bash 3.2.57). NO `declare -A`,
#     `mapfile`, `readarray`, `${var,,}`. Verified by scenario 10.
#   - Network-isolated: PATH-shadows `gh` to fixtures stub. NO real GitHub
#     calls. NO `claude` CLI invocations (deterministic + no API key).
#   - Self-cleaning: all synthetic repos under $TMPDIR/tcs-e2e-dogfood.XXXXXX,
#     wiped on EXIT trap. CLAUDE_PLUGIN_DATA sandboxed inside that root so
#     override sentinels and audit logs never leak into the user's data dir.
#   - Each scenario function MUST be self-contained: setup + exercise + assert
#     + emit a single PASS/FAIL/SKIP line with timing. Aggregator parses those.

# shellcheck disable=SC2030,SC2031  # GH_STUB_SCENARIO export inside subshell
                                    # is intentional — each scenario sandboxes
                                    # its env-vars in a (...) group on purpose.
# shellcheck disable=SC2329          # _cleanup is invoked indirectly via trap.

set -uo pipefail

# ---------------------------------------------------------------------------
# Paths & globals
# ---------------------------------------------------------------------------

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PLUGIN_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
SCRIPTS_DIR="$PLUGIN_ROOT/scripts"
TEMPLATES_DIR="$PLUGIN_ROOT/templates"
FIXTURES_DIR="$PLUGIN_ROOT/tests/fixtures"

VERBOSE=0
ONE_SCENARIO=""
LIST_ONLY=0

# Aggregate counters (populated by _emit_result).
TOTAL_RUN=0
TOTAL_PASS=0
TOTAL_FAIL=0
TOTAL_SKIP=0
PERF_VIOLATIONS=""        # "scenario|budget|measured" lines
START_EPOCH_S=$(date +%s)

# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------

_usage() {
  cat <<'EOF'
tests/e2e/dogfood.sh — tcs-git-helpers end-to-end dogfood driver

  --scenario N    Run scenario N only (1..10).
  --list          Enumerate scenarios; do not run.
  --verbose       Surface hook stderr / fixture build noise on stdout.
  -h | --help     Show this help.

Exit 0 if all selected scenarios PASS, non-zero otherwise.
EOF
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --scenario)
      ONE_SCENARIO="${2:-}"
      shift 2 || { _usage; exit 2; }
      ;;
    --scenario=*)
      ONE_SCENARIO="${1#--scenario=}"
      shift
      ;;
    --list)
      LIST_ONLY=1
      shift
      ;;
    --verbose|-v)
      VERBOSE=1
      shift
      ;;
    -h|--help)
      _usage
      exit 0
      ;;
    *)
      printf 'dogfood.sh: unknown arg: %s\n' "$1" >&2
      _usage >&2
      exit 2
      ;;
  esac
done

if [ -n "$ONE_SCENARIO" ]; then
  case "$ONE_SCENARIO" in
    ''|*[!0-9]*) printf 'dogfood.sh: --scenario expects an integer\n' >&2; exit 2 ;;
  esac
fi

# ---------------------------------------------------------------------------
# Workspace + cleanup
# ---------------------------------------------------------------------------

WORK_ROOT=$(mktemp -d "${TMPDIR:-/tmp}/tcs-e2e-dogfood.XXXXXX")
REPOS_ROOT=""             # populated lazily by _build_fixtures
PLUGIN_DATA="$WORK_ROOT/plugin-data"
mkdir -p "$PLUGIN_DATA"

_cleanup() {
  local rc=$?
  if [ -n "${WORK_ROOT:-}" ] && [ -d "$WORK_ROOT" ]; then
    chmod -R u+rwX "$WORK_ROOT" 2>/dev/null || true
    rm -rf "$WORK_ROOT" 2>/dev/null || true
  fi
  return "$rc"
}
trap _cleanup EXIT INT TERM

# ---------------------------------------------------------------------------
# Logging helpers
# ---------------------------------------------------------------------------

_vlog() { [ "$VERBOSE" = "1" ] && printf '  [v] %s\n' "$*"; }
_section() { printf '\n── Scenario %s: %s ──\n' "$1" "$2"; }

# Wall-clock helper that reports milliseconds. Uses Python because bash
# arithmetic can't handle subsecond. Falls back to integer seconds if Python
# is unavailable (rare on macOS — both /usr/bin/python3 and the homebrew one
# are common). Bash 3.2 compatible: no $EPOCHREALTIME (that's bash 5+).
_now_ms() {
  if command -v python3 >/dev/null 2>&1; then
    python3 -c 'import time; print(int(time.time()*1000))'
    return 0
  fi
  if command -v perl >/dev/null 2>&1; then
    perl -MTime::HiRes=time -e 'printf "%d", time()*1000'
    return 0
  fi
  # Last resort: seconds × 1000 (loses sub-second resolution).
  printf '%s000' "$(date +%s)"
}

# ---------------------------------------------------------------------------
# Result emission — every scenario funnels through here so the aggregator
# stays the single source of truth for the summary report.
# ---------------------------------------------------------------------------
#
# Args: $1=scenario# $2=name $3=status[PASS|FAIL|SKIP] $4=elapsed_ms
#       $5=budget_ms (optional; "" means no budget) $6=detail (optional)
_emit_result() {
  local n="$1" name="$2" status="$3" elapsed="$4"
  local budget="${5:-}" detail="${6:-}"
  local line over=""

  TOTAL_RUN=$((TOTAL_RUN + 1))
  case "$status" in
    PASS) TOTAL_PASS=$((TOTAL_PASS + 1)) ;;
    FAIL) TOTAL_FAIL=$((TOTAL_FAIL + 1)) ;;
    SKIP) TOTAL_SKIP=$((TOTAL_SKIP + 1)) ;;
  esac

  if [ -n "$budget" ] && [ "$status" = "PASS" ] && [ "$elapsed" -gt "$budget" ]; then
    over=" [PERF: ${elapsed}ms > ${budget}ms budget]"
    PERF_VIOLATIONS="${PERF_VIOLATIONS}${n}|${name}|${budget}|${elapsed}
"
  fi

  if [ -n "$detail" ]; then
    line=$(printf '  S%-2s %-44s  %-4s  %5sms%s  — %s' \
      "$n" "$name" "$status" "$elapsed" "$over" "$detail")
  else
    line=$(printf '  S%-2s %-44s  %-4s  %5sms%s' \
      "$n" "$name" "$status" "$elapsed" "$over")
  fi
  printf '%s\n' "$line"
}

# ---------------------------------------------------------------------------
# Hook runners
# ---------------------------------------------------------------------------
#
# Build the PreToolUse JSON envelope (Bash) and pipe it into a hook script.
# Returns: stdout via $HOOK_STDOUT, stderr via $HOOK_STDERR, exit via $HOOK_RC.
_run_bash_hook() {
  local hook="$1" cmd="$2"
  local input out_f err_f
  input=$(jq -n --arg c "$cmd" '{tool_name:"Bash", tool_input:{command:$c}}')
  out_f=$(mktemp "$WORK_ROOT/hook-out.XXXXXX")
  err_f=$(mktemp "$WORK_ROOT/hook-err.XXXXXX")
  printf '%s' "$input" | bash "$hook" >"$out_f" 2>"$err_f"
  HOOK_RC=$?
  HOOK_STDOUT=$(cat "$out_f")
  HOOK_STDERR=$(cat "$err_f")
  rm -f "$out_f" "$err_f"
  _vlog "hook=$hook rc=$HOOK_RC stdout=$HOOK_STDOUT"
  return 0
}

_run_exit_worktree_hook() {
  local hook="$1" worktree="$2"
  local input out_f err_f
  input=$(jq -n --arg p "$worktree" \
    '{tool_name:"ExitWorktree", tool_input:{worktree_path:$p}}')
  out_f=$(mktemp "$WORK_ROOT/hook-out.XXXXXX")
  err_f=$(mktemp "$WORK_ROOT/hook-err.XXXXXX")
  printf '%s' "$input" | bash "$hook" >"$out_f" 2>"$err_f"
  HOOK_RC=$?
  HOOK_STDOUT=$(cat "$out_f")
  HOOK_STDERR=$(cat "$err_f")
  rm -f "$out_f" "$err_f"
  return 0
}

_run_session_start_hook() {
  local hook="$1"
  local out_f err_f
  out_f=$(mktemp "$WORK_ROOT/hook-out.XXXXXX")
  err_f=$(mktemp "$WORK_ROOT/hook-err.XXXXXX")
  printf '{}' | bash "$hook" >"$out_f" 2>"$err_f"
  HOOK_RC=$?
  HOOK_STDOUT=$(cat "$out_f")
  HOOK_STDERR=$(cat "$err_f")
  rm -f "$out_f" "$err_f"
  return 0
}

# Helper assertions — set RESULT_DETAIL on failure so the caller can pass
# it into _emit_result.
_is_deny() {
  case "$1" in
    *'"permissionDecision":"deny"'*) return 0 ;;
    *) return 1 ;;
  esac
}

_contains() {
  case "$1" in
    *"$2"*) return 0 ;;
    *) return 1 ;;
  esac
}

# ---------------------------------------------------------------------------
# Fixture build (lazy — once per run)
# ---------------------------------------------------------------------------

_build_fixtures() {
  if [ -n "$REPOS_ROOT" ] && [ -d "$REPOS_ROOT" ]; then
    return 0
  fi
  REPOS_ROOT="$WORK_ROOT/repos"
  mkdir -p "$REPOS_ROOT"
  if [ "$VERBOSE" = "1" ]; then
    bash "$FIXTURES_DIR/repos/build.sh" "$REPOS_ROOT" >/dev/null
  else
    bash "$FIXTURES_DIR/repos/build.sh" "$REPOS_ROOT" >/dev/null 2>&1
  fi
  _vlog "fixtures built under $REPOS_ROOT"
}

# Plumb the gh-stub into PATH for every scenario. Each scenario is free to
# pin GH_STUB_SCENARIO=… inside its own subshell.
_setup_path() {
  PATH="$FIXTURES_DIR/gh_stubs:$PATH"
  export PATH
}

# Sandbox per-scenario: each scenario runs in a subshell that exports its own
# CLAUDE_PLUGIN_DATA under WORK_ROOT, so the audit/sentinel side-effects don't
# leak between scenarios.
_scenario_sandbox_env() {
  local n="$1"
  CLAUDE_PLUGIN_DATA="$PLUGIN_DATA/s${n}"
  mkdir -p "$CLAUDE_PLUGIN_DATA"
  export CLAUDE_PLUGIN_DATA
  CLAUDE_PLUGIN_ROOT="$PLUGIN_ROOT"
  export CLAUDE_PLUGIN_ROOT
  # Defensive: clear any inherited override / sentinel state.
  unset CLAUDE_ALLOW_RESET_HARD CLAUDE_ALLOW_CLEAN_FORCE \
        CLAUDE_ALLOW_DESTRUCTIVE_CHECKOUT CLAUDE_ALLOW_DESTRUCTIVE_RESTORE \
        CLAUDE_ALLOW_FORCE_BRANCH_DELETE CLAUDE_ALLOW_STASH_DESTROY \
        CLAUDE_ALLOW_REFLOG_EXPIRE CLAUDE_ALLOW_NO_VERIFY \
        CLAUDE_ALLOW_PUSH_TO_CLOSED_PR CLAUDE_ALLOW_FORCE_PUSH \
        CLAUDE_ALLOW_REMOTE_BRANCH_DELETE CLAUDE_ALLOW_BRANCH_FROM_UNFINISHED \
        CLAUDE_ALLOW_RESUME_MERGED_BRANCH CLAUDE_ALLOW_HOOKSPATH_OVERRIDE \
        CLAUDE_ALLOW_GIT_BAD_OPS CLAUDE_ALLOW_WORKTREE_EXIT_WITH_CHANGES \
        TCS_GIT_HELPERS_SETUP_ACTIVE GH_STUB_SCENARIO 2>/dev/null || true
}

# ---------------------------------------------------------------------------
# Scenario 1: clean repo, install plugin (simulated), verify .githooks/ files
# ---------------------------------------------------------------------------
#
# We don't drive the full /tcs-git-helpers:git-setup skill (that requires a
# Claude session). Instead, we replicate its core file-copy + hooksPath
# semantics: copy templates into the repo, set core.hooksPath, verify that
# the version markers landed and `git config core.hooksPath` returns the
# right path. The setup skill's own bats tests cover its full behaviour.
_scenario_1() {
  local n=1 name="setup install copies templates + sets hooksPath" t0 t1 elapsed
  _section "$n" "$name"
  t0=$(_now_ms)
  (
    set -u
    _scenario_sandbox_env "$n"
    _build_fixtures
    local repo="$REPOS_ROOT/clean-repo"
    cd "$repo" || exit

    # Copy templates verbatim (mirrors the setup skill's copy step).
    mkdir -p .githooks
    cp "$TEMPLATES_DIR/githooks/pre-commit"  .githooks/pre-commit
    cp "$TEMPLATES_DIR/githooks/commit-msg"  .githooks/commit-msg
    cp "$TEMPLATES_DIR/githooks/pre-push"    .githooks/pre-push
    cp "$TEMPLATES_DIR/githooks/post-merge"  .githooks/post-merge
    chmod +x .githooks/pre-commit .githooks/commit-msg \
             .githooks/pre-push .githooks/post-merge

    # Set hooksPath inside the protected window — the setup skill exports
    # TCS_GIT_HELPERS_SETUP_ACTIVE=1 inside a subshell to permit this. Our
    # subshell here mirrors that.
    export TCS_GIT_HELPERS_SETUP_ACTIVE=1
    git config core.hooksPath .githooks

    # Verify the four hook files have a tcs-git-helpers semver marker.
    for h in pre-commit commit-msg pre-push post-merge; do
      grep -q "tcs-git-helpers: v" ".githooks/$h" \
        || { echo "S1: marker missing in .githooks/$h"; exit 1; }
    done

    # Verify hooksPath landed.
    actual=$(git config --get core.hooksPath)
    [ "$actual" = ".githooks" ] \
      || { echo "S1: hooksPath=$actual, expected .githooks"; exit 1; }

    # Setup skill explicitly does NOT auto-commit. Verify working tree shows
    # the .githooks/ as an untracked addition.
    porcelain=$(git status --porcelain)
    case "$porcelain" in
      *".githooks/"*) : ;;
      *) echo "S1: .githooks not visible in porcelain: $porcelain"; exit 1 ;;
    esac

    exit 0
  )
  local rc=$?
  t1=$(_now_ms); elapsed=$((t1 - t0))
  if [ "$rc" -eq 0 ]; then
    _emit_result "$n" "$name" PASS "$elapsed"
  else
    _emit_result "$n" "$name" FAIL "$elapsed" "" "subshell exit=$rc"
  fi
}

# ---------------------------------------------------------------------------
# Scenario 2: M1 — push to closed PR is denied; override allows once.
# ---------------------------------------------------------------------------
_scenario_2() {
  local n=2 name="M1 push-to-closed-PR deny + override once" t0 t1 elapsed
  _section "$n" "$name"
  t0=$(_now_ms)
  (
    set -u
    _scenario_sandbox_env "$n"
    _build_fixtures
    cd "$REPOS_ROOT/closed-pr" || exit
    export GH_STUB_SCENARIO=closed-pr

    _run_bash_hook "$SCRIPTS_DIR/block-bad-git-ops.sh" \
      "git push origin feat/closed-pr-branch"
    _is_deny "$HOOK_STDOUT" \
      || { echo "S2 part-A: expected deny, got: $HOOK_STDOUT"; exit 1; }
    _contains "$HOOK_STDOUT" "PUSH_TO_CLOSED_PR" \
      || { echo "S2 part-A: missing rule name"; exit 1; }

    # Override: granular env-var consumed once + audit row written.
    # Bust the 60s PR-state cache so this scenario does not depend on the
    # first call's cache hit.
    rm -rf "$CLAUDE_PLUGIN_DATA/cache" 2>/dev/null || true
    export CLAUDE_ALLOW_PUSH_TO_CLOSED_PR=1
    _run_bash_hook "$SCRIPTS_DIR/block-bad-git-ops.sh" \
      "git push origin feat/closed-pr-branch"
    if _is_deny "$HOOK_STDOUT"; then
      echo "S2 part-B: override should ALLOW, got: $HOOK_STDOUT"; exit 1
    fi
    audit="$CLAUDE_PLUGIN_DATA/audit/overrides.jsonl"
    [ -s "$audit" ] || { echo "S2 part-B: audit log missing/empty"; exit 1; }
    grep -q "CLAUDE_ALLOW_PUSH_TO_CLOSED_PR" "$audit" \
      || { echo "S2 part-B: audit row missing env_var"; exit 1; }

    exit 0
  )
  local rc=$?
  t1=$(_now_ms); elapsed=$((t1 - t0))
  if [ "$rc" -eq 0 ]; then
    _emit_result "$n" "$name" PASS "$elapsed"
  else
    _emit_result "$n" "$name" FAIL "$elapsed" "" "subshell exit=$rc"
  fi
}

# ---------------------------------------------------------------------------
# Scenario 3: M2 — branch from unfinished work is denied.
# ---------------------------------------------------------------------------
_scenario_3() {
  local n=3 name="M2 branch-from-unfinished deny" t0 t1 elapsed
  _section "$n" "$name"
  t0=$(_now_ms)
  (
    set -u
    _scenario_sandbox_env "$n"
    _build_fixtures
    # clean-unmerged: branch ahead of origin, no PR (gh stub no-pr scenario).
    cd "$REPOS_ROOT/clean-unmerged" || exit
    export GH_STUB_SCENARIO=no-pr

    _run_bash_hook "$SCRIPTS_DIR/block-bad-git-ops.sh" \
      "git checkout -b feat/another"
    _is_deny "$HOOK_STDOUT" \
      || { echo "S3 part-A: expected deny, got: $HOOK_STDOUT"; exit 1; }
    _contains "$HOOK_STDOUT" "BRANCH_FROM_UNFINISHED" \
      || { echo "S3 part-A: missing rule name"; exit 1; }

    # Dirty tree variant — switch -c form
    cd "$REPOS_ROOT/dirty" || exit
    _run_bash_hook "$SCRIPTS_DIR/block-bad-git-ops.sh" \
      "git switch -c feat/another"
    _is_deny "$HOOK_STDOUT" \
      || { echo "S3 part-B: expected deny on dirty, got: $HOOK_STDOUT"; exit 1; }
    _contains "$HOOK_STDOUT" "BRANCH_FROM_UNFINISHED" \
      || { echo "S3 part-B: missing rule name"; exit 1; }

    exit 0
  )
  local rc=$?
  t1=$(_now_ms); elapsed=$((t1 - t0))
  if [ "$rc" -eq 0 ]; then
    _emit_result "$n" "$name" PASS "$elapsed"
  else
    _emit_result "$n" "$name" FAIL "$elapsed" "" "subshell exit=$rc"
  fi
}

# ---------------------------------------------------------------------------
# Scenario 4: M3 — squash-merged branch checkout is denied; merge-commit
#                  branch is allowed (control).
# ---------------------------------------------------------------------------
_scenario_4() {
  local n=4 name="M3 squash-merged deny + merge-commit allow" t0 t1 elapsed
  _section "$n" "$name"
  t0=$(_now_ms)
  (
    set -u
    _scenario_sandbox_env "$n"
    _build_fixtures
    # The squash-merged fixture leaves us on feat/squashed; the canonical
    # M3 trigger is "git checkout <orphan-branch>" while sitting elsewhere.
    cd "$REPOS_ROOT/squash-merged" || exit
    git checkout -q main
    export GH_STUB_SCENARIO=no-pr

    _run_bash_hook "$SCRIPTS_DIR/block-bad-git-ops.sh" \
      "git checkout feat/squashed"
    _is_deny "$HOOK_STDOUT" \
      || { echo "S4 part-A: expected deny on squashed, got: $HOOK_STDOUT"; exit 1; }
    _contains "$HOOK_STDOUT" "RESUME_MERGED_BRANCH" \
      || { echo "S4 part-A: missing rule name"; exit 1; }

    # Control: merge-commit-merged should NOT trigger M3 — branch tip is
    # an ancestor of origin/main, so checkout is safe.
    cd "$REPOS_ROOT/merge-commit-merged" || exit
    git checkout -q main
    _run_bash_hook "$SCRIPTS_DIR/block-bad-git-ops.sh" \
      "git checkout feat/merge-commit"
    if _is_deny "$HOOK_STDOUT"; then
      echo "S4 part-B: merge-commit branch wrongly denied: $HOOK_STDOUT"
      exit 1
    fi

    exit 0
  )
  local rc=$?
  t1=$(_now_ms); elapsed=$((t1 - t0))
  if [ "$rc" -eq 0 ]; then
    _emit_result "$n" "$name" PASS "$elapsed"
  else
    _emit_result "$n" "$name" FAIL "$elapsed" "" "subshell exit=$rc"
  fi
}

# ---------------------------------------------------------------------------
# Scenario 5: M7 — destructive patterns each deny; one override allows once.
# ---------------------------------------------------------------------------
#
# The 10 patterns below are the canonical M7 list (PRD §M7). RESET_HARD is
# tested twice: once unblocked (deny) and once with CLAUDE_ALLOW_RESET_HARD
# (allow). All others assert deny only — full granular-override coverage
# is exercised by tests/bats/block-bad-git-ops.bats.
_scenario_5() {
  local n=5 name="M7 destructive patterns x10 + override once" t0 t1 elapsed
  _section "$n" "$name"
  t0=$(_now_ms)
  (
    set -u
    _scenario_sandbox_env "$n"
    _build_fixtures
    cd "$REPOS_ROOT/clean-unmerged" || exit
    export GH_STUB_SCENARIO=no-pr

    # rule_name|command pairs. Pipe-delimited because spaces are common in cmd.
    cases='
RESET_HARD|git reset --hard origin/main
CLEAN_FORCE|git clean -fdx
DESTRUCTIVE_CHECKOUT|git checkout .
DESTRUCTIVE_CHECKOUT|git checkout -- src/foo.ts
DESTRUCTIVE_RESTORE|git restore --worktree --source=HEAD~1 src/
FORCE_BRANCH_DELETE|git branch -D feat/clean-unmerged
STASH_DESTROY|git stash drop stash@{0}
REFLOG_EXPIRE|git reflog expire --expire=now --all
NO_VERIFY|git commit --no-verify -m "skip"
FORCE_PUSH|git push --force origin feat/clean-unmerged
'
    fail_msg=""
    n_cases=0
    while IFS= read -r line; do
      [ -z "$line" ] && continue
      rule="${line%%|*}"
      cmd="${line#*|}"
      n_cases=$((n_cases + 1))
      _run_bash_hook "$SCRIPTS_DIR/block-bad-git-ops.sh" "$cmd"
      if ! _is_deny "$HOOK_STDOUT"; then
        fail_msg="$rule did not deny: cmd='$cmd'"
        break
      fi
      if ! _contains "$HOOK_STDOUT" "$rule"; then
        fail_msg="$rule deny missing rule name: $HOOK_STDOUT"
        break
      fi
    done <<EOF
$cases
EOF
    [ "$n_cases" -ge 10 ] \
      || { echo "S5: parsed $n_cases cases, expected ≥10"; exit 1; }
    [ -z "$fail_msg" ] \
      || { echo "S5: $fail_msg"; exit 1; }

    # Override pass: granular CLAUDE_ALLOW_RESET_HARD allows once.
    rm -rf "$CLAUDE_PLUGIN_DATA/cache" 2>/dev/null || true
    export CLAUDE_ALLOW_RESET_HARD=1
    _run_bash_hook "$SCRIPTS_DIR/block-bad-git-ops.sh" \
      "git reset --hard HEAD~1"
    if _is_deny "$HOOK_STDOUT"; then
      echo "S5: override should ALLOW reset --hard, got: $HOOK_STDOUT"; exit 1
    fi

    exit 0
  )
  local rc=$?
  t1=$(_now_ms); elapsed=$((t1 - t0))
  if [ "$rc" -eq 0 ]; then
    _emit_result "$n" "$name" PASS "$elapsed"
  else
    _emit_result "$n" "$name" FAIL "$elapsed" "" "subshell exit=$rc"
  fi
}

# ---------------------------------------------------------------------------
# Scenario 6: M8 — worktree exit with uncommitted changes is denied.
# ---------------------------------------------------------------------------
_scenario_6() {
  local n=6 name="M8 worktree exit with changes deny + override allow" t0 t1 elapsed
  _section "$n" "$name"
  t0=$(_now_ms)
  (
    set -u
    _scenario_sandbox_env "$n"
    _build_fixtures

    # The dirty fixture has uncommitted modifications + untracked files +
    # one unpushed commit. ExitWorktree-guard inspects the path passed in
    # tool_input.worktree_path, not $PWD — pass the fixture path directly.
    local repo="$REPOS_ROOT/dirty"
    _run_exit_worktree_hook "$SCRIPTS_DIR/worktree-exit-guard.sh" "$repo"
    _is_deny "$HOOK_STDOUT" \
      || { echo "S6 part-A: expected deny, got: $HOOK_STDOUT"; exit 1; }
    # Verify cascading denial. The dirty fixture's feat/dirty-tree has no
    # upstream tracking ref (never pushed), so the "unpushed" check returns
    # 0 — that branch of the cascade is silent. We assert the three checks
    # that DO fire on this fixture: modified, untracked, unmerged.
    for token in "modified" "untracked" "unmerged"; do
      _contains "$HOOK_STDOUT" "$token" \
        || { echo "S6 part-A: missing $token in deny: $HOOK_STDOUT"; exit 1; }
    done

    # Override consumes once → allow.
    export CLAUDE_ALLOW_WORKTREE_EXIT_WITH_CHANGES=1
    _run_exit_worktree_hook "$SCRIPTS_DIR/worktree-exit-guard.sh" "$repo"
    if _is_deny "$HOOK_STDOUT"; then
      echo "S6 part-B: override should ALLOW, got: $HOOK_STDOUT"; exit 1
    fi

    exit 0
  )
  local rc=$?
  t1=$(_now_ms); elapsed=$((t1 - t0))
  if [ "$rc" -eq 0 ]; then
    _emit_result "$n" "$name" PASS "$elapsed"
  else
    _emit_result "$n" "$name" FAIL "$elapsed" "" "subshell exit=$rc"
  fi
}

# ---------------------------------------------------------------------------
# Scenario 7: large repo (50 branches) — SessionStart brief stays under
#             the 300ms p99 budget. The fixture only has 50 branches, not
#             500 — but the hook's hot path is constant-time wrt branch
#             count (3 git calls + 1 TSV read). Validating ≤300ms here is
#             a realistic proxy for the SDD §Quality Requirements budget.
# ---------------------------------------------------------------------------
_scenario_7() {
  local n=7 name="SessionStart brief perf budget (≤300ms)" t0 t1 elapsed
  local budget=300
  _section "$n" "$name"
  t0=$(_now_ms)
  (
    set -u
    _scenario_sandbox_env "$n"
    _build_fixtures
    cd "$REPOS_ROOT/large-50-branches" || exit
    _run_session_start_hook "$SCRIPTS_DIR/session-start-brief.sh"
    [ "$HOOK_RC" -eq 0 ] \
      || { echo "S7: hook rc=$HOOK_RC stderr=$HOOK_STDERR"; exit 1; }
    # Brief writes JSON to stdout when there's something actionable (v2.2.2+).
    # The large-50-branches fixture has no .githooks/ → setup_seg fires, so
    # stdout must contain a non-empty JSON object with the tcs-git-helpers tag.
    _contains "$HOOK_STDOUT" "[tcs-git-helpers]" \
      || { echo "S7: brief missing tag in stdout: $HOOK_STDOUT"; exit 1; }
    exit 0
  )
  local rc=$?
  t1=$(_now_ms); elapsed=$((t1 - t0))
  if [ "$rc" -eq 0 ]; then
    _emit_result "$n" "$name" PASS "$elapsed" "$budget"
  else
    _emit_result "$n" "$name" FAIL "$elapsed" "$budget" "subshell exit=$rc"
  fi
}

# ---------------------------------------------------------------------------
# Scenario 8: rate-limited gh — fail-open ALLOW with stderr warning.
# ---------------------------------------------------------------------------
_scenario_8() {
  local n=8 name="gh rate-limited → fail-open allow + warn" t0 t1 elapsed
  _section "$n" "$name"
  t0=$(_now_ms)
  (
    set -u
    _scenario_sandbox_env "$n"
    _build_fixtures
    cd "$REPOS_ROOT/clean-unmerged" || exit
    export GH_STUB_SCENARIO=rate-limited

    _run_bash_hook "$SCRIPTS_DIR/block-bad-git-ops.sh" \
      "git push origin feat/clean-unmerged"
    if _is_deny "$HOOK_STDOUT"; then
      echo "S8: rate-limit should fail-OPEN, got deny: $HOOK_STDOUT"; exit 1
    fi
    # Warning to stderr is the contract (fail-open WITH visibility).
    _contains "$HOOK_STDERR" "fail-open" \
      || _contains "$HOOK_STDERR" "UNKNOWN" \
      || { echo "S8: missing fail-open warning, stderr=$HOOK_STDERR"; exit 1; }
    exit 0
  )
  local rc=$?
  t1=$(_now_ms); elapsed=$((t1 - t0))
  if [ "$rc" -eq 0 ]; then
    _emit_result "$n" "$name" PASS "$elapsed"
  else
    _emit_result "$n" "$name" FAIL "$elapsed" "" "subshell exit=$rc"
  fi
}

# ---------------------------------------------------------------------------
# Scenario 9: post-merge .githooks template runs the BATCHED gh call against
#             a stale-branches scenario — completes in well under the 10s
#             budget from research/performance.md §3.
# ---------------------------------------------------------------------------
_scenario_9() {
  local n=9 name="post-merge batched gh on stale repo (≤10s)" t0 t1 elapsed
  local budget=10000
  _section "$n" "$name"
  t0=$(_now_ms)
  (
    set -u
    _scenario_sandbox_env "$n"
    _build_fixtures

    # We need a fixture with the same branch names the gh stub returns as
    # merged. The stale-3-branches stub returns feat/stale-a, fix/stale-b,
    # chore/stale-c. Build a one-off repo that has those local branches.
    local repo="$WORK_ROOT/stale-batch"
    rm -rf "$repo"; mkdir -p "$repo"
    git -C "$repo" init -q -b main
    git -C "$repo" config user.name tcs-fixture
    git -C "$repo" config user.email fixture@tcs.invalid
    git -C "$repo" config commit.gpgsign false
    git -C "$repo" -c protocol.file.allow=always \
        commit --allow-empty -q -m "feat: init"
    for b in feat/stale-a fix/stale-b chore/stale-c; do
      git -C "$repo" branch "$b" main
    done
    # Install the post-merge hook AND its sibling lib-bundle.sh — since
    # v2.1.0, hooks source the bundle from the same .githooks/ dir, so this
    # one-off fixture must mirror that layout (otherwise the hook bails with
    # "lib-bundle.sh missing"). install_files.sh does this in real installs.
    mkdir -p "$repo/.githooks"
    cp "$TEMPLATES_DIR/githooks/post-merge" "$repo/.githooks/post-merge"
    cp "$TEMPLATES_DIR/githooks/lib-bundle.sh" "$repo/.githooks/lib-bundle.sh"
    chmod +x "$repo/.githooks/post-merge"

    cd "$repo" || exit
    export GH_STUB_SCENARIO=stale-3-branches

    # Drive the post-merge hook directly. Args are <prev-HEAD> <was-squash>
    # for git's contract (1 = was-squash); the hook ignores them in v1.
    out_f=$(mktemp "$WORK_ROOT/pm-out.XXXXXX")
    err_f=$(mktemp "$WORK_ROOT/pm-err.XXXXXX")
    bash "$repo/.githooks/post-merge" 0 0 >"$out_f" 2>"$err_f"
    rc=$?
    err=$(cat "$err_f")
    rm -f "$out_f" "$err_f"
    [ "$rc" -eq 0 ] || { echo "S9: post-merge rc=$rc err=$err"; exit 1; }
    # The hook prints suggestions to stderr. At minimum it should mention
    # one of the stale branch names from the gh stub.
    case "$err" in
      *stale-a*|*stale-b*|*stale-c*) : ;;
      *) echo "S9: post-merge stderr missing stale branch: $err"; exit 1 ;;
    esac
    exit 0
  )
  local rc=$?
  t1=$(_now_ms); elapsed=$((t1 - t0))
  if [ "$rc" -eq 0 ]; then
    _emit_result "$n" "$name" PASS "$elapsed" "$budget"
  else
    _emit_result "$n" "$name" FAIL "$elapsed" "$budget" "subshell exit=$rc"
  fi
}

# ---------------------------------------------------------------------------
# Scenario 10: bash 3.2 compatibility — static check.
#
# Per CON-1, every shell script we ship MUST run on macOS /bin/bash 3.2.57.
# Forbidden constructs:
#   - declare -A ........ associative arrays (bash 4)
#   - mapfile / readarray  (bash 4)
#   - ${var,,} / ${var^^}  (bash 4 case-conversion)
# We grep the entire scripts/ + templates/githooks/ + this script tree for
# any of those patterns. Any hit → FAIL.
# ---------------------------------------------------------------------------
_scenario_10() {
  local n=10 name="bash 3.2 compat — no bash-4 features" t0 t1 elapsed
  _section "$n" "$name"
  t0=$(_now_ms)
  (
    set -u
    # Forbidden constructs (POSIX ERE):
    #   declare -A          → associative array (bash 4)
    #   mapfile / readarray → bash 4 builtins
    #   ${var,,} / ${var^^} → bash 4 case-conversion
    # NOTE: we strip comments (anything from # onward) before matching so
    # documentation references like `# no declare -A` don't trip the check.
    # We also use `bash -n` as a sanity gate (bash 3.2 fails to parse the
    # `${var,,}` form at all — a pre-parse is the most reliable detector).
    pat='declare[[:space:]]+-A([^[:alnum:]_]|$)'
    pat="$pat|mapfile([^[:alnum:]_]|$)|readarray([^[:alnum:]_]|$)"
    pat="$pat"'|\$\{[A-Za-z_][A-Za-z0-9_]*,,'
    pat="$pat"'|\$\{[A-Za-z_][A-Za-z0-9_]*\^\^'

    targets=""
    # SCRIPT_DIR is intentionally excluded — this very file documents the
    # forbidden patterns to detect them, which would otherwise self-flag.
    for d in "$SCRIPTS_DIR" "$TEMPLATES_DIR/githooks"; do
      [ -d "$d" ] || continue
      while IFS= read -r f; do targets="$targets $f"; done <<EOF
$(find "$d" -type f \( -name '*.sh' -o -name 'pre-*' -o -name 'post-*' -o -name 'commit-*' \))
EOF
    done

    hits=""
    for f in $targets; do
      [ -f "$f" ] || continue
      # Strip comments before matching; awk preserves line numbers via NR.
      match=$(LC_ALL=C awk '
        {
          line = $0
          # Drop everything from the first unquoted # onward. Crude but
          # adequate for shell scripts whose # always opens a comment unless
          # it sits inside single/double quotes — and the patterns we hunt
          # do not appear inside such quotes in this codebase.
          n = index(line, "#")
          if (n > 0) line = substr(line, 1, n - 1)
          print NR ":" line
        }
      ' "$f" | LC_ALL=C grep -E "$pat" || true)
      if [ -n "$match" ]; then
        hits="$hits
$f:
$match"
      fi

      # Defense-in-depth: bash 3.2 will FAIL to parse a script that uses
      # `${var,,}` / `${var^^}` / `mapfile`-as-builtin. Run it through `bash
      # -n` to catch anything our regex missed.
      if ! /bin/bash -n "$f" 2>/dev/null; then
        # Only flag if the parse failure is on a hot path — re-run with
        # error output captured to differentiate.
        err=$(/bin/bash -n "$f" 2>&1 || true)
        case "$err" in
          *"bad substitution"*|*"unexpected"*"declare"*)
            hits="$hits
$f: bash -n parse error: $err"
            ;;
        esac
      fi
    done

    if [ -n "$hits" ]; then
      echo "S10: bash-4-only feature detected:$hits"
      exit 1
    fi
    exit 0
  )
  local rc=$?
  t1=$(_now_ms); elapsed=$((t1 - t0))
  if [ "$rc" -eq 0 ]; then
    _emit_result "$n" "$name" PASS "$elapsed"
  else
    _emit_result "$n" "$name" FAIL "$elapsed" "" "subshell exit=$rc"
  fi
}

# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------

_list() {
  cat <<'EOF'
S1   setup install copies templates + sets hooksPath
S2   M1 push-to-closed-PR deny + override once
S3   M2 branch-from-unfinished deny
S4   M3 squash-merged deny + merge-commit allow
S5   M7 destructive patterns x10 + override once
S6   M8 worktree exit with changes deny + override allow
S7   SessionStart brief perf budget (≤300ms)
S8   gh rate-limited → fail-open allow + warn
S9   post-merge batched gh on stale repo (≤10s)
S10  bash 3.2 compat — no bash-4 features
EOF
}

if [ "$LIST_ONLY" = "1" ]; then
  _list
  exit 0
fi

# Sanity: tooling.
for tool in jq git bash find grep mktemp; do
  command -v "$tool" >/dev/null 2>&1 \
    || { printf 'dogfood.sh: required tool missing: %s\n' "$tool" >&2; exit 1; }
done

_setup_path

# Build synthetic-repo fixtures ONCE in the parent shell before any scenario
# runs. Each scenario subshell sees REPOS_ROOT via env and skips the rebuild.
# build.sh is the canonical fixture builder (T1.9; produces 19 repos
# including large-50-branches and long-1000-commits — ~30s on M-series).
_build_fixtures
export REPOS_ROOT

printf '╭─ tcs-git-helpers e2e dogfood ─────────────────────╮\n'
printf '│ plugin_root  : %s\n' "$PLUGIN_ROOT"
printf '│ work_root    : %s\n' "$WORK_ROOT"
printf '│ bash_version : %s\n' "$BASH_VERSION"
printf '╰────────────────────────────────────────────────────╯\n'

_run_one() {
  case "$1" in
    1)  _scenario_1  ;;
    2)  _scenario_2  ;;
    3)  _scenario_3  ;;
    4)  _scenario_4  ;;
    5)  _scenario_5  ;;
    6)  _scenario_6  ;;
    7)  _scenario_7  ;;
    8)  _scenario_8  ;;
    9)  _scenario_9  ;;
    10) _scenario_10 ;;
    *)  printf 'dogfood.sh: unknown scenario: %s\n' "$1" >&2; return 1 ;;
  esac
}

if [ -n "$ONE_SCENARIO" ]; then
  _run_one "$ONE_SCENARIO" || true
else
  for i in 1 2 3 4 5 6 7 8 9 10; do
    _run_one "$i" || true
  done
fi

# ---------------------------------------------------------------------------
# Aggregate report
# ---------------------------------------------------------------------------

END_EPOCH_S=$(date +%s)
TOTAL_S=$((END_EPOCH_S - START_EPOCH_S))

printf '\n══ Summary ════════════════════════════════════════════\n'
printf '  scenarios run : %s\n' "$TOTAL_RUN"
printf '  pass          : %s\n' "$TOTAL_PASS"
printf '  fail          : %s\n' "$TOTAL_FAIL"
printf '  skip          : %s\n' "$TOTAL_SKIP"
printf '  elapsed       : %ss\n' "$TOTAL_S"

if [ -n "$PERF_VIOLATIONS" ]; then
  printf '\n  perf violations:\n'
  printf '%s' "$PERF_VIOLATIONS" | while IFS='|' read -r sn pname budget measured; do
    [ -z "$sn" ] && continue
    printf '    S%s "%s" — %sms > %sms budget\n' "$sn" "$pname" "$measured" "$budget"
  done
fi

printf '═══════════════════════════════════════════════════════\n'

if [ "$TOTAL_FAIL" -gt 0 ]; then
  exit 1
fi
exit 0
