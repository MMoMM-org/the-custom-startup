#!/usr/bin/env bats
# Tests for scripts/session-start-brief.sh.
#
# v2.2.2 rewrite: the brief is no longer a plain-text line. SessionStart
# stdout goes only to Claude's context, so the script now emits a JSON
# hook response with two channels:
#   - systemMessage          : user-visible TUI notice
#   - hookSpecificOutput.additionalContext : Claude-only context
# When nothing is actionable, the script exits 0 silently (no stdout).
#
# Coverage:
#   1.  Silent on idle (feat branch, hooks current, no stale)
#   2.  Silent on idle when cache file missing
#   3.  Main branch idle → additionalContext nudge only, no systemMessage
#   4.  Drift hint → both channels carry the suggestion
#   5.  Setup hint when .githooks/ absent → both channels
#   6.  Cleanup hint when stale-count > 0 → both channels
#   7.  Main + cleanup → systemMessage has hint, additionalContext has hint + nudge
#   8.  JSON output parses cleanly
#   9.  No gh invocations (sentinel stub)
#  10.  Performance p99 < 300ms (500ms on CI) over 100 invocations
#
# Constraints:
#   - bash 3.2 compatible (no declare -A, no mapfile)
#   - POSIX ERE patterns only
#   - No jq dependency

bats_require_minimum_version 1.5.0

load 'lib/helpers'

# ----------------------------------------------------------------------
# Setup / teardown
# ----------------------------------------------------------------------

setup() {
  TESTS_DIR="$(cd "$(dirname "$BATS_TEST_FILENAME")" && pwd)"
  PLUGIN_ROOT="$(cd "$TESTS_DIR/../.." && pwd)"
  HOOK="$PLUGIN_ROOT/scripts/session-start-brief.sh"

  # Sandbox plugin data so cache writes don't affect the user's real data.
  CLAUDE_PLUGIN_DATA="$(mktemp -d "${TMPDIR:-/tmp}/tcs-ssb.XXXXXX")"
  export CLAUDE_PLUGIN_DATA

  CACHE_DIR="$CLAUDE_PLUGIN_DATA/cache"
  mkdir -p "$CACHE_DIR"

  # Build a synthetic fixture repo for this test (fresh per test).
  TEST_REPO="$(mktemp -d "${TMPDIR:-/tmp}/tcs-ssb-repo.XXXXXX")"
  export TEST_REPO

  # Deterministic git identity.
  export GIT_AUTHOR_NAME="bats"
  export GIT_AUTHOR_EMAIL="b@a.ts"
  export GIT_COMMITTER_NAME="bats"
  export GIT_COMMITTER_EMAIL="b@a.ts"
  export GIT_CONFIG_GLOBAL=/dev/null
  export GIT_CONFIG_SYSTEM=/dev/null

  # Build a base repo with an origin so ahead/behind tracking works.
  ORIGIN="$(mktemp -d "${TMPDIR:-/tmp}/tcs-ssb-origin.XXXXXX")"
  export ORIGIN
  git -C "$ORIGIN" init -q --bare 2>/dev/null \
    || { git -C "$ORIGIN" init --bare >/dev/null 2>&1; }
  git -C "$ORIGIN" symbolic-ref HEAD refs/heads/main 2>/dev/null || true

  git -C "$TEST_REPO" init -q 2>/dev/null || git -C "$TEST_REPO" init >/dev/null 2>&1
  git -C "$TEST_REPO" config commit.gpgsign false
  git -C "$TEST_REPO" config tag.gpgsign false
  git -C "$TEST_REPO" config user.name "bats"
  git -C "$TEST_REPO" config user.email "b@a.ts"

  printf 'init\n' > "$TEST_REPO/init.txt"
  git -C "$TEST_REPO" add init.txt
  git -C "$TEST_REPO" commit -q -m "feat: init"
  git -C "$TEST_REPO" checkout -B main >/dev/null 2>&1 || true
  git -C "$TEST_REPO" remote add origin "$ORIGIN"
  git -C "$TEST_REPO" push -q -u origin main 2>/dev/null \
    || git -C "$TEST_REPO" push -q -u origin HEAD:main 2>/dev/null || true
  git -C "$TEST_REPO" symbolic-ref refs/remotes/origin/HEAD refs/remotes/origin/main 2>/dev/null || true

  # Create and switch to feat branch — most tests run from a feature branch.
  git -C "$TEST_REPO" checkout -q -b feat/foo 2>/dev/null || true
  git -C "$TEST_REPO" push -q -u origin feat/foo 2>/dev/null || true

  # Repo hash matches lib/cache.sh _repo_hash exactly (printf '%s' on the
  # real-path show-toplevel, no trailing newline).
  _real_top="$(git -C "$TEST_REPO" rev-parse --show-toplevel 2>/dev/null)"
  REPO_HASH="$(printf '%s' "$_real_top" | shasum 2>/dev/null | head -c 12)"
  export REPO_HASH
  export CACHE_DIR
}

