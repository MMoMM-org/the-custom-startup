#!/usr/bin/env bats
#
# tests/bats/lib_version.bats
#
# Tests for scripts/lib/version.sh — _version_newer, the ordering both
# drift reporters use to tell "hooks older" from "plugin older" (#221).

bats_require_minimum_version 1.5.0

setup() {
  TESTS_DIR="$(cd "$(dirname "$BATS_TEST_FILENAME")" && pwd)"
  # shellcheck disable=SC1091
  . "$TESTS_DIR/../../scripts/lib/version.sh"
}

@test "V1 a higher patch is newer" {
  run _version_newer 2.2.39 2.2.21
  [ "$status" -eq 0 ]
}

@test "V2 a lower patch is not newer" {
  run _version_newer 2.2.21 2.2.39
  [ "$status" -eq 1 ]
}

@test "V3 equal versions are not newer" {
  run _version_newer 2.2.39 2.2.39
  [ "$status" -eq 1 ]
}

@test "V4 components compare numerically, not lexically" {
  run _version_newer 2.10.0 2.9.9
  [ "$status" -eq 0 ]
  run _version_newer 2.9.9 2.10.0
  [ "$status" -eq 1 ]
}

@test "V5 a leading v is ignored on either side" {
  run _version_newer v3.0.0 2.9.9
  [ "$status" -eq 0 ]
  run _version_newer 3.0.0 v2.9.9
  [ "$status" -eq 0 ]
}

@test "V6 missing trailing components count as zero" {
  run _version_newer 2.2 2.2.0
  [ "$status" -eq 1 ]
  run _version_newer 2.2.1 2.2
  [ "$status" -eq 0 ]
}

@test "V7 a non-numeric version is never newer" {
  run _version_newer 9.0.0-rc1 2.0.0
  [ "$status" -eq 1 ]
  run _version_newer 9.0.0 ""
  [ "$status" -eq 1 ]
  run _version_newer 9..0 2.0.0
  [ "$status" -eq 1 ]
}

@test "V8 a leading zero is not read as octal" {
  run _version_newer 2.08.0 2.7.0
  [ "$status" -eq 0 ]
}
