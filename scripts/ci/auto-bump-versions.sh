#!/bin/bash
#
# scripts/ci/auto-bump-versions.sh
#
# Auto-bump plugin manifest versions for every change that has not had its
# bump yet. Run on main after a merge, on dispatch, or on a schedule.
#
# What is owed is derived from the checked-out history, never from the push
# that triggered the run (issue #196). GitHub delivered no push event for #187,
# so no run happened, and the old range-based bump (`github.event.before..sha`)
# never looked at that commit again: tcs-patterns stayed one version behind its
# CHANGELOG and every later run failed its verify step. Deriving the work from
# the state of main means a lost, cancelled or failed run is caught up by the
# next one, whatever the reason it was lost.
#
#   1. For each plugins/<X>/ with a manifest, find L: the newest first-parent
#      commit that RAISED plugins/<X>/.claude-plugin/plugin.json's version
#      (strictly higher than in its first parent, or the manifest is new there).
#      A revert or a hand-set lower version is never L, so a version that has
#      already shipped is never shipped again with different contents.
#   2. Every first-parent commit after L that touched plugins/<X>/ is owed one
#      bump — touched, not net-changed: a change and its revert both shipped.
#   3. The owed bumps are replayed oldest first, starting from the higher of
#      the manifest's version and L's. Each is a patch bump, unless the top
#      version heading of plugins/<X>/CHANGELOG.md *as of that commit* (e.g.
#      "## [2.0.0] - ...") names exactly the next major (M+1.0.0) or the next
#      minor (M.m+1.0) — then that version. This is what the lost runs would
#      have produced one by one, so the CHANGELOG and the manifest agree.
#      Writing that heading is how a breaking or feature release is requested;
#      plugin.json is never hand-edited for it. Any other heading (a skipped
#      major, an Unreleased section, no CHANGELOG) gets the patch bump, and
#      check-changelog-version-sync.sh reports a heading the bump cannot reach.
#   4. If any plugin's version differs from what it was when
#      .claude-plugin/marketplace.json last raised metadata.version (or the
#      plugin did not exist then): patch-bump the marketplace once.
#
# Mutates files in place. Does not commit or push — leave that to the workflow.
#
# Usage:
#   auto-bump-versions.sh
#
# Positional arguments are ignored with a note. A run queued before #196 still
# executes the old bump-and-push.sh, which passes <base-sha> <head-sha>.
#
# Exit codes:
#   0  — success (whether or not anything was bumped)
#   1  — error (shallow clone, git failure, malformed version, a manifest no
#        commit ever gave a version). Never falls back to bumping.
#
# Bash 3.2 compatible. shellcheck clean.

set -uo pipefail

if [ "$#" -gt 0 ]; then
  printf 'auto-bump-versions: arguments ignored (%s) — the bump is derived from the checked-out history (#196)\n' "$*" >&2
fi

MARKETPLACE=".claude-plugin/marketplace.json"

die() {
  printf 'auto-bump-versions: %s\n' "$1" >&2
  exit 1
}

# A shallow clone has no L for most plugins: refuse rather than bump them all.
shallow="$(git rev-parse --is-shallow-repository 2>&1)" \
  || die "not a git repository: $shallow"
[ "$shallow" = "false" ] \
  || die "shallow clone — the history needed to find what is owed is missing (use fetch-depth: 0)"

# ---------------------------------------------------------------------------
# Reading versions out of history
# ---------------------------------------------------------------------------

# Print the version at <json-key-path> in <rev>:<path>, or nothing when the
# file or the key is absent there. <rev> "WORKTREE" reads the checked-out file.
version_at() {
  rev="$1"
  path="$2"
  key="$3"
  if [ "$rev" = "WORKTREE" ]; then
    cat "$path" 2>/dev/null
  else
    git show "${rev}:${path}" 2>/dev/null
  fi | python3 -c '
import json, sys
try:
    d = json.load(sys.stdin)
except Exception:
    sys.exit(0)
for k in sys.argv[1].split("."):
    d = d.get(k) if isinstance(d, dict) else None
    if d is None:
        sys.exit(0)
print(d)
' "$key"
}

# 0 if version <new> is strictly higher than <old>; an empty <old> (the file
# did not exist) counts as lower. A version that is not X.Y.Z never compares.
is_raise() {
  python3 - "$1" "$2" <<'PY'
import sys

def parse(v):
    parts = v.split('.')
    if len(parts) != 3 or not all(p.isdigit() for p in parts):
        return None
    return tuple(int(p) for p in parts)

new, old = parse(sys.argv[1]), sys.argv[2]
if new is None:
    sys.exit(1)
if old == '':
    sys.exit(0)
old = parse(old)
sys.exit(0 if old is not None and new > old else 1)
PY
}

# Print L for <path>: the newest first-parent commit that raised the version
# at <json-key-path>. Returns 1 when no commit ever did.
#
# Path-limited, so a merge counts when its tree differs from its first parent
# — what a --no-ff merge of a hand bump looks like. The candidate list is only
# a pre-filter; every candidate's value is compared, so a reformatted manifest
# is not a raise.
last_raise() {
  path="$1"
  key="$2"
  revs="$(git log --first-parent --format=%H -- "$path")" || return 1
  for rev in $revs; do
    new="$(version_at "$rev" "$path" "$key")"
    [ -n "$new" ] || continue
    # The root commit has no parent: `rev^` fails and old stays empty.
    old="$(version_at "${rev}^" "$path" "$key")"
    if is_raise "$new" "$old"; then
      printf '%s\n' "$rev"
      return 0
    fi
  done
  return 1
}

