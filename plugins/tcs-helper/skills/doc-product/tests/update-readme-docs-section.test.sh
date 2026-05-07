#!/usr/bin/env bash
# update-readme-docs-section.test.sh — pressure tests for
# scripts/update-readme-docs-section.sh
# Bash 3.2 compatible; macOS awk compatible.

# shellcheck disable=SC2030,SC2031,SC2329
set -euo pipefail

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_ROOT="$(dirname "$SCRIPT_DIR")"
UPDATE_SH="${SKILL_ROOT}/scripts/update-readme-docs-section.sh"
FIX_DIR="${SCRIPT_DIR}/fixtures/readme-update"
SAMPLE_DOCS="${FIX_DIR}/sample-docs"

if [ ! -x "$UPDATE_SH" ]; then
  printf 'FATAL: %s not found or not executable\n' "$UPDATE_SH" >&2
  exit 1
fi

# ---------------------------------------------------------------------------
# Sandbox-safe tempdir
# ---------------------------------------------------------------------------
_make_tmpdir() {
  local base="/tmp/claude-501"
  if [ ! -d "$base" ]; then
    base="${TMPDIR:-/tmp}"
  fi
  local d="${base}/update-readme-$$-${RANDOM}"
  mkdir -p "$d"
  printf '%s\n' "$d"
}

# ---------------------------------------------------------------------------
# Test harness
# ---------------------------------------------------------------------------
PASS_COUNT=0
FAIL_COUNT=0

pass() { PASS_COUNT=$((PASS_COUNT + 1)); printf 'PASS  %s\n' "$1"; }
fail() { FAIL_COUNT=$((FAIL_COUNT + 1)); printf 'FAIL  %s — %s\n' "$1" "$2"; }

assert_contains() {
  local label="$1" needle="$2" haystack="$3"
  if printf '%s\n' "$haystack" | grep -qF "$needle"; then
    pass "$label"
  else
    fail "$label" "expected to contain: $needle"
  fi
}

assert_not_contains() {
  local label="$1" needle="$2" haystack="$3"
  if printf '%s\n' "$haystack" | grep -qF "$needle"; then
    fail "$label" "should NOT contain: $needle"
  else
    pass "$label"
  fi
}

assert_eq() {
  local label="$1" expected="$2" actual="$3"
  if [ "$expected" = "$actual" ]; then
    pass "$label"
  else
    fail "$label" "expected=$(printf '%q' "$expected") got=$(printf '%q' "$actual")"
  fi
}

_run() {
  # Run the script with given fixture README; echo final README content
  local readme="$1"
  bash "$UPDATE_SH" --readme "$readme" --docs-dir "$SAMPLE_DOCS"
  cat "$readme"
}

# ---------------------------------------------------------------------------
# S1: with-license-no-section → INSERT before ## License
# ---------------------------------------------------------------------------
scenario_1() {
  printf '\n--- S1: README with ## License but no Documentation section → INSERT ---\n'
  local tmp readme out
  tmp="$(_make_tmpdir)"
  readme="${tmp}/README.md"
  cp "${FIX_DIR}/with-license-no-section.md" "$readme"

  out="$(bash "$UPDATE_SH" --readme "$readme" --docs-dir "$SAMPLE_DOCS" 2>&1)"
  assert_contains "S1: action prints INSERT" "INSERT (before ## License)" "$out"

  local readme_content
  readme_content="$(cat "$readme")"
  assert_contains "S1: start marker present" "<!-- doc-product:documentation:start -->" "$readme_content"
  assert_contains "S1: end marker present"   "<!-- doc-product:documentation:end -->"   "$readme_content"
  assert_contains "S1: ## Documentation heading present" "## Documentation" "$readme_content"
  assert_contains "S1: installation page link" "[Installation](docs/installation.md)" "$readme_content"
  assert_contains "S1: configuration page link" "[Configuration](docs/configuration.md)" "$readme_content"
  assert_contains "S1: troubleshooting page link" "[Troubleshooting](docs/troubleshooting.md)" "$readme_content"
  assert_contains "S1: extra page link present (non-canonical)" "[Extra Topic](docs/topic-extra.md)" "$readme_content"
  assert_contains "S1: blockquote summary captured" "Install the foo widget on your machine." "$readme_content"
  assert_not_contains "S1: docs/README.md excluded" "[Documentation](docs/README.md)" "$readme_content"
  assert_not_contains "S1: docs/CLAUDE.md excluded" "docs/CLAUDE.md" "$readme_content"
  assert_contains "S1: ## License preserved after section" "## License" "$readme_content"

  rm -rf "$tmp"
}

