#!/usr/bin/env bash
# test_batch_security.sh — T2.4 security guard for rule-enforcer batch mode (spec 016, Phase 2).
#
# Batch mode derives hook/CI/pre-push filenames from a SLUG computed from rule text, and in
# batch mode that rule text comes from SCANNED files — attacker-influenced if a malicious
# CLAUDE.md is scanned. Two protections must hold:
#   1. The slug-validation gate (SKILL.md Step 8) rejects any slug that is not
#      ^[a-z0-9][a-z0-9-]{0,62}$ — blocking path traversal via crafted rule descriptions.
#   2. The --from-file path confinement (SKILL.md Step 0 / B1) rejects ".." and absolute
#      paths outside the repo + the known ~/.claude set.
#
# This test (a) executably proves the slug gate and confinement logic reject attacker input,
# and (b) asserts via grep that SKILL.md actually INSTRUCTS these protections, so the
# executable behavior corresponds to documented, mandated behavior.
#
# bash 3.2 compatible (repo guardrail): no mapfile, no declare -A, no process substitution.

set -eu

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SKILL="$SCRIPT_DIR/SKILL.md"
# Repo root (four levels up: rule-enforcer/skills/tcs-helper/plugins/<root>).
REPO_ROOT="$(cd "$SCRIPT_DIR/../../../.." && pwd)"

pass=0
fail=0

check() {
  desc="$1"
  result="$2"
  if [ "$result" = "0" ]; then
    echo "PASS: $desc"
    pass=$((pass + 1))
  else
    echo "FAIL: $desc"
    fail=$((fail + 1))
  fi
}

# ---------------------------------------------------------------------------
# Part 1 — SLUG-GATE BEHAVIOR
# Encodes the canonical slug regex the skill mandates and proves it rejects
# path-traversal / malformed input while accepting well-formed slugs.
# ---------------------------------------------------------------------------
SLUG_RE='^[a-z0-9][a-z0-9-]{0,62}$'

# slug_ok <string> -> exit 0 if the string is an ACCEPTED slug, 1 if REJECTED.
# bash 3.2 supports =~; the regex is held in a variable (unquoted on the RHS)
# so the {0,62} bound is treated as an ERE quantifier, not a literal.
slug_ok() {
  s="$1"
  if [[ "$s" =~ $SLUG_RE ]]; then
    return 0
  fi
  return 1
}

assert_slug_reject() {
  if slug_ok "$1"; then
    check "slug REJECT: '$1'" 1
  else
    check "slug REJECT: '$1'" 0
  fi
}

assert_slug_accept() {
  if slug_ok "$1"; then
    check "slug ACCEPT: '$1'" 0
  else
    check "slug ACCEPT: '$1'" 1
  fi
}

# Build a 63-char (max valid) and 64-char (too long) all-lowercase string, bash 3.2 safe.
s63=""
i=0
while [ "$i" -lt 63 ]; do
  s63="${s63}a"
  i=$((i + 1))
done
s64="${s63}a"

echo "=== Part 1: slug-validation gate (regex $SLUG_RE) ==="
# REJECT — path traversal, path separators, dots, casing, leading hyphen, length, empty.
assert_slug_reject "../../etc/evil"
assert_slug_reject "../escape"
assert_slug_reject "/abs/path"
assert_slug_reject "foo/bar"
assert_slug_reject "foo.bar"
assert_slug_reject ".."
assert_slug_reject "Foo"
assert_slug_reject "-lead"
assert_slug_reject "$s64"
assert_slug_reject ""

# ACCEPT — well-formed kebab-case slugs.
assert_slug_accept "enforce-venv"
assert_slug_accept "no-break-system-packages"
assert_slug_accept "a"
assert_slug_accept "$s63"

# ---------------------------------------------------------------------------
# Part 2 — --from-file CONFINEMENT
# Reference implementation of the confinement rule (mirrors the SKILL.md
# Step 0 / B1 confinement rule): reject any path containing "..", reject
# absolute paths that are not under the repo root or ~/.claude; else accept.
# ---------------------------------------------------------------------------

# path_ok <path> -> exit 0 if ACCEPTED, 1 if REJECTED.
path_ok() {
  p="$1"
  # Reject any ".." component (path traversal).
  case "$p" in
    *..*) return 1 ;;
  esac
  # Absolute paths: allowed only under the repo root or the ~/.claude set.
  case "$p" in
    /*)
      case "$p" in
        "$REPO_ROOT"/*|"$HOME"/.claude/*) return 0 ;;
        *) return 1 ;;
      esac
      ;;
    # Relative path with no "..": accept.
    *) return 0 ;;
  esac
}

assert_path_reject() {
  if path_ok "$1"; then
    check "path REJECT: '$1'" 1
  else
    check "path REJECT: '$1'" 0
  fi
}

assert_path_accept() {
  if path_ok "$1"; then
    check "path ACCEPT: '$1'" 0
  else
    check "path ACCEPT: '$1'" 1
  fi
}

echo "=== Part 2: --from-file path confinement (mirrors SKILL.md Step 0 / B1) ==="
assert_path_reject "../outside"
assert_path_reject "/etc/passwd"
assert_path_reject "../../secret"
assert_path_accept "CLAUDE.md"
assert_path_accept "docs/ai/memory/general.md"

# ---------------------------------------------------------------------------
# Part 3 — DOC-CONTRACT assertions
# Confirm SKILL.md actually INSTRUCTS the protections proven above, so the
# executable checks correspond to documented, mandated behavior.
# ---------------------------------------------------------------------------
echo "=== Part 3: SKILL.md doc-contract ==="

if [ ! -f "$SKILL" ]; then
  check "SKILL.md exists" 1
else
  check "SKILL.md exists" 0

  # C1: slug regex documented (fixed-string match on the canonical regex).
  if grep -qF '^[a-z0-9][a-z0-9-]{0,62}$' "$SKILL"; then
    check "SKILL.md documents slug-validation regex ^[a-z0-9][a-z0-9-]{0,62}\$" 0
  else
    check "SKILL.md documents slug-validation regex ^[a-z0-9][a-z0-9-]{0,62}\$" 1
  fi

  # C2: --from-file / Step 0 confinement instructs rejecting "..".
  if grep -qF -- '--from-file' "$SKILL" && grep -qF 'reject `..`' "$SKILL"; then
    check "SKILL.md instructs --from-file path validation rejecting '..'" 0
  else
    check "SKILL.md instructs --from-file path validation rejecting '..'" 1
  fi

  # C3: personal ~/.claude content paraphrased / never pasted into artifacts.
  if grep -qF 'paraphrased' "$SKILL" && grep -qF 'never pasted' "$SKILL"; then
    check "SKILL.md instructs personal ~/.claude content is paraphrased, never pasted" 0
  else
    check "SKILL.md instructs personal ~/.claude content is paraphrased, never pasted" 1
  fi
fi

echo ""
echo "Results: $pass passed, $fail failed"
[ "$fail" -eq 0 ]