teardown() {
  if [ -n "${TEST_REPO:-}" ] && [ -d "$TEST_REPO" ]; then
    chmod -R u+w "$TEST_REPO" 2>/dev/null || true
    rm -rf "$TEST_REPO"
  fi
  if [ -n "${ORIGIN:-}" ] && [ -d "$ORIGIN" ]; then
    rm -rf "$ORIGIN"
  fi
  if [ -n "${CLAUDE_PLUGIN_DATA:-}" ] && [ -d "$CLAUDE_PLUGIN_DATA" ]; then
    rm -rf "$CLAUDE_PLUGIN_DATA"
  fi
}

# Write a stale-cache TSV file. Args: $1=updated_iso, $2+=rows.
_write_test_cache() {
  local updated_iso="$1"
  shift
  local tsv_path="$CACHE_DIR/${REPO_HASH}-stale-cache.tsv"
  {
    printf '# tcs-git-helpers stale cache v1\n'
    printf '# updated_iso=%s\n' "$updated_iso"
    printf '# repo_path=%s\n' "$TEST_REPO"
    printf '# default_branch=main\n'
    for row in "$@"; do
      printf '%s\n' "$row"
    done
  } > "$tsv_path"
}

# Install fake .githooks/ with hooks bannered at a given version. The
# drift-check in section 8b of session-start-brief.sh reads the first
# tcs-git-helpers banner line out of pre-commit / pre-push / commit-msg /
# post-merge, so we only need to write those files with the banner.
_install_githooks_at() {
  local v="$1"
  mkdir -p "$TEST_REPO/.githooks"
  local h
  for h in pre-commit pre-push commit-msg post-merge; do
    {
      printf '#!/bin/bash\n'
      printf '# tcs-git-helpers: %s\n' "$v"
      printf 'exit 0\n'
    } > "$TEST_REPO/.githooks/$h"
    chmod +x "$TEST_REPO/.githooks/$h"
  done
}

