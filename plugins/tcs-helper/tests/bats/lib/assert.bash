#!/usr/bin/env bash
#
# tests/bats/lib/assert.bash
#
# Substring assertions for the tcs-helper bats suites. Load with:
#
#   load 'lib/assert'
#
# Use these instead of a bare `[[ "$h" == *"x"* ]]` or `! cmd` anywhere but
# the last line of a test: under bash 3.2 a non-final `[[ ]]` does not trip
# errexit, and `! cmd` never does on any bash, so the test passes whatever the
# assertion says. tests/test_bats_blind_assertions.py rejects both forms.
# Args: haystack, needle (matched literally).

_has() {
  printf '%s' "$1" | grep -qF -- "$2" \
    || { printf 'expected [%s] in [%s]\n' "$2" "$1" >&2; return 1; }
}

_lacks() {
  if printf '%s' "$1" | grep -qF -- "$2"; then
    printf 'did not expect [%s] in [%s]\n' "$2" "$1" >&2
    return 1
  fi
}
