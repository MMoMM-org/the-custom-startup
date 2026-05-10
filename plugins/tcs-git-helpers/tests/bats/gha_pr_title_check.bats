#!/usr/bin/env bats
#
# tests/bats/gha_pr_title_check.bats
#
# Coverage for templates/github-actions/pr-title-check.yml
#
# Spec references:
#   - PRD §Feature S2 — GHA opt-in PR title check
#   - SDD §GitHub Actions Templates
#
# Lightweight checks only:
#   - File exists
#   - YAML parses (via python3 + PyYAML)
#   - on: trigger includes pull_request with at least opened/edited types
#   - Embedded regex matches the same Conventional Commits contract as commit-msg
#
# Full GHA testing happens in Phase 6 via a real PR.
#
# Constraints:
#   - bash 3.2 compatible
#   - mktemp form: "${TMPDIR:-/tmp}/...XXXXXX"
#   - bats `! cmd` trap: use `run` + status checks, NOT bare `! cmd`

bats_require_minimum_version 1.5.0

# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------

setup_file() {
  TESTS_DIR="$(cd "$(dirname "$BATS_TEST_FILENAME")" && pwd)"
  PLUGIN_ROOT="$(cd "$TESTS_DIR/../.." && pwd)"
  export TESTS_DIR PLUGIN_ROOT

  YAML="$PLUGIN_ROOT/templates/github-actions/pr-title-check.yml"
  export YAML
}

# Extract the regex literal from the YAML.
# The YAML is expected to define a line like:
#   regex='^(feat|fix|...)(\([a-z0-9._-]+\))?!?: .+'
# We grep for that single-quoted assignment and strip the quotes.
extract_regex() {
  # POSIX-friendly: single-quoted regex= assignment, take RHS, strip leading/trailing single quotes.
  grep -E "^[[:space:]]*regex='[^']+'" "$YAML" | head -n 1 | sed -E "s/^[[:space:]]*regex='([^']+)'.*$/\1/"
}

# ---------------------------------------------------------------------------
# File / YAML structural checks
# ---------------------------------------------------------------------------

@test "pr-title-check.yml: file exists at templates/github-actions/" {
  [ -f "$YAML" ]
}

@test "pr-title-check.yml: header has tcs-git-helpers version marker" {
  run grep -E '^# tcs-git-helpers: v[0-9]+\.[0-9]+\.[0-9]+' "$YAML"
  [ "$status" -eq 0 ]
}

@test "pr-title-check.yml: parses as valid YAML" {
  run python3 -c "import sys, yaml; yaml.safe_load(open('$YAML'))"
  [ "$status" -eq 0 ]
}

@test "pr-title-check.yml: top-level name is set" {
  run python3 -c "
import yaml
d = yaml.safe_load(open('$YAML'))
assert 'name' in d, 'missing name'
assert isinstance(d['name'], str) and d['name'], 'empty name'
"
  [ "$status" -eq 0 ]
}

# ---------------------------------------------------------------------------
# Trigger checks: pull_request event with title-edit-relevant types
# ---------------------------------------------------------------------------

@test "pr-title-check.yml: triggers on pull_request event" {
  # In YAML, `on:` becomes the boolean True key when parsed by PyYAML
  # (because "on" is a YAML 1.1 boolean). Look up by both keys.
  run python3 -c "
import yaml
d = yaml.safe_load(open('$YAML'))
on = d.get('on', d.get(True))
assert on is not None, 'missing on:'
assert 'pull_request' in on, 'pull_request not in on:'
"
  [ "$status" -eq 0 ]
}

@test "pr-title-check.yml: pull_request types include opened and edited" {
  run python3 -c "
import yaml
d = yaml.safe_load(open('$YAML'))
on = d.get('on', d.get(True))
pr = on['pull_request']
types = pr.get('types', [])
for t in ('opened', 'edited'):
    assert t in types, f'missing type: {t} (got: {types})'
"
  [ "$status" -eq 0 ]
}

@test "pr-title-check.yml: defines a job that runs on ubuntu-latest" {
  run python3 -c "
import yaml
d = yaml.safe_load(open('$YAML'))
jobs = d.get('jobs', {})
assert jobs, 'no jobs defined'
runners = [j.get('runs-on') for j in jobs.values()]
assert 'ubuntu-latest' in runners, f'no ubuntu-latest job (got: {runners})'
"
  [ "$status" -eq 0 ]
}