# Install .githooks/ at the plugin.json current version → silences drift_seg.
_install_githooks_current() {
  local v
  v="$(grep -E '"version"[[:space:]]*:' "$PLUGIN_ROOT/.claude-plugin/plugin.json" \
       | head -1 \
       | sed -E 's/.*"version"[[:space:]]*:[[:space:]]*"([^"]+)".*/\1/')"
  _install_githooks_at "$v"
}

# Run the hook in the test repo dir.
_run_hook() {
  run --separate-stderr bash -c 'cd "$1" && exec "$2"' _ "$TEST_REPO" "$HOOK"
}

# ----------------------------------------------------------------------
# Test 1: Silent on idle (feat branch, hooks current, no stale)
# ----------------------------------------------------------------------

@test "silent on idle: feat branch + current githooks + no stale" {
  _install_githooks_current
  local now_iso
  now_iso="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  _write_test_cache "$now_iso"  # empty cache, no stale rows

  _run_hook

  [ "$status" -eq 0 ]
  [ -z "$output" ]
  [ -z "$stderr" ]
}

# ----------------------------------------------------------------------
# Test 2: Silent on idle when cache file is missing entirely
# ----------------------------------------------------------------------

@test "silent on idle: cache file absent, fail-open" {
  _install_githooks_current
  local tsv_path="$CACHE_DIR/${REPO_HASH}-stale-cache.tsv"
  [ ! -f "$tsv_path" ]

  _run_hook

  [ "$status" -eq 0 ]
  [ -z "$output" ]
  [ -z "$stderr" ]
}

# ----------------------------------------------------------------------
# Test 3: Main branch idle — additionalContext nudge only, no systemMessage
# ----------------------------------------------------------------------

@test "main branch idle: additionalContext has nudge, no systemMessage" {
  git -C "$TEST_REPO" checkout -q main 2>/dev/null || true
  _install_githooks_current
  local now_iso
  now_iso="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  _write_test_cache "$now_iso"

  _run_hook

  [ "$status" -eq 0 ]
  [ -n "$output" ]
  # No systemMessage field present → user sees nothing.
  _ssb_lacks "$output" '"systemMessage"'
  # additionalContext present and contains the protected-branch nudge.
  printf '%s' "$output" | grep -q '"additionalContext"'
  printf '%s' "$output" | grep -q "protected branch"
  printf '%s' "$output" | grep -q "do not create or edit"
  printf '%s' "$output" | grep -q "main"
}

# ----------------------------------------------------------------------
# Test 4: Drift hint surfaces in both channels
# ----------------------------------------------------------------------

@test "drift hint surfaces in systemMessage and additionalContext" {
  _install_githooks_at "2.0.0"   # forces drift vs current plugin.json
  local now_iso
  now_iso="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  _write_test_cache "$now_iso"

  _run_hook

  [ "$status" -eq 0 ]
  [ -n "$output" ]
  printf '%s' "$output" | grep -q '"systemMessage"'
  printf '%s' "$output" | grep -q '"additionalContext"'
  printf '%s' "$output" | grep -q "hooks v2.0.0"
  printf '%s' "$output" | grep -q "run /tcs-git-helpers:git-setup --update"
}

# ----------------------------------------------------------------------
# Test 5: Setup hint surfaces when .githooks/ absent
# ----------------------------------------------------------------------

@test "setup hint surfaces when .githooks/ absent" {
  [ ! -d "$TEST_REPO/.githooks" ]
  local now_iso
  now_iso="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  _write_test_cache "$now_iso"

  _run_hook

  [ "$status" -eq 0 ]
  [ -n "$output" ]
  printf '%s' "$output" | grep -q '"systemMessage"'
  printf '%s' "$output" | grep -q "run /tcs-git-helpers:git-setup"
}

# ----------------------------------------------------------------------
# Test 6: Cleanup hint surfaces when stale-count > 0
# ----------------------------------------------------------------------

@test "cleanup hint surfaces when stale-count > 0" {
  _install_githooks_current
  local now_iso
  now_iso="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  _write_test_cache "$now_iso" \
    "feat/old-thing	38	2026-04-12T10:00:00Z" \
    "fix/another-thing	40	2026-04-15T09:00:00Z"

  _run_hook

  [ "$status" -eq 0 ]
  [ -n "$output" ]
  printf '%s' "$output" | grep -q '"systemMessage"'
  printf '%s' "$output" | grep -q "run /tcs-git-helpers:git-audit --cleanup"
}

# ----------------------------------------------------------------------
# Test 7: Main + cleanup — systemMessage has hint, additionalContext has hint + nudge
# ----------------------------------------------------------------------

@test "main + cleanup: systemMessage has hint, additionalContext has hint + nudge" {
  git -C "$TEST_REPO" checkout -q main 2>/dev/null || true
  _install_githooks_current
  local now_iso
  now_iso="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  _write_test_cache "$now_iso" \
    "feat/old-thing	38	2026-04-12T10:00:00Z"

  _run_hook

  [ "$status" -eq 0 ]
  printf '%s' "$output" | grep -q '"systemMessage"'
  printf '%s' "$output" | grep -q '"additionalContext"'
  # Cleanup hint must appear in both fields (count the occurrences ≥ 2).
  local count
  count="$(printf '%s' "$output" | grep -o "run /tcs-git-helpers:git-audit --cleanup" | wc -l | tr -d '[:space:]')"
  [ "$count" -ge 2 ]
  # Nudge appears only in additionalContext, so just count ≥ 1.
  printf '%s' "$output" | grep -q "protected branch"
}

# ----------------------------------------------------------------------
# Test 8: JSON output parses cleanly
# ----------------------------------------------------------------------

@test "JSON output is syntactically valid when emitted" {
  _install_githooks_at "2.0.0"   # ensure something is emitted
  local now_iso
  now_iso="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  _write_test_cache "$now_iso"

  _run_hook

  [ "$status" -eq 0 ]
  [ -n "$output" ]
  # Validate via python3 if present, else jq, else skip.
  if command -v python3 >/dev/null 2>&1; then
    printf '%s' "$output" | python3 -c 'import json,sys;json.loads(sys.stdin.read())'
  elif command -v jq >/dev/null 2>&1; then
    printf '%s' "$output" | jq -e . >/dev/null
  else
    skip "Neither python3 nor jq available to validate JSON"
  fi
}

# ----------------------------------------------------------------------
# Test 9: No gh invocations (sentinel stub)
# ----------------------------------------------------------------------

@test "hook makes NO gh invocations (sentinel stub exits 99)" {
  local stub_dir
  stub_dir="$(mktemp -d "${TMPDIR:-/tmp}/tcs-ssb-ghstub.XXXXXX")"
  local sentinel="$stub_dir/gh-invoked"

  cat > "$stub_dir/gh" << 'STUB'
#!/bin/bash
# Sentinel: record invocation and exit 99 (hook must never call us).
printf 'gh-stub-sentinel invoked with: %s\n' "$*" >&2
touch "${GH_SENTINEL_FILE}"
exit 99
STUB
  chmod +x "$stub_dir/gh"

  local now_iso
  now_iso="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  _write_test_cache "$now_iso"

  run --separate-stderr bash -c \
    'export PATH="$1:$PATH"; export GH_SENTINEL_FILE="$2"; cd "$3" && exec "$4"' \
    _ "$stub_dir" "$sentinel" "$TEST_REPO" "$HOOK"

  [ "$status" -eq 0 ]
  [ ! -f "$sentinel" ]

  rm -rf "$stub_dir"
}

# ----------------------------------------------------------------------
# Test 10: Performance p99 under 300ms (500ms on CI)
# ----------------------------------------------------------------------

@test "performance p99 under 300ms (100 invocations)" {
  _install_githooks_current
  local now_iso
  now_iso="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  _write_test_cache "$now_iso" \
    "feat/old-thing	38	2026-04-12T10:00:00Z" \
    "fix/another-thing	40	2026-04-15T09:00:00Z"

  local ceiling_ms
  if [ "${CI:-}" = "true" ]; then
    ceiling_ms=$(_perf_budget 500)
  else
    ceiling_ms=$(_perf_budget 300)
  fi

  local n=100
  local tmp_times
  tmp_times="$(mktemp "${TMPDIR:-/tmp}/tcs-ssb-perf.XXXXXX")"

  local ms_cmd=""
  if command -v gdate >/dev/null 2>&1; then
    ms_cmd="gdate +%s%3N"
  elif command -v perl >/dev/null 2>&1; then
    ms_cmd="perl -MTime::HiRes=time -e 'printf \"%d\n\", time()*1000'"
  fi

  if [ -z "$ms_cmd" ]; then
    rm -f "$tmp_times"
    skip "Millisecond timing not available (no gdate, no perl)"
  fi

  local i t0 t1 elapsed_ms
  for i in $(seq 1 $n); do
    t0="$(eval "$ms_cmd" 2>/dev/null || echo 0)"
    bash -c 'cd "$1" && exec "$2"' _ "$TEST_REPO" "$HOOK" >/dev/null 2>&1
    t1="$(eval "$ms_cmd" 2>/dev/null || echo 0)"
    elapsed_ms="$((t1 - t0))"
    printf '%s\n' "$elapsed_ms" >> "$tmp_times"
  done

  local p99
  p99="$(sort -n "$tmp_times" | awk 'NR==99{print; exit}')"
  rm -f "$tmp_times"

  case "${p99:-}" in
    ''|*[!0-9]*) skip "Could not parse timing data; skipping perf assertion" ;;
  esac

  if [ "$p99" -ge "$ceiling_ms" ]; then
    printf 'FAIL: p99=%dms exceeds ceiling=%dms\n' "$p99" "$ceiling_ms" >&2
    return 1
  fi
}

# ======================================================================
# spec-020 T4.3 — the tcs-patterns drift advisory segment (section 8c).
#
# Each test builds a fixture plugin tree under $BATS_TEST_TMPDIR holding a
# COPY of the real session-start-brief.sh (plus lib/ and ../.claude-plugin/,
# which it reads relative to its own directory) and a STUB patterns_drift.py
# that prints canned lines and records that it ran. Two layouts:
#   repo:  <fx>/plugins/{tcs-git-helpers,tcs-patterns}/scripts/
#   cache: <fx>/cache/mkt/tcs-git-helpers/2.2.22/scripts/
#          <fx>/cache/mkt/tcs-patterns/<v>/scripts/
# Substring asserts go through _ssb_has/_ssb_lacks (grep -qF; args: haystack,
# needle), never a bare non-final [[ ]] or `! cmd` (which bats does not fail on).
# ======================================================================

_ssb_has() {
  printf '%s' "$1" | grep -qF -- "$2" \
    || { printf 'expected [%s] in [%s]\n' "$2" "$1" >&2; return 1; }
}

_ssb_lacks() {
  if printf '%s' "$1" | grep -qF -- "$2"; then
    printf 'did not expect [%s] in [%s]\n' "$2" "$1" >&2
    return 1
  fi
}

# The systemMessage of the hook's JSON output, decoded (empty when absent).
_ssb_sysmsg() {
  printf '%s' "$output" | python3 -c \
    'import json,sys;t=sys.stdin.read().strip();sys.stdout.write(json.loads(t).get("systemMessage","") if t else "")'
}

# The hookSpecificOutput.additionalContext (the model's context), decoded
# (empty when absent). Review M2: pattern segments must never reach it.
_ssb_ctx() {
  printf '%s' "$output" | python3 -c \
    'import json,sys;t=sys.stdin.read().strip();sys.stdout.write(json.loads(t).get("hookSpecificOutput",{}).get("additionalContext","") if t else "")'
}

# Copy the real hook into a tcs-git-helpers plugin root at $1; sets FX_HOOK.
_fx_git_helpers_at() {
  local root="$1"
  mkdir -p "$root/scripts" "$root/.claude-plugin"
  cp "$PLUGIN_ROOT/scripts/session-start-brief.sh" "$root/scripts/"
  cp -R "$PLUGIN_ROOT/scripts/lib" "$root/scripts/lib"
  cp "$PLUGIN_ROOT/.claude-plugin/plugin.json" "$root/.claude-plugin/"
  FX_HOOK="$root/scripts/session-start-brief.sh"
}

# Write a stub reporter into tcs-patterns plugin root $1 that prints the
# remaining args as lines. It writes its argv to scripts/ran when executed,
# and exits with the code in scripts/exit_code if that file exists.
_fx_patterns_stub_at() {
  local root="$1"
  shift
  mkdir -p "$root/scripts"
  cat > "$root/scripts/patterns_drift.py" << 'PY'
import pathlib, sys
here = pathlib.Path(__file__).resolve().parent
(here / "ran").write_text(" ".join(sys.argv[1:]))
canned = here / "canned.txt"
if canned.exists():
    sys.stdout.write(canned.read_text())
code = here / "exit_code"
sys.exit(int(code.read_text()) if code.exists() else 0)
PY
  : > "$root/scripts/canned.txt"
  local line
  for line in "$@"; do
    printf '%s\n' "$line" >> "$root/scripts/canned.txt"
  done
}

# Repo layout: hook at <fx>/plugins/tcs-git-helpers, stub at
# <fx>/plugins/tcs-patterns printing "$@". Sets FX_HOOK and FX_PATTERNS.
_fx_repo_layout() {
  local fx="$BATS_TEST_TMPDIR/fx"
  _fx_git_helpers_at "$fx/plugins/tcs-git-helpers"
  FX_PATTERNS="$fx/plugins/tcs-patterns"
  _fx_patterns_stub_at "$FX_PATTERNS" "$@"
}

# Cache layout: hook at <fx>/cache/mkt/tcs-git-helpers/2.2.22. Sets FX_HOOK
# and FX_CACHE_PATTERNS (the tcs-patterns/ directory holding version dirs).
_fx_cache_layout() {
  local fx="$BATS_TEST_TMPDIR/fx"
  _fx_git_helpers_at "$fx/cache/mkt/tcs-git-helpers/2.2.22"
  FX_CACHE_PATTERNS="$fx/cache/mkt/tcs-patterns"
  mkdir -p "$FX_CACHE_PATTERNS"
}

# Any manifest file: the stub ignores its content.
_fx_manifest() {
  mkdir -p "$TEST_REPO/.claude/skills"
  printf 'bundle = "2.0.0"\n' > "$TEST_REPO/.claude/skills/.tcs-patterns-manifest"
}

_run_fx_hook() {
  run --separate-stderr bash -c 'cd "$1" && exec "$2"' _ "$TEST_REPO" "$FX_HOOK"
}

@test "patterns advisory: drifted patterns named with both versions and the update command" {
  _install_githooks_current
  _fx_manifest
  _fx_repo_layout "DRIFT:ddd:3:4" "DRIFT:hexagonal:2:5"

  _run_fx_hook

  [ "$status" -eq 0 ]
  [ -z "$stderr" ]
  local msg
  msg="$(_ssb_sysmsg)"
  [ "$msg" = "[tcs-git-helpers] patterns ddd v3 → v4, hexagonal v2 → v5; run /tcs-patterns:patterns-setup update" ]
  # The reporter is handed the repository's top level.
  [ "$(cat "$FX_PATTERNS/scripts/ran")" = "$(git -C "$TEST_REPO" rev-parse --show-toplevel)" ]
}

@test "patterns advisory: reporter says OK → no segment, silent overall" {
  _install_githooks_current
  _fx_manifest
  _fx_repo_layout "OK"

  _run_fx_hook

  [ "$status" -eq 0 ]
  [ -f "$FX_PATTERNS/scripts/ran" ]
  [ -z "$output" ]
  [ -z "$stderr" ]
}

@test "patterns advisory: no manifest → reporter never runs, no segment" {
  _install_githooks_current
  _fx_repo_layout "DRIFT:ddd:3:4"

  _run_fx_hook

  [ "$status" -eq 0 ]
  [ ! -e "$FX_PATTERNS/scripts/ran" ]
  [ -z "$output" ]
  [ -z "$stderr" ]
}

@test "patterns advisory: MISSING alone is suppressed" {
  _install_githooks_current
  _fx_manifest
  _fx_repo_layout "MISSING"

  _run_fx_hook

  [ "$status" -eq 0 ]
  [ -f "$FX_PATTERNS/scripts/ran" ]
  [ -z "$output" ]
  [ -z "$stderr" ]
}

@test "patterns advisory: UNKNOWN alone names the pattern and the status command" {
  _install_githooks_current
  _fx_manifest
  _fx_repo_layout "UNKNOWN:ddd:3" "UNKNOWN:hexagonal:1"

  _run_fx_hook

  [ "$status" -eq 0 ]
  [ -z "$stderr" ]
  local msg
  msg="$(_ssb_sysmsg)"
  [ "$msg" = "[tcs-git-helpers] patterns ddd v3, hexagonal v1 not in the catalogue; run /tcs-patterns:patterns-setup status" ]
}

@test "patterns advisory: DRIFT and UNKNOWN share one systemMessage, drift first" {
  _install_githooks_current
  _fx_manifest
  # The reporter sorts by pattern name, so UNKNOWN can precede DRIFT in its output.
  _fx_repo_layout "UNKNOWN:hexagonal:3" "DRIFT:ddd:1:2"

  _run_fx_hook

  [ "$status" -eq 0 ]
  [ -z "$stderr" ]
  local msg
  msg="$(_ssb_sysmsg)"
  [ "$msg" = "[tcs-git-helpers] patterns ddd v1 → v2; run /tcs-patterns:patterns-setup update • patterns hexagonal v3 not in the catalogue; run /tcs-patterns:patterns-setup status" ]
}

@test "patterns advisory: malformed lines are dropped under a UTF-8 locale; only the valid one surfaces" {
  _install_githooks_current
  _fx_manifest
  # Under a UTF-8 locale bash 3.2's [!a-z0-9-] admits uppercase, so Ddd
  # passes unless the parser pins LC_ALL=C.
  _fx_repo_layout "DRIFT:Ddd:1:2" "DRIFT:ddd:x:2" "DRIFT:ddd:1:2:extra" \
    "UNKNOWN:ddd" "UNKNOWN:ddd:1:2" "UNKNOWN:Ddd:1" "UNKNOWN:ddd:1:" "DRIFT:ddd:1:2:" \
    "MISSING" "OK" "" \
    "DRIFT:hexagonal:1:2"

  run --separate-stderr env LC_ALL=en_US.UTF-8 bash -c 'cd "$1" && exec "$2"' _ "$TEST_REPO" "$FX_HOOK"

  [ "$status" -eq 0 ]
  [ -z "$stderr" ]
  local msg
  msg="$(_ssb_sysmsg)"
  [ "$msg" = "[tcs-git-helpers] patterns hexagonal v1 → v2; run /tcs-patterns:patterns-setup update" ]
}

@test "patterns advisory: tcs-patterns absent → no segment, no error" {
  _install_githooks_current
  _fx_manifest
  _fx_git_helpers_at "$BATS_TEST_TMPDIR/fx/plugins/tcs-git-helpers"

  _run_fx_hook

  [ "$status" -eq 0 ]
  [ -z "$output" ]
  [ -z "$stderr" ]
}

@test "patterns advisory: tcs-patterns at 1.x in the cache (no reporter) → no segment, no error" {
  _install_githooks_current
  _fx_manifest
  _fx_cache_layout
  mkdir -p "$FX_CACHE_PATTERNS/1.4.4/scripts" "$FX_CACHE_PATTERNS/1.4.4/skills"
  printf '#!/bin/bash\n' > "$FX_CACHE_PATTERNS/1.4.4/scripts/block-eslint-disable.sh"

  _run_fx_hook

  [ "$status" -eq 0 ]
  [ -z "$output" ]
  [ -z "$stderr" ]
}

@test "patterns advisory: cache layout, 2.10.0 beats 2.0.0" {
  _install_githooks_current
  _fx_manifest
  _fx_cache_layout
  _fx_patterns_stub_at "$FX_CACHE_PATTERNS/2.0.0" "DRIFT:ddd:1:2"
  _fx_patterns_stub_at "$FX_CACHE_PATTERNS/2.10.0" "DRIFT:ddd:1:10"

  _run_fx_hook

  [ "$status" -eq 0 ]
  [ -z "$stderr" ]
  [ "$(_ssb_sysmsg)" = "[tcs-git-helpers] patterns ddd v1 → v10; run /tcs-patterns:patterns-setup update" ]
}

@test "patterns advisory: cache layout, 2.10.0 beats 2.9.0 (numeric, not lexical)" {
  _install_githooks_current
  _fx_manifest
  _fx_cache_layout
  _fx_patterns_stub_at "$FX_CACHE_PATTERNS/2.9.0" "DRIFT:ddd:1:9"
  _fx_patterns_stub_at "$FX_CACHE_PATTERNS/2.10.0" "DRIFT:ddd:1:10"

  _run_fx_hook

  [ "$status" -eq 0 ]
  [ -z "$stderr" ]
  [ "$(_ssb_sysmsg)" = "[tcs-git-helpers] patterns ddd v1 → v10; run /tcs-patterns:patterns-setup update" ]
  [ ! -e "$FX_CACHE_PATTERNS/2.9.0/scripts/ran" ]
}

@test "patterns advisory: repo layout wins over a cached tcs-patterns when both exist" {
  _install_githooks_current
  _fx_manifest
  # One tree satisfies both lookups relative to the hook at
  # <fx>/plugins/tcs-git-helpers/scripts: ../../tcs-patterns (repo) and
  # ../../../tcs-patterns/<ver> (cache).
  _fx_repo_layout "DRIFT:ddd:1:2"
  local cache_stub="$BATS_TEST_TMPDIR/fx/tcs-patterns/9.9.9"
  _fx_patterns_stub_at "$cache_stub" "DRIFT:hexagonal:7:8"

  _run_fx_hook

  [ "$status" -eq 0 ]
  [ -z "$stderr" ]
  [ "$(_ssb_sysmsg)" = "[tcs-git-helpers] patterns ddd v1 → v2; run /tcs-patterns:patterns-setup update" ]
  [ -e "$FX_PATTERNS/scripts/ran" ]
  [ ! -e "$cache_stub/scripts/ran" ]
}

@test "patterns advisory: hooks drift and patterns drift share one systemMessage" {
  _install_githooks_at "2.0.0"
  _fx_manifest
  _fx_repo_layout "DRIFT:ddd:3:4"

  _run_fx_hook

  [ "$status" -eq 0 ]
  [ -z "$stderr" ]
  local msg
  msg="$(_ssb_sysmsg)"
  _ssb_has "$msg" "hooks v2.0.0 → v"
  _ssb_has "$msg" "run /tcs-git-helpers:git-setup --update"
  _ssb_has "$msg" "patterns ddd v3 → v4; run /tcs-patterns:patterns-setup update"
  # Review M2: hook drift keeps reaching the model; pattern drift does not.
  local ctx
  ctx="$(_ssb_ctx)"
  _ssb_has "$ctx" "hooks v2.0.0 → v"
  _ssb_has "$ctx" "run /tcs-git-helpers:git-setup --update"
  _ssb_lacks "$ctx" "patterns"
  _ssb_lacks "$ctx" "ddd"
}

# Review M2: a pattern name comes from repository content (the manifest), so
# the patterns segment is shown to the user (systemMessage) and never put in
# the model's context (additionalContext).
@test "patterns advisory: pattern drift alone goes to systemMessage only, never additionalContext" {
  _install_githooks_current
  _fx_manifest
  _fx_repo_layout "DRIFT:testing:0:1"

  _run_fx_hook

  [ "$status" -eq 0 ]
  [ -z "$stderr" ]
  [ "$(_ssb_sysmsg)" = "[tcs-git-helpers] patterns testing v0 → v1; run /tcs-patterns:patterns-setup update" ]
  [ -z "$(_ssb_ctx)" ]
}

@test "patterns advisory: on main the model gets the branch nudge but not the pattern drift" {
  _install_githooks_current
  _fx_manifest
  _fx_repo_layout "DRIFT:testing:0:1"
  git -C "$TEST_REPO" checkout -q main

  _run_fx_hook

  [ "$status" -eq 0 ]
  [ "$(_ssb_sysmsg)" = "[tcs-git-helpers] patterns testing v0 → v1; run /tcs-patterns:patterns-setup update" ]
  [ "$(_ssb_ctx)" = "[tcs-git-helpers] On protected branch 'main': do not create or edit non-gitignored files here. Switch to a feature branch before any Write/Edit." ]
}

@test "patterns advisory: a 64-character pattern name is kept, a 65-character one dropped" {
  _install_githooks_current
  _fx_manifest
  local n64=aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
  local n65=bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb
  [ "${#n64}" -eq 64 ]
  [ "${#n65}" -eq 65 ]
  _fx_repo_layout "DRIFT:${n64}:1:2" "DRIFT:${n65}:1:2" "UNKNOWN:${n65}:1"

  _run_fx_hook

  [ "$status" -eq 0 ]
  [ -z "$stderr" ]
  [ "$(_ssb_sysmsg)" = "[tcs-git-helpers] patterns ${n64} v1 → v2; run /tcs-patterns:patterns-setup update" ]
}

# Review L6: on Python < 3.11 the reporter prints UNSUPPORTED:python instead of
# failing on `import tomllib`; the brief turns it into a hint, user-only.
@test "patterns advisory: UNSUPPORTED:python becomes a user-only hint" {
  _install_githooks_current
  _fx_manifest
  _fx_repo_layout "UNSUPPORTED:python"

  _run_fx_hook

  [ "$status" -eq 0 ]
  [ -z "$stderr" ]
  [ "$(_ssb_sysmsg)" = "[tcs-git-helpers] patterns advisory needs python ≥ 3.11" ]
  [ -z "$(_ssb_ctx)" ]
}

# Review M4: the reporter runs isolated (python3 -I): no user site, no
# PYTHON* environment, no script directory on sys.path.
@test "patterns advisory: the reporter runs under python3 -I" {
  _install_githooks_current
  _fx_manifest
  _fx_repo_layout "DRIFT:ddd:1:2"
  cat > "$FX_PATTERNS/scripts/patterns_drift.py" << 'PY'
import pathlib, sys
here = pathlib.Path(__file__).resolve().parent
(here / "isolated").write_text(str(sys.flags.isolated))
print("DRIFT:ddd:1:2")
PY

  _run_fx_hook

  [ "$status" -eq 0 ]
  [ "$(cat "$FX_PATTERNS/scripts/isolated")" = "1" ]
}

@test "patterns advisory: reporter exits non-zero → no segment" {
  _install_githooks_current
  _fx_manifest
  _fx_repo_layout "DRIFT:ddd:3:4"
  printf '3' > "$FX_PATTERNS/scripts/exit_code"

  _run_fx_hook

  [ "$status" -eq 0 ]
  [ -f "$FX_PATTERNS/scripts/ran" ]
  [ -z "$output" ]
  [ -z "$stderr" ]
}

@test "patterns advisory: python3 absent from PATH → no segment, no error" {
  _install_githooks_current
  _fx_manifest
  _fx_repo_layout "DRIFT:ddd:3:4"

  # A PATH holding everything in /usr/bin and /bin except python3*, plus git.
  local nopy="$BATS_TEST_TMPDIR/nopy" f
  mkdir -p "$nopy"
  for f in /usr/bin/* /bin/*; do
    case "${f##*/}" in python3*) continue ;; esac
    [ -e "$nopy/${f##*/}" ] || ln -s "$f" "$nopy/${f##*/}"
  done
  [ -e "$nopy/git" ] || ln -s "$(command -v git)" "$nopy/git"
  run env PATH="$nopy" /bin/bash -c 'command -v python3'
  [ "$status" -ne 0 ]

  run --separate-stderr env PATH="$nopy" /bin/bash -c 'cd "$1" && exec "$2"' _ "$TEST_REPO" "$FX_HOOK"

  [ "$status" -eq 0 ]
  [ ! -e "$FX_PATTERNS/scripts/ran" ]
  [ -z "$output" ]
  [ -z "$stderr" ]
}

