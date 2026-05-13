#!/usr/bin/env bats
# Test suite: tcs-git-helpers-version source file
# Validates that the version file exists and meets the spec.
# See: docs/XDD/specs/012-tcs-git-helpers-hook-runtime-contract/solution.md#adr-2

setup() {
  PLUGIN_ROOT="$(cd "$(dirname "$BATS_TEST_FILENAME")/../.." && pwd)"
  VERSION_FILE="${PLUGIN_ROOT}/templates/githooks/tcs-git-helpers-version"
}

@test "tcs-git-helpers-version file exists" {
  [ -f "$VERSION_FILE" ]
}

@test "tcs-git-helpers-version contains a single non-empty trimmed line matching ^[a-z0-9-]+$" {
  local content trimmed_content
  content="$(cat "$VERSION_FILE")"
  trimmed_content="$(echo "$content" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')"

  # Ensure file has exactly one line (per SDD/ADR-2)
  [ "$(grep -c '' "$VERSION_FILE")" -eq 1 ]

  # Ensure it's not empty
  [ -n "$trimmed_content" ]

  # Ensure it matches the pattern
  [[ "$trimmed_content" =~ ^[a-z0-9-]+$ ]]
}
