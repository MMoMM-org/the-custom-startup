#!/bin/bash
#
# scripts/ci/auto-bump-versions.sh
#
# Auto-bump plugin manifest versions when plugin code changed without a bump.
# Triggered by push to main (typically a PR merge). Reads the diff range and:
#
#   1. For each plugins/<X>/ with non-manifest changes: patch-bump
#      plugins/<X>/.claude-plugin/plugin.json IF not already bumped in the diff.
#   2. If ANY plugin manifest changed in the diff (either bumped by step 1 or
#      manually bumped in the PR): patch-bump .claude-plugin/marketplace.json
#      IF not already bumped in the diff.
#
# Mutates files in place. Does not commit or push — leave that to the workflow.
#
# Usage:
#   auto-bump-versions.sh <base-sha> <head-sha>
#
# Exit codes:
#   0  — success (whether or not anything was bumped)
#   1  — error (git diff failed, malformed version, missing manifest)
#
# Bash 3.2 compatible. shellcheck clean.

set -uo pipefail

BASE_SHA="${1:-HEAD^}"
HEAD_SHA="${2:-HEAD}"

# ---------------------------------------------------------------------------
# Collect changed paths in the diff range
# ---------------------------------------------------------------------------

changed_files="$(git diff --name-only "$BASE_SHA" "$HEAD_SHA" 2>&1)" || {
  printf 'auto-bump-versions: git diff failed: %s\n' "$changed_files" >&2
  exit 1
}

# ---------------------------------------------------------------------------
# Classify per plugin: touched (non-manifest) vs already-bumped (manifest)
# ---------------------------------------------------------------------------

touched_plugins=""
already_bumped_plugins=""
marketplace_in_diff=0

while IFS= read -r path; do
  [ -z "$path" ] && continue

  case "$path" in
    .claude-plugin/marketplace.json)
      marketplace_in_diff=1
      ;;
    plugins/*/.claude-plugin/plugin.json)
      plugin="${path#plugins/}"
      plugin="${plugin%%/*}"
      already_bumped_plugins="${already_bumped_plugins}
${plugin}"
      ;;
    plugins/*/*)
      plugin="${path#plugins/}"
      plugin="${plugin%%/*}"
      touched_plugins="${touched_plugins}
${plugin}"
      ;;
  esac
done <<EOF
$changed_files
EOF

touched_plugins="$(printf '%s\n' "$touched_plugins" | sort -u | grep -v '^$' || true)"
already_bumped_plugins="$(printf '%s\n' "$already_bumped_plugins" | sort -u | grep -v '^$' || true)"

# Plugins needing a bump = touched - already_bumped
to_bump=""
for plugin in $touched_plugins; do
  found=0
  for bumped in $already_bumped_plugins; do
    if [ "$plugin" = "$bumped" ]; then
      found=1
      break
    fi
  done
  if [ "$found" -eq 0 ]; then
    to_bump="${to_bump}
${plugin}"
  fi
done
to_bump="$(printf '%s\n' "$to_bump" | sort -u | grep -v '^$' || true)"

# ---------------------------------------------------------------------------
# Patch-bump helper (uses python3 for JSON round-trip — preserves field order)
# ---------------------------------------------------------------------------

bump_version() {
  manifest="$1"
  key_path="$2"

  if [ ! -f "$manifest" ]; then
    printf 'auto-bump-versions: skip — manifest not found: %s\n' "$manifest" >&2
    return 1
  fi

  python3 - "$manifest" "$key_path" <<'PY'
import json
import sys

manifest_path = sys.argv[1]
key_path = sys.argv[2].split('.')

with open(manifest_path) as f:
    data = json.load(f)

target = data
for key in key_path[:-1]:
    target = target[key]

current = target[key_path[-1]]
parts = current.split('.')
if len(parts) != 3:
    print(f'auto-bump-versions: malformed version "{current}" in {manifest_path}',
          file=sys.stderr)
    sys.exit(1)

major, minor, patch = parts
try:
    new = f'{major}.{minor}.{int(patch) + 1}'
except ValueError:
    print(f'auto-bump-versions: non-numeric patch "{patch}" in {manifest_path}',
          file=sys.stderr)
    sys.exit(1)

target[key_path[-1]] = new

with open(manifest_path, 'w') as f:
    # ensure_ascii=False preserves non-ASCII characters (em-dashes, etc.)
    # in plugin descriptions. Without it, json.dump escapes them to \uXXXX
    # and silently rewrites unrelated lines on every bump (bug from PR #31
    # auto-bump-versions live test on 2026-05-21).
    json.dump(data, f, indent=2, ensure_ascii=False)
    f.write('\n')

print(f'{manifest_path}: {current} -> {new}')
PY
}

# ---------------------------------------------------------------------------
# Execute bumps
# ---------------------------------------------------------------------------

bumped_any=0
for plugin in $to_bump; do
  manifest="plugins/${plugin}/.claude-plugin/plugin.json"
  if bump_version "$manifest" "version"; then
    bumped_any=1
  fi
done

# Marketplace bump if any plugin manifest changed in this push (either by us
# above OR manually in the merged PR) and marketplace wasn't already touched.
if { [ -n "$already_bumped_plugins" ] || [ "$bumped_any" -eq 1 ]; } \
   && [ "$marketplace_in_diff" -eq 0 ]; then
  bump_version ".claude-plugin/marketplace.json" "metadata.version"
fi

exit 0