@test "patterns advisory end-to-end: the real reporter names a lowered pattern version" {
  _install_githooks_current
  local cat_v
  cat_v="$(cat "$PLUGIN_ROOT/../tcs-patterns/templates/patterns/ddd/VERSION")"
  local low=$((cat_v - 1))
  mkdir -p "$TEST_REPO/.claude/skills"
  {
    printf '# Written by /tcs-patterns:patterns-setup. Reviewed and committed like any other file.\n'
    printf 'bundle = "2.0.0"\n'
    printf '\n[patterns.ddd]\n'
    printf 'version = "%s"\n' "$low"
    printf 'installed_as = "tcs-ddd"\n'
    printf 'sha256 = "%s"\n' "0000000000000000000000000000000000000000000000000000000000000000"
  } > "$TEST_REPO/.claude/skills/.tcs-patterns-manifest"

  _run_hook

  [ "$status" -eq 0 ]
  [ -z "$stderr" ]
  [ "$(_ssb_sysmsg)" = "[tcs-git-helpers] patterns ddd v${low} → v${cat_v}; run /tcs-patterns:patterns-setup update" ]
  [ -z "$(_ssb_ctx)" ]
}

# spec-020 T4.4 — the two-way property that makes the grain worth its cost.
# One pattern's catalogue change advises in a repository that installed it AND
# stays silent in one that did not. Both halves in ONE run: "advises" alone is
# satisfied by a reporter that lists the whole catalogue, "silent" alone by one
# that never reports. Real hook, real reporter, real installer; only the
# catalogue is a fixture (two patterns).
_fx_install_patterns() {
  # args: repo catalogue pattern...
  local repo="$1" cat="$2"
  shift 2
  python3 -I -c '
import sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
import install
install.install(Path(sys.argv[2]), sys.argv[4:], catalogue_dir=Path(sys.argv[3]), bundle="2.0.0")
' "$PLUGIN_ROOT/../tcs-patterns/skills/patterns-setup/lib" "$repo" "$cat" "$@"
}