@test "pr-title-check.yml: no third-party uses: actions (S2 self-contained)" {
  # Allow `uses: actions/checkout@...` if added; deny anything not in actions/* org.
  # Current design: NO uses: at all.
  run python3 -c "
import yaml
d = yaml.safe_load(open('$YAML'))
bad = []
for jname, job in d.get('jobs', {}).items():
    for step in job.get('steps', []):
        u = step.get('uses')
        if u and not u.startswith('actions/'):
            bad.append(u)
assert not bad, f'third-party actions used: {bad}'
"
  [ "$status" -eq 0 ]
}

# ---------------------------------------------------------------------------
# Regex extraction + parity with commit-msg hook
# ---------------------------------------------------------------------------

@test "pr-title-check.yml: regex literal is extractable from YAML" {
  re="$(extract_regex)"
  [ -n "$re" ]
}

@test "pr-title-check.yml: regex includes all 11 default types" {
  re="$(extract_regex)"
  for t in feat fix docs style refactor test chore perf revert build ci; do
    case "$re" in
      *"$t"*) ;;
      *) printf 'missing type: %s\n' "$t" >&2; return 1 ;;
    esac
  done
}

@test "pr-title-check.yml: regex uses scope char class [a-z0-9._-]+" {
  re="$(extract_regex)"
  case "$re" in
    *'[a-z0-9._-]+'*) ;;
    *) printf 'scope char class missing or wrong: %s\n' "$re" >&2; return 1 ;;
  esac
}

# ---------------------------------------------------------------------------
# Regex behavior — valid PR titles MUST match
# ---------------------------------------------------------------------------

@test "regex: matches 'feat: add foo'" {
  re="$(extract_regex)"
  title='feat: add foo'
  [[ "$title" =~ $re ]]
}

@test "regex: matches 'fix(scope): bar'" {
  re="$(extract_regex)"
  title='fix(scope): bar'
  [[ "$title" =~ $re ]]
}

@test "regex: matches 'feat(api)!: breaking change'" {
  re="$(extract_regex)"
  title='feat(api)!: breaking change'
  [[ "$title" =~ $re ]]
}

@test "regex: matches 'chore(deps): bump'" {
  re="$(extract_regex)"
  title='chore(deps): bump'
  [[ "$title" =~ $re ]]
}

@test "regex: matches 'docs(readme.md): typo'" {
  # Exercises the `.` and `_` chars in scope class.
  re="$(extract_regex)"
  title='docs(readme.md): typo'
  [[ "$title" =~ $re ]]
}

@test "regex: matches 'ci(build_pipeline): enable cache'" {
  re="$(extract_regex)"
  title='ci(build_pipeline): enable cache'
  [[ "$title" =~ $re ]]
}

@test "regex: matches 'feat!: breaking change without scope'" {
  re="$(extract_regex)"
  title='feat!: breaking change without scope'
  [[ "$title" =~ $re ]]
}

# ---------------------------------------------------------------------------
# Regex behavior — invalid PR titles MUST NOT match
#
# NOTE: Use the inline `[[ ]]` form (mirroring the positive tests above) and
# fail explicitly when the regex matches. The earlier `run bash -c "$re"` form
# was broken on bash 3.2 because unquoted regex metacharacters (`\(`, `?`, etc.)
# triggered a syntax error → exit 2, which `[ "$status" -ne 0 ]` accepted as a
# pass — silently masking any regression where a bad title actually matched.
# ---------------------------------------------------------------------------

@test "regex: rejects 'add foo' (no type)" {
  re="$(extract_regex)"
  title='add foo'
  if [[ "$title" =~ $re ]]; then return 1; fi
}

@test "regex: rejects 'feat add foo' (no colon)" {
  re="$(extract_regex)"
  title='feat add foo'
  if [[ "$title" =~ $re ]]; then return 1; fi
}

@test "regex: rejects 'random: stuff' (type not allowed)" {
  re="$(extract_regex)"
  title='random: stuff'
  if [[ "$title" =~ $re ]]; then return 1; fi
}

@test "regex: rejects 'feat(): empty scope'" {
  re="$(extract_regex)"
  title='feat(): empty scope'
  if [[ "$title" =~ $re ]]; then return 1; fi
}

@test "regex: rejects 'FEAT: uppercase type'" {
  re="$(extract_regex)"
  title='FEAT: uppercase type'
  if [[ "$title" =~ $re ]]; then return 1; fi
}

@test "regex: rejects 'feat:' (no description)" {
  re="$(extract_regex)"
  title='feat:'
  if [[ "$title" =~ $re ]]; then return 1; fi
}
