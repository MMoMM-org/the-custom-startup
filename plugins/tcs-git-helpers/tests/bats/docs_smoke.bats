#!/usr/bin/env bats
# T1.2 — README + CHANGELOG smoke test
# Validates plugins/tcs-git-helpers documentation surface so future tasks have
# stable docs-shape contract:
#   - README mentions all 12 PRD Goals (M1-M12) on dedicated `- M<N>` lines
#   - README has the four mandatory sections (## Overview, ## Installation,
#     ## Basic Usage, ## References)
#   - All in-document `](path)` links resolve to files that exist relative
#     to the plugin root
#   - CHANGELOG has the `## [1.0.0] - 2026-MM-DD` entry

PLUGIN_ROOT="${BATS_TEST_DIRNAME}/../.."

# ---------------------------------------------------------------------------
# README — 12 PRD Goals (M1..M12) coverage
# ---------------------------------------------------------------------------

@test "README.md exists" {
  [ -f "${PLUGIN_ROOT}/README.md" ]
}

@test "README references all 12 PRD Goals via '- M<N>' lines (>=12 matches)" {
  run grep -c '^- M' "${PLUGIN_ROOT}/README.md"
  [ "$status" -eq 0 ]
  [ "$output" -ge 12 ]
}

@test "README mentions each M1..M12 explicitly" {
  for i in 1 2 3 4 5 6 7 8 9 10 11 12; do
    grep -qE "^- M${i}\b" "${PLUGIN_ROOT}/README.md" || {
      echo "missing PRD Goal line: M${i}" >&2
      return 1
    }
  done
}

# ---------------------------------------------------------------------------
# README — required sections
# ---------------------------------------------------------------------------

@test "README has '## Overview' section" {
  grep -qE '^## Overview$' "${PLUGIN_ROOT}/README.md"
}

@test "README has '## Installation' section" {
  grep -qE '^## Installation$' "${PLUGIN_ROOT}/README.md"
}

@test "README has '## Basic Usage' section" {
  grep -qE '^## Basic Usage$' "${PLUGIN_ROOT}/README.md"
}

@test "README has '## References' section" {
  grep -qE '^## References$' "${PLUGIN_ROOT}/README.md"
}

# ---------------------------------------------------------------------------
# README — link integrity (every `](path)` resolves)
# Skips: external URLs (http/https/mailto), in-page anchors (#...).
# ---------------------------------------------------------------------------

@test "README in-document links resolve to existing files" {
  local readme="${PLUGIN_ROOT}/README.md"
  local missing=""
  # Extract markdown link targets with sed (POSIX BRE).
  local targets
  targets="$(sed -nE 's/.*\]\(([^)]+)\).*/\1/p' "$readme")"
  while IFS= read -r target; do
    [ -z "$target" ] && continue
    case "$target" in
      http://*|https://*|mailto:*) continue ;;   # external — skip
      \#*) continue ;;                            # in-page anchor — skip
    esac
    # Strip in-link anchor suffix (e.g., foo.md#section -> foo.md)
    local path="${target%%#*}"
    [ -z "$path" ] && continue
    if [ ! -e "${PLUGIN_ROOT}/${path}" ]; then
      missing="${missing}${path}\n"
    fi
  done <<< "$targets"
  if [ -n "$missing" ]; then
    printf 'unresolved README links:\n%b' "$missing" >&2
    return 1
  fi
}

# ---------------------------------------------------------------------------
# CHANGELOG — 1.0.0 entry with date
# ---------------------------------------------------------------------------

@test "CHANGELOG.md exists" {
  [ -f "${PLUGIN_ROOT}/CHANGELOG.md" ]
}

@test "CHANGELOG has '## [1.0.0] - 2026-...' entry" {
  run grep -E '^## \[1\.0\.0\] - 2026' "${PLUGIN_ROOT}/CHANGELOG.md"
  [ "$status" -eq 0 ]
  [ -n "$output" ]
}
