#!/usr/bin/env bats
# tests/bats/lib_helpers.bats
# Coverage for the shared test helpers in lib/helpers.bash.
#
# These back assertions in every other suite, so a silent break here would
# weaken tests everywhere without failing anything visibly.

bats_require_minimum_version 1.5.0

load 'lib/helpers'

# -- _perf_budget -------------------------------------------------------------

@test "_perf_budget returns the raw budget when no slack is set" {
  run env -u TCS_PERF_SLACK bash -c "source '${BATS_TEST_DIRNAME}/lib/helpers.bash'; _perf_budget 150"
  [ "$status" -eq 0 ]
  [ "$output" = "150" ]
}

@test "_perf_budget multiplies by TCS_PERF_SLACK" {
  TCS_PERF_SLACK=4 run bash -c "source '${BATS_TEST_DIRNAME}/lib/helpers.bash'; TCS_PERF_SLACK=4 _perf_budget 150"
  [ "$status" -eq 0 ]
  [ "$output" = "600" ]
}

@test "_perf_budget ignores a non-numeric slack rather than erroring" {
  run bash -c "source '${BATS_TEST_DIRNAME}/lib/helpers.bash'; TCS_PERF_SLACK=lots _perf_budget 150"
  [ "$status" -eq 0 ]
  [ "$output" = "150" ]
}

@test "_perf_budget never tightens a budget below the specified value" {
  # A slack of 0 would turn every budget into an unsatisfiable 0ms.
  run bash -c "source '${BATS_TEST_DIRNAME}/lib/helpers.bash'; TCS_PERF_SLACK=0 _perf_budget 150"
  [ "$status" -eq 0 ]
  [ "$output" = "150" ]
}

@test "every perf assertion in the suite goes through _perf_budget" {
  # Guard the guard: a budget written as a bare literal escapes the slack
  # factor and will flake on a hosted runner (issue: macOS CI enablement).
  local bare
  bare="$(grep -rnE '\[ "\$(p99|elapsed|elapsed_ms|ceiling_ms)" -(lt|ge|gt) [0-9]+ \]' \
            "${BATS_TEST_DIRNAME}"/*.bats || true)"
  [ -z "$bare" ] || { printf 'budget not routed through _perf_budget:\n%s\n' "$bare" >&2; return 1; }
}

# -- _minimal_path ------------------------------------------------------------

@test "_minimal_path builds a PATH holding only the named tools" {
  local p
  p="$(_minimal_path bash)"
  [ -d "$p" ]
  [ -x "$p/bash" ]

  # The tool we did not ask for must be unreachable through it.
  run env -i PATH="$p" /bin/bash -c 'command -v git'
  [ "$status" -ne 0 ]
}
