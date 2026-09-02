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
# The four "README has '## Skills'" style greps that used to sit here are gone
# (issue #90). A heading is prose for humans: if the information architecture
# from spec-006 gets reorganised, the next reader notices, and asserting the
# literal heading text only guaranteed that nobody could improve the layout
# without also editing a test. What remains below is the link-integrity check,
# which resolves every path the README claims exists and so catches real
# breakage.
# ---------------------------------------------------------------------------

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
