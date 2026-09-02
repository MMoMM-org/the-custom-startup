#!/bin/bash
#
# scripts/ci/check-changelog-version-sync.sh
#
# Fail when a plugin's CHANGELOG.md documents a version its plugin.json does
# not carry — the state a dropped auto-bump leaves behind (issue #93).
#
# On 2026-08-31 two PRs merged 8 seconds apart, the second auto-bump run lost a
# non-fast-forward push, and tcs-helper shipped with CHANGELOG [4.3.1] against
# plugin.json 4.3.0. Nothing noticed: the merge was clean and only a red run in
# the Actions tab recorded it.
#
# The invariant is one-sided. A CHANGELOG *behind* plugin.json is normal — not
# every change earns an entry, and this repo patch-bumps on any plugin file.
# A CHANGELOG *ahead* means a version was written down but never shipped.
#
#   --allow-ahead N   tolerate the CHANGELOG being N patch releases ahead.
#                     Use 0 on main, where the bump has already happened.
#                     Use 1 on a pull request, where the entry names the
#                     version the merge is about to produce.
#
# Plugins without a CHANGELOG.md, and CHANGELOGs whose first heading is not a
# version (e.g. "## [Unreleased]"), are skipped — there is nothing to compare.
#
# Usage:
#   check-changelog-version-sync.sh [--allow-ahead N] [<plugin-dir> ...]
#
# Exit codes:
#   0  — every comparable plugin is consistent
#   1  — at least one CHANGELOG is ahead of its manifest
#   2  — usage error or unreadable manifest
#
# Bash 3.2 compatible. shellcheck clean.

set -uo pipefail

allow_ahead=0
plugin_dirs=""

while [ "$#" -gt 0 ]; do
  case "$1" in
    --allow-ahead)
      allow_ahead="${2:-}"
      case "$allow_ahead" in
        ''|*[!0-9]*)
          printf 'check-changelog-version-sync: --allow-ahead needs a non-negative integer\n' >&2
          exit 2
          ;;
      esac
      shift 2
      ;;
    -h|--help)
      sed -n '3,30p' "$0"
      exit 0
      ;;
    -*)
      printf 'check-changelog-version-sync: unknown option %s\n' "$1" >&2
      exit 2
      ;;
    *)
      plugin_dirs="${plugin_dirs} $1"
      shift
      ;;
  esac
done

if [ -z "${plugin_dirs// /}" ]; then
  plugin_dirs="$(printf '%s ' plugins/*/)"
fi

# Print the version a CHANGELOG's first "## " heading names, or nothing when
# the first heading is not a plain semver (Unreleased sections, prose headings).
_changelog_version() {
  grep -m1 '^## ' "$1" 2>/dev/null \
    | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' \
    | head -1
}

_manifest_version() {
  python3 - "$1" <<'PY'
import json
import sys

try:
    with open(sys.argv[1]) as f:
        print(json.load(f)["version"])
except (OSError, ValueError, KeyError) as exc:
    print(f"check-changelog-version-sync: cannot read version from {sys.argv[1]}: {exc}",
          file=sys.stderr)
    sys.exit(2)
PY
}

# 0 if $1 is more than $allow_ahead patch releases beyond $2, on the same
# major.minor. A CHANGELOG on a different major.minor than the manifest is
# reported too — that is a deliberate release the manifest has not followed.
_is_too_far_ahead() {
  changelog="$1"
  manifest="$2"
  python3 - "$changelog" "$manifest" "$allow_ahead" <<'PY'
import sys

changelog = tuple(int(p) for p in sys.argv[1].split('.'))
manifest = tuple(int(p) for p in sys.argv[2].split('.'))
allow_ahead = int(sys.argv[3])

if changelog <= manifest:
    sys.exit(1)                     # behind or equal — fine

# Ahead. Tolerated only as patch releases on the same major.minor line.
same_line = changelog[:2] == manifest[:2]
within = same_line and (changelog[2] - manifest[2]) <= allow_ahead
sys.exit(1 if within else 0)
PY
}

status=0
checked=0

for dir in $plugin_dirs; do
  dir="${dir%/}"
  [ -d "$dir" ] || continue

  changelog="$dir/CHANGELOG.md"
  manifest="$dir/.claude-plugin/plugin.json"

  [ -f "$changelog" ] || continue
  if [ ! -f "$manifest" ]; then
    printf 'check-changelog-version-sync: %s has a CHANGELOG but no plugin.json\n' "$dir" >&2
    status=1
    continue
  fi

  cl_version="$(_changelog_version "$changelog")"
  [ -n "$cl_version" ] || continue

  mf_version="$(_manifest_version "$manifest")" || exit 2

  checked=$((checked + 1))

  if _is_too_far_ahead "$cl_version" "$mf_version"; then
    printf '%s: CHANGELOG documents %s but plugin.json carries %s\n' \
      "$dir" "$cl_version" "$mf_version" >&2
    status=1
  else
    printf '%s: CHANGELOG %s / manifest %s — ok\n' "$dir" "$cl_version" "$mf_version"
  fi
done

if [ "$checked" -eq 0 ]; then
  printf 'check-changelog-version-sync: compared nothing — the plugin glob or the\n' >&2
  printf '  CHANGELOG heading parser is broken, not "all clear"\n' >&2
  exit 1
fi

if [ "$status" -ne 0 ]; then
  printf '\nA CHANGELOG ahead of its manifest means a documented version never shipped.\n' >&2
  printf 'Usually a dropped auto-bump (issue #93) — check the Actions tab for a failed\n' >&2
  printf '"Auto-bump plugin versions" run, and repair the manifest by hand.\n' >&2
fi

exit "$status"
