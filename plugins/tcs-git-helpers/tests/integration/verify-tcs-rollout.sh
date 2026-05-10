#!/usr/bin/env bash
# verify-tcs-rollout.sh — Integration acceptance harness for tcs-git-helpers rollout.
#
# Verifies that a target repo has the plugin correctly installed:
#   1. .githooks/pre-commit      exists, executable, v1.0.0 marker in lines 1-3
#   2. .githooks/pre-push        exists, executable, v1.0.0 marker in lines 1-3
#   3. .githooks/commit-msg      exists, executable, v1.0.0 marker in lines 1-3
#   4. .githooks/post-merge      exists, executable, v1.0.0 marker in lines 1-3
#   5. core.hooksPath == .githooks
#   6. Setup did NOT auto-stage any .githooks/* files
#   7. No conflicting hook tool artifacts present
#
# Usage:
#   verify-tcs-rollout.sh [--repo-path PATH]
#
# Args:
#   --repo-path PATH   Target repo root (default: $TCS_VERIFY_REPO or $PWD)
#
# Output:
#   -- Verifying tcs-git-helpers rollout in <repo-path> --
#   PASS: <check-name>
#   FAIL: <check-name> -- <reason>
#   Total: X/Y checks passed.
#
# Exit code: 0 if all checks pass, 1 if any fail.
#
# Reusable: T6.3, T6.4 — pass --repo-path to target another repo.
#
# Bash 3.2 compatible. shellcheck-clean.

set -euo pipefail

# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------
REPO_PATH="${TCS_VERIFY_REPO:-}"

while [ "$#" -gt 0 ]; do
  case "$1" in
    --repo-path)
      shift
      REPO_PATH="$1"
      ;;
    --repo-path=*)
      REPO_PATH="${1#--repo-path=}"
      ;;
    *)
      printf 'Usage: %s [--repo-path PATH]\n' "$0" >&2
      exit 2
      ;;
  esac
  shift
done

if [ -z "$REPO_PATH" ]; then
  REPO_PATH="$(pwd)"
fi

# ---------------------------------------------------------------------------
# Result tracking
# ---------------------------------------------------------------------------
PASS_COUNT=0
FAIL_COUNT=0
TOTAL=0

_pass() {
  PASS_COUNT=$((PASS_COUNT + 1))
  TOTAL=$((TOTAL + 1))
  printf 'PASS: %s\n' "$1"
}

_fail() {
  FAIL_COUNT=$((FAIL_COUNT + 1))
  TOTAL=$((TOTAL + 1))
  printf 'FAIL: %s -- %s\n' "$1" "$2"
}

# ---------------------------------------------------------------------------
# Check: hook file has v1.0.0 marker in lines 1-3
# ---------------------------------------------------------------------------
_assert_hook_marker() {
  local name="$1"
  local hook_file="$REPO_PATH/.githooks/$name"

  if [ ! -f "$hook_file" ]; then
    _fail "marker_${name}" ".githooks/$name does not exist"
    return 1
  fi

  if [ ! -x "$hook_file" ]; then
    _fail "marker_${name}" ".githooks/$name exists but is not executable"
    return 1
  fi

  # Check lines 1-3 for marker (bash 3.2: use head + grep, no mapfile)
  local marker_line
  marker_line="$(head -3 "$hook_file" | grep -E '^#[[:space:]]*tcs-git-helpers:[[:space:]]*v1\.0\.0' || true)"

  if [ -z "$marker_line" ]; then
    _fail "marker_${name}" ".githooks/$name has no '# tcs-git-helpers: v1.0.0' marker in lines 1-3"
    return 1
  fi

  _pass "marker_${name}"
  return 0
}

# ---------------------------------------------------------------------------
# Checks
# ---------------------------------------------------------------------------

assert_marker_pre_commit() {
  _assert_hook_marker "pre-commit"
}

assert_marker_pre_push() {
  _assert_hook_marker "pre-push"
}

assert_marker_commit_msg() {
  _assert_hook_marker "commit-msg"
}

assert_marker_post_merge() {
  _assert_hook_marker "post-merge"
}

assert_hookspath_set() {
  local name="hookspath_set"
  local actual
  actual="$(git -C "$REPO_PATH" config --get core.hooksPath 2>/dev/null || true)"

  if [ "$actual" = ".githooks" ]; then
    _pass "$name"
  else
    _fail "$name" "core.hooksPath is '${actual:-<unset>}', expected '.githooks'"
  fi
}

assert_no_auto_commit() {
  local name="no_auto_stage"
  local staged
  staged="$(git -C "$REPO_PATH" diff --cached --name-only 2>/dev/null | grep '^\.githooks/' || true)"

  if [ -z "$staged" ]; then
    _pass "$name"
  else
    _fail "$name" "Setup auto-staged .githooks/* files: $staged"
  fi
}

assert_no_conflicts() {
  local name="no_conflicts"
  local found=""

  if [ -d "$REPO_PATH/.husky" ]; then
    found="$found .husky/"
  fi

  for f in lefthook.yml lefthook.yaml .lefthook.yml .pre-commit-config.yaml; do
    if [ -f "$REPO_PATH/$f" ]; then
      found="$found $f"
    fi
  done

  if [ -f "$REPO_PATH/package.json" ]; then
    if grep -qE '"husky"[[:space:]]*:' "$REPO_PATH/package.json" 2>/dev/null; then
      found="$found package.json(husky)"
    fi
    if grep -qE '"simple-git-hooks"[[:space:]]*:' "$REPO_PATH/package.json" 2>/dev/null; then
      found="$found package.json(simple-git-hooks)"
    fi
  fi

  if [ -z "$found" ]; then
    _pass "$name"
  else
    _fail "$name" "Conflicting hook tool artifacts found:$found"
  fi
}

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
printf '%s\n' "── Verifying tcs-git-helpers rollout in $REPO_PATH ──"

assert_marker_pre_commit  || true
assert_marker_pre_push    || true
assert_marker_commit_msg  || true
assert_marker_post_merge  || true
assert_hookspath_set      || true
assert_no_auto_commit     || true
assert_no_conflicts       || true

printf 'Total: %d/%d checks passed.\n' "$PASS_COUNT" "$TOTAL"

if [ "$FAIL_COUNT" -gt 0 ]; then
  exit 1
fi
exit 0