# ---------------------------------------------------------------------------
# S2: with-license-marked-section → UPDATE (replace block content)
# ---------------------------------------------------------------------------
scenario_2() {
  printf '\n--- S2: README with marker block → UPDATE in place ---\n'
  local tmp readme out
  tmp="$(_make_tmpdir)"
  readme="${tmp}/README.md"
  cp "${FIX_DIR}/with-license-marked-section.md" "$readme"

  out="$(bash "$UPDATE_SH" --readme "$readme" --docs-dir "$SAMPLE_DOCS" 2>&1)"
  assert_contains "S2: action prints UPDATE" "UPDATE" "$out"

  local readme_content
  readme_content="$(cat "$readme")"
  assert_not_contains "S2: stale link removed" "[Stale Page](docs/stale.md)" "$readme_content"
  assert_contains "S2: fresh installation link present" "[Installation](docs/installation.md)" "$readme_content"

  rm -rf "$tmp"
}

# ---------------------------------------------------------------------------
# S3: with-license-unmarked-section → WARN, leave alone
# ---------------------------------------------------------------------------
scenario_3() {
  printf '\n--- S3: README with hand-written ## Documentation (no markers) → WARN, no clobber ---\n'
  local tmp readme out before after
  tmp="$(_make_tmpdir)"
  readme="${tmp}/README.md"
  cp "${FIX_DIR}/with-license-unmarked-section.md" "$readme"
  before="$(cat "$readme")"

  out="$(bash "$UPDATE_SH" --readme "$readme" --docs-dir "$SAMPLE_DOCS" 2>&1 || true)"
  after="$(cat "$readme")"

  assert_contains "S3: warning printed" "WARNING" "$out"
  assert_contains "S3: warning mentions markers" "doc-product:documentation:start" "$out"
  assert_eq "S3: README byte-for-byte unchanged" "$before" "$after"

  rm -rf "$tmp"
}

# ---------------------------------------------------------------------------
# S4: no-license → APPEND at end
# ---------------------------------------------------------------------------
scenario_4() {
  printf '\n--- S4: README with no ## License → APPEND at end ---\n'
  local tmp readme out
  tmp="$(_make_tmpdir)"
  readme="${tmp}/README.md"
  cp "${FIX_DIR}/no-license.md" "$readme"

  out="$(bash "$UPDATE_SH" --readme "$readme" --docs-dir "$SAMPLE_DOCS" 2>&1)"
  assert_contains "S4: action prints APPEND" "APPEND" "$out"

  local readme_content last_line
  readme_content="$(cat "$readme")"
  assert_contains "S4: end marker present" "<!-- doc-product:documentation:end -->" "$readme_content"

  # The last non-empty line should be the end marker (i.e., section is at EOF, not before any later content)
  last_line="$(awk '/./ { l = $0 } END { print l }' "$readme")"
  assert_eq "S4: end marker is last non-empty line" "<!-- doc-product:documentation:end -->" "$last_line"

  rm -rf "$tmp"
}

# ---------------------------------------------------------------------------
# S5: README missing entirely → notice, exit 0, no file created
# ---------------------------------------------------------------------------
scenario_5() {
  printf '\n--- S5: README missing → notice, no creation ---\n'
  local tmp readme out exit_code
  tmp="$(_make_tmpdir)"
  readme="${tmp}/missing-readme.md"

  exit_code=0
  out="$(bash "$UPDATE_SH" --readme "$readme" --docs-dir "$SAMPLE_DOCS" 2>&1)" || exit_code=$?

  assert_eq "S5: exit code is 0" "0" "$exit_code"
  assert_contains "S5: notice mentions skip" "skipping Documentation-section update" "$out"

  if [ -f "$readme" ]; then
    fail "S5: script must NOT create the README" "file exists at $readme"
  else
    pass "S5: script did NOT create a README"
  fi

  rm -rf "$tmp"
}

# ---------------------------------------------------------------------------
# S6: docs/ directory missing → notice, exit 0, README untouched
# ---------------------------------------------------------------------------
scenario_6() {
  printf '\n--- S6: docs/ directory missing → notice, no mutation ---\n'
  local tmp readme out exit_code before after
  tmp="$(_make_tmpdir)"
  readme="${tmp}/README.md"
  cp "${FIX_DIR}/with-license-no-section.md" "$readme"
  before="$(cat "$readme")"

  exit_code=0
  out="$(bash "$UPDATE_SH" --readme "$readme" --docs-dir "${tmp}/nonexistent-docs" 2>&1)" || exit_code=$?
  after="$(cat "$readme")"

  assert_eq "S6: exit code is 0" "0" "$exit_code"
  assert_contains "S6: notice mentions docs/ missing" "docs/ directory not found" "$out"
  assert_eq "S6: README unchanged when docs/ missing" "$before" "$after"

  rm -rf "$tmp"
}