# Print the version a CHANGELOG's first "## " heading names, or nothing when
# the file is missing or the first heading is not a release (Unreleased,
# prose, a pre-release).
# A release is a canonical X.Y.Z (no leading zeros) opened by "[", whitespace
# or line start and closed by "]", whitespace or end of line — so a
# pre-release ("2.0.0-rc1"), build metadata ("2.0.0+7") or "2.00.0" names no
# release at all. auto-bump-versions.sh and check-changelog-version-sync.sh
# must apply this same rule, or the PR-side check accepts what the merge
# will not produce.
changelog_version() {
  grep -m1 '^## ' "$1" 2>/dev/null \
    | grep -oE '(^|[[:space:]]|\[)(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)(\]|[[:space:]]|$)' \
    | head -1 \
    | grep -oE '[0-9]+\.[0-9]+\.[0-9]+'
}

# ---------------------------------------------------------------------------
# Bump helper (uses python3 for JSON round-trip — preserves field order)
# ---------------------------------------------------------------------------

# bump_version <manifest> <json-key-path> <floor> <step>...
#   Apply one bump per <step>, starting from the higher of the manifest's
#   version and <floor> (empty: the manifest's). A step is the CHANGELOG
#   heading that commit carried, or "-" for none: the step sets the version
#   to it when it is exactly the next major or next minor, and patch-bumps
#   otherwise.
bump_version() {
  manifest="$1"
  key_path="$2"
  floor="$3"
  shift 3

  if [ ! -f "$manifest" ]; then
    printf 'auto-bump-versions: skip — manifest not found: %s\n' "$manifest" >&2
    return 1
  fi

  python3 - "$manifest" "$key_path" "$floor" "$@" <<'PY'
import json
import sys

manifest_path = sys.argv[1]
key_path = sys.argv[2].split('.')
floor = sys.argv[3]
steps = sys.argv[4:]

with open(manifest_path) as f:
    data = json.load(f)

target = data
for key in key_path[:-1]:
    target = target[key]

current = target[key_path[-1]]


def parse(version):
    parts = version.split('.')
    if len(parts) != 3 or not all(p.isdigit() for p in parts):
        print(f'auto-bump-versions: malformed version "{version}" in {manifest_path}',
              file=sys.stderr)
        sys.exit(1)
    return tuple(int(p) for p in parts)


version = parse(current)
# Never step below a version that already shipped: after a reverted bump the
# manifest is lower than L's, and 1.4.5 must not go out twice.
if floor:
    version = max(version, parse(floor))

# A major or minor release is requested through the CHANGELOG, and honoured
# only when it is exactly the next one — a skipped version is not a release
# this script may invent.
requested = False
for step in steps:
    major, minor, patch = version
    next_major = (major + 1, 0, 0)
    next_minor = (major, minor + 1, 0)
    asked = parse(step) if step != '-' else None
    if asked in (next_major, next_minor):
        version = asked
        requested = True
    else:
        version = (major, minor, patch + 1)

new = '.'.join(str(p) for p in version)
target[key_path[-1]] = new

with open(manifest_path, 'w') as f:
    # ensure_ascii=False preserves non-ASCII characters (em-dashes, etc.)
    # in plugin descriptions. Without it, json.dump escapes them to \uXXXX
    # and silently rewrites unrelated lines on every bump (bug from PR #31
    # auto-bump-versions live test on 2026-05-21).
    json.dump(data, f, indent=2, ensure_ascii=False)
    f.write('\n')

note = ' (requested by CHANGELOG)' if requested else ''
count = f', {len(steps)} commits' if len(steps) > 1 else ''
print(f'{manifest_path}: {current} -> {new}{note}{count}')
PY
}

# ---------------------------------------------------------------------------
# Plugins: replay every owed bump
# ---------------------------------------------------------------------------

for dir in plugins/*/; do
  plugin_dir="${dir%/}"
  manifest="${plugin_dir}/.claude-plugin/plugin.json"
  [ -f "$manifest" ] || continue

  raised="$(last_raise "$manifest" "version")" \
    || die "${plugin_dir}: no commit ever gave ${manifest} a version"

  owed="$(git rev-list --first-parent --reverse "${raised}..HEAD" -- "${plugin_dir}/")" \
    || die "${plugin_dir}: git rev-list failed"
  [ -n "$owed" ] || continue

  steps=""
  for rev in $owed; do
    heading="$(git show "${rev}:${plugin_dir}/CHANGELOG.md" 2>/dev/null \
      | changelog_version /dev/stdin)"
    steps="${steps} ${heading:--}"
  done

  floor="$(version_at "$raised" "$manifest" "version")"
  # shellcheck disable=SC2086  # steps is a list of X.Y.Z or "-", never spaced
  bump_version "$manifest" "version" "$floor" $steps \
    || die "${plugin_dir}: bump failed"
done

# ---------------------------------------------------------------------------
# Marketplace: one patch when any plugin version moved since its last raise
# ---------------------------------------------------------------------------

[ -f "$MARKETPLACE" ] || exit 0

marketplace_raised="$(last_raise "$MARKETPLACE" "metadata.version")" \
  || die "no commit ever gave ${MARKETPLACE} a metadata.version"

moved=0
for dir in plugins/*/; do
  manifest="${dir%/}/.claude-plugin/plugin.json"
  [ -f "$manifest" ] || continue
  if [ "$(version_at WORKTREE "$manifest" "version")" \
       != "$(version_at "$marketplace_raised" "$manifest" "version")" ]; then
    moved=1
    break
  fi
done

if [ "$moved" -eq 1 ]; then
  bump_version "$MARKETPLACE" "metadata.version" "" - \
    || die "marketplace bump failed"
fi

exit 0
