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
#   --allow-ahead N   tolerate the CHANGELOG being N patch releases ahead,
#                     and, for any N >= 1, also exactly the next major
#                     (M+1.0.0) or next minor (M.m+1.0) of the manifest.
#                     Use 0 on main, where the bump has already happened —
#                     nothing ahead is accepted there.
#                     Use 1 on a pull request, where the entry names the
#                     version the merge is about to produce.
#
# A breaking or feature release is requested by writing the next-major or
# next-minor heading in the plugin's CHANGELOG; auto-bump-versions.sh then sets
# plugin.json to it on merge. plugin.json is never hand-edited for it. Any other
# version ahead (a skipped major, 1.6.0 against 1.4.x) is one the bump cannot
# produce, so it fails here, naming what is allowed.
#
# Every plugin must have a CHANGELOG.md; a missing one is a failure. Four of the
# six had none, which is how the tcs-patterns bump in #114/#115 went unnoticed:
# the check that would have caught a version gap had nothing to compare against
# for exactly the plugin that had one.
#
# A CHANGELOG whose first heading is not a release (e.g. "## [Unreleased]",
# "## [2.0.0-rc1]", or a non-canonical "## [2.00.0]") is skipped for the
# comparison — the file exists, it just has nothing to compare yet.
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
      # The whole header comment, however long it grows.
      awk 'NR > 2 { if ($0 !~ /^#/) exit; print }' "$0"
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
# the first heading is not a release (Unreleased sections, prose headings,
# pre-releases).
# A release is a canonical X.Y.Z (no leading zeros) opened by "[", whitespace
# or line start and closed by "]", whitespace or end of line — so a
# pre-release ("2.0.0-rc1"), build metadata ("2.0.0+7") or "2.00.0" names no
# release at all. auto-bump-versions.sh and check-changelog-version-sync.sh
# must apply this same rule, or the PR-side check accepts what the merge
# will not produce.
_changelog_version() {
  grep -m1 '^## ' "$1" 2>/dev/null \
    | grep -oE '(^|[[:space:]]|\[)(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)(\]|[[:space:]]|$)' \
    | head -1 \
    | grep -oE '[0-9]+\.[0-9]+\.[0-9]+'
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

# 0 if $1 is further ahead of $2 than the merge's auto-bump can take it, and
# print the reason. Tolerated ahead: up to $allow_ahead patch releases on the
# same major.minor and, when $allow_ahead >= 1, exactly the next major or the
# next minor. A CHANGELOG behind or equal to the manifest is always fine.
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

if allow_ahead == 0:
    print('nothing ahead is allowed here')
    sys.exit(0)

major, minor, patch = manifest
patch_limit = (major, minor, patch + allow_ahead)
next_minor = (major, minor + 1, 0)
next_major = (major + 1, 0, 0)

same_line = changelog[:2] == manifest[:2]
if (same_line and changelog <= patch_limit) or changelog in (next_minor, next_major):
    sys.exit(1)

fmt = lambda v: '.'.join(str(p) for p in v)
print(f'allowed: up to {fmt(patch_limit)}, or {fmt(next_minor)}, or {fmt(next_major)}')
sys.exit(0)
PY
}

status=0
checked=0

for dir in $plugin_dirs; do
  dir="${dir%/}"
  [ -d "$dir" ] || continue

  changelog="$dir/CHANGELOG.md"
  manifest="$dir/.claude-plugin/plugin.json"

  # A plugin directory without a manifest is not a plugin — skip it rather than
  # reporting a scaffold or a stray directory as a missing CHANGELOG.
  [ -f "$manifest" ] || continue

  if [ ! -f "$changelog" ]; then
    printf '%s: no CHANGELOG.md — every plugin needs one\n' "$dir" >&2
    status=1
    continue
  fi

  cl_version="$(_changelog_version "$changelog")"
  [ -n "$cl_version" ] || continue

  mf_version="$(_manifest_version "$manifest")" || exit 2

  checked=$((checked + 1))

  if reason="$(_is_too_far_ahead "$cl_version" "$mf_version")"; then
    printf '%s: CHANGELOG documents %s but plugin.json carries %s — %s\n' \
      "$dir" "$cl_version" "$mf_version" "$reason" >&2
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
  printf '\nA missing CHANGELOG means a plugin can ship a version nothing records.
A CHANGELOG ahead of its manifest means a documented version never shipped.\n' >&2
  printf 'A lost auto-bump run is caught up by the next one (#196); trigger\n' >&2
  printf '"Auto-bump plugin versions" via Run workflow to catch up now. If the gap\n' >&2
  printf 'survives a run, the bump cannot close it: a version set by hand, a reverted\n' >&2
  printf 'bump, a CHANGELOG heading the bump cannot reach, or a push that keeps being\n' >&2
  printf 'rejected (GH013). Never hand-edit plugin.json to silence it.\n' >&2
fi

exit "$status"