# ---------------------------------------------------------------------------
# S7: idempotency — INSERT then UPDATE produces same content
# ---------------------------------------------------------------------------
scenario_7() {
  printf '\n--- S7: idempotent — second run is a no-op for content ---\n'
  local tmp readme content_after_first content_after_second
  tmp="$(_make_tmpdir)"
  readme="${tmp}/README.md"
  cp "${FIX_DIR}/with-license-no-section.md" "$readme"

  bash "$UPDATE_SH" --readme "$readme" --docs-dir "$SAMPLE_DOCS" >/dev/null 2>&1
  content_after_first="$(cat "$readme")"

  bash "$UPDATE_SH" --readme "$readme" --docs-dir "$SAMPLE_DOCS" >/dev/null 2>&1
  content_after_second="$(cat "$readme")"

  assert_eq "S7: README content stable across two runs" \
    "$content_after_first" "$content_after_second"

  rm -rf "$tmp"
}

# ---------------------------------------------------------------------------
# S8: page ordering — canonical pages first, alpha for non-canonical
# ---------------------------------------------------------------------------
scenario_8() {
  printf '\n--- S8: canonical-then-alpha ordering ---\n'
  local tmp readme readme_content order
  tmp="$(_make_tmpdir)"
  readme="${tmp}/README.md"
  cp "${FIX_DIR}/with-license-no-section.md" "$readme"

  bash "$UPDATE_SH" --readme "$readme" --docs-dir "$SAMPLE_DOCS" >/dev/null 2>&1
  readme_content="$(cat "$readme")"

  # Extract just the order of bullets (page basenames) inside the marker block
  order="$(awk '
    /<!-- doc-product:documentation:start -->/ { in_block = 1; next }
    /<!-- doc-product:documentation:end -->/ { in_block = 0 }
    in_block && /^- \[/ { print }
  ' "$readme")"

  # Canonical fixture pages: installation, configuration, troubleshooting (no setup/usage in fixture)
  # Non-canonical: topic-extra
  # Expected order: installation, configuration, troubleshooting, topic-extra (alpha within non-canonical)
  local expected
  expected="- [Installation](docs/installation.md) — Install the foo widget on your machine.
- [Configuration](docs/configuration.md) — Settings reference.
- [Troubleshooting](docs/troubleshooting.md)
- [Extra Topic](docs/topic-extra.md) — Non-canonical page that should sort alphabetically after the canonical pages."

  assert_eq "S8: bullet order matches canonical-then-alpha rule" "$expected" "$order"

  rm -rf "$tmp"
}

# ---------------------------------------------------------------------------
# S9: dry-run does NOT write to disk
# ---------------------------------------------------------------------------
scenario_9() {
  printf '\n--- S9: --dry-run prints proposal, leaves README untouched ---\n'
  local tmp readme out before after
  tmp="$(_make_tmpdir)"
  readme="${tmp}/README.md"
  cp "${FIX_DIR}/with-license-no-section.md" "$readme"
  before="$(cat "$readme")"

  out="$(bash "$UPDATE_SH" --readme "$readme" --docs-dir "$SAMPLE_DOCS" --dry-run 2>&1)"
  after="$(cat "$readme")"

  assert_eq "S9: README unchanged after --dry-run" "$before" "$after"
  assert_contains "S9: dry-run output contains marker" "<!-- doc-product:documentation:start -->" "$out"

  rm -rf "$tmp"
}

# ---------------------------------------------------------------------------
# S10: bad argument → exit 1
# ---------------------------------------------------------------------------
scenario_10() {
  printf '\n--- S10: unknown argument → exit 1 ---\n'
  local out exit_code
  exit_code=0
  out="$(bash "$UPDATE_SH" --bogus 2>&1)" || exit_code=$?

  if [ "$exit_code" -ne 0 ]; then
    pass "S10: exit code is non-zero"
  else
    fail "S10: exit code is non-zero" "got 0"
  fi
  assert_contains "S10: stderr mentions unknown argument" "unknown argument" "$out"
}

# ---------------------------------------------------------------------------
# Run all
# ---------------------------------------------------------------------------
scenario_1
scenario_2
scenario_3
scenario_4
scenario_5
scenario_6
scenario_7
scenario_8
scenario_9
scenario_10

printf '\n========================================\n'
printf 'Results: %d passed, %d failed\n' "$PASS_COUNT" "$FAIL_COUNT"
printf '========================================\n'

if [ "$FAIL_COUNT" -gt 0 ]; then
  exit "$FAIL_COUNT"
fi
exit 0
