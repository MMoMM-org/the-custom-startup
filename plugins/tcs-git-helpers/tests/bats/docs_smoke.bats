#!/usr/bin/env bats
# README + CHANGELOG smoke test
# Validates plugins/tcs-git-helpers documentation surface so future tasks have
# a stable docs-shape contract. The README was restructured in spec-006
# (docs-rewrite) to the tcs-helper-style layout, so this test tracks the
# current information architecture rather than the original v1.0 PRD dump:
#   - README has the user-facing sections (## Skills, ## Hooks, ## Installation,
#     ## References). The M1-M12 PRD goals now live in spec-011 requirements,
#     not the user-facing README.
#   - All in-document `](path)` links resolve to files that exist relative
#     to the plugin root
#   - CHANGELOG has the `## [1.0.0] - 2026-MM-DD` entry

PLUGIN_ROOT="${BATS_TEST_DIRNAME}/../.."

# ---------------------------------------------------------------------------
# README — existence
# ---------------------------------------------------------------------------

@test "README.md exists" {
  [ -f "${PLUGIN_ROOT}/README.md" ]
}

# ---------------------------------------------------------------------------
# README — required sections (current spec-006 information architecture)
# ---------------------------------------------------------------------------

@test "README has '## Skills' section" {
  grep -qE '^## Skills$' "${PLUGIN_ROOT}/README.md"
}

@test "README has '## Hooks' section" {
  grep -qE '^## Hooks$' "${PLUGIN_ROOT}/README.md"
}

@test "README has '## Installation' section" {
  grep -qE '^## Installation$' "${PLUGIN_ROOT}/README.md"
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