@test "patterns advisory two-way: one pattern change advises where installed and only there" {
  _install_githooks_current

  # Real tcs-patterns reporter + lib next to the real hook (repo layout), with
  # a two-pattern fixture catalogue where the reporter's default points.
  local fx="$BATS_TEST_TMPDIR/fx" src="$PLUGIN_ROOT/../tcs-patterns"
  _fx_git_helpers_at "$fx/plugins/tcs-git-helpers"
  mkdir -p "$fx/plugins/tcs-patterns/scripts" "$fx/plugins/tcs-patterns/skills/patterns-setup"
  cp "$src/scripts/patterns_drift.py" "$fx/plugins/tcs-patterns/scripts/"
  cp -R "$src/skills/patterns-setup/lib" "$fx/plugins/tcs-patterns/skills/patterns-setup/lib"
  rm -rf "$fx/plugins/tcs-patterns/skills/patterns-setup/lib/__pycache__"
  local catalogue="$fx/plugins/tcs-patterns/templates/patterns" p
  for p in ddd hexagonal; do
    mkdir -p "$catalogue/$p"
    printf '1\n' > "$catalogue/$p/VERSION"
    printf -- '---\nname: %s\ndescription: "fixture"\n---\n\nbody\n' "$p" > "$catalogue/$p/SKILL.md"
  done

  # A installs ddd only; B (a copy of the same fixture repo) installs hexagonal only.
  local repo_a="$TEST_REPO" repo_b="$BATS_TEST_TMPDIR/repo-b"
  cp -R "$repo_a" "$repo_b"
  _fx_install_patterns "$repo_a" "$catalogue" ddd
  _fx_install_patterns "$repo_b" "$catalogue" hexagonal

  # Both start current: silent.
  _run_fx_hook
  [ "$status" -eq 0 ]
  [ -z "$output" ]
  TEST_REPO="$repo_b"
  _run_fx_hook
  [ "$status" -eq 0 ]
  [ -z "$output" ]

  # One change: ddd's catalogue VERSION only.
  printf '2\n' > "$catalogue/ddd/VERSION"

  # Half 1: A, which installed ddd, is advised.
  TEST_REPO="$repo_a"
  _run_fx_hook
  [ "$status" -eq 0 ]
  local msg_a
  msg_a="$(_ssb_sysmsg)"
  _ssb_has "$msg_a" "patterns ddd v1 → v2"
  _ssb_has "$msg_a" "run /tcs-patterns:patterns-setup update"

  # Half 2 (same run): B, which never installed ddd, hears nothing about patterns.
  TEST_REPO="$repo_b"
  _run_fx_hook
  [ "$status" -eq 0 ]
  local msg_b
  msg_b="$(_ssb_sysmsg)"
  _ssb_lacks "$msg_b" "patterns"
  _ssb_lacks "$msg_b" "ddd"
  [ -z "$output" ]
}
