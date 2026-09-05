#!/bin/bash
#
# scripts/ci/check-docs-sync.sh
#
# Fail when a pull request changes user-facing code without accounting for the
# documentation surfaces that change with it.
#
# Written when auto-merge was switched on. Until then the pause before merging
# was where somebody noticed the docs had not been updated — not a CI concern,
# a human one. A pull request that merges itself has no such pause, so the
# check has to exist or the habit does not.
#
# The motivating failure is precise, and worth stating because it rules out the
# obvious cheaper check. In #129 the statusline gained an opt-in segment.
# docs/guides/statusline.md *was* written. Still missing at that point:
#
#   - CHANGELOG.md               — no entry at all
#   - README.md                  — still described the old ccusage bar
#   - scripts/statusline.toml    — the new keys were absent
#   - the configurator           — which writes its *own* statusline.toml, so
#                                  anyone configuring through the wizard would
#                                  never have learned the feature existed
#
# A check asking "did any documentation change?" would have passed. So this one
# does not ask that. It asks, per surface, whether that surface was answered.
#
# Two rules:
#
#   A. Any change under scripts/ or plugins/ requires a CHANGELOG.md change.
#      Excluded: **/tests/** and scripts/ci/** — test work and CI plumbing are
#      not user-facing, and a check that fires on them teaches people to ignore
#      it.
#
#   B. A mapping table (.github/docs-map) names, per code glob, the surfaces
#      that must move with it. Deliberately small: it holds only entries with a
#      demonstrated failure behind them. A rule that is usually wrong gets
#      switched off within a week, and then it protects nothing.
#
# Either can be waived from the pull request body, but never silently:
#
#   Docs: scripts/statusline.toml — internal rename only, no option changed
#
# The reason must be at least MIN_REASON characters. "n/a" is refused on
# purpose: a waiver should cost more than the edit it avoids.
#
# Usage:
#   check-docs-sync.sh --changed-files <file|-> [--pr-body <file>] [--map <file>]
#
# Exit codes:
#   0  — every affected surface is either changed or waived with a reason
#   1  — at least one surface is unaccounted for (each is named)
#   2  — bad invocation

set -u

MIN_REASON=20
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

changed_files_src=""
pr_body_file=""
map_file="$REPO_ROOT/.github/docs-map"

die() { printf 'check-docs-sync: %s\n' "$1" >&2; exit 2; }

while [ $# -gt 0 ]; do
  case "$1" in
    --changed-files) changed_files_src="${2:-}"; shift 2 || die "--changed-files needs a value" ;;
    --pr-body)       pr_body_file="${2:-}";      shift 2 || die "--pr-body needs a value" ;;
    --map)           map_file="${2:-}";          shift 2 || die "--map needs a value" ;;
    -h|--help)       sed -n '2,60p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *)               die "unknown argument: $1" ;;
  esac
done

[ -n "$changed_files_src" ] || die "--changed-files is required"

if [ "$changed_files_src" = "-" ]; then
  CHANGED=$(cat)
else
  [ -f "$changed_files_src" ] || die "no such file: $changed_files_src"
  CHANGED=$(cat "$changed_files_src")
fi

PR_BODY=""
if [ -n "$pr_body_file" ] && [ -f "$pr_body_file" ]; then
  PR_BODY=$(cat "$pr_body_file")
fi

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# Was this exact path among the changed files?
changed() {
  printf '%s\n' "$CHANGED" | grep -Fxq -- "$1"
}

# Does any changed path match this glob? Compared with bash's own pattern
# matching rather than `find`, because the input is a list of paths, not a tree.
any_changed_matching() {
  local pattern="$1" path
  while IFS= read -r path; do
    [ -n "$path" ] || continue
    # shellcheck disable=SC2254  # the pattern is meant to glob
    case "$path" in $pattern) return 0 ;; esac
  done <<< "$CHANGED"
  return 1
}

# Is there a waiver for this surface, carrying a real reason?
#
# Accepts an em dash or a plain "--" as the separator, because a commit message
# typed on a German keyboard will use one and a copy-paste of this comment the
# other. Everything after it must be MIN_REASON characters of actual text.
waived() {
  local surface="$1" line reason
  [ -n "$PR_BODY" ] || return 1
  while IFS= read -r line; do
    case "$line" in
      [Dd]ocs:*) ;;
      *) continue ;;
    esac
    # Strip the "Docs:" prefix, then split on the first separator.
    line="${line#*[Dd]ocs:}"
    case "$line" in
      *—*)  reason="${line#*—}";  line="${line%%—*}"  ;;
      *--*) reason="${line#*--}"; line="${line%%--*}" ;;
      *) continue ;;
    esac
    # Trim surrounding whitespace from both halves.
    line="${line#"${line%%[![:space:]]*}"}"; line="${line%"${line##*[![:space:]]}"}"
    reason="${reason#"${reason%%[![:space:]]*}"}"; reason="${reason%"${reason##*[![:space:]]}"}"

    [ "$line" = "$surface" ] || continue
    if [ "${#reason}" -ge "$MIN_REASON" ]; then
      return 0
    fi
    printf '  waiver for %s rejected: the reason is %d characters, %d are required\n' \
      "$surface" "${#reason}" "$MIN_REASON" >&2
    return 1
  done <<< "$PR_BODY"
  return 1
}

MISSING=""
note_missing() {
  MISSING="${MISSING}${MISSING:+$'\n'}  - $1"$'\n'"      $2"
}

# ---------------------------------------------------------------------------
# Rule A — user-facing code requires a CHANGELOG entry
# ---------------------------------------------------------------------------

user_facing=""
while IFS= read -r path; do
  [ -n "$path" ] || continue
  case "$path" in
    */tests/*|tests/*) continue ;;
    scripts/ci/*)      continue ;;
    scripts/*|plugins/*) user_facing="$path" ;;
  esac
done <<< "$CHANGED"

if [ -n "$user_facing" ]; then
  if ! changed "CHANGELOG.md" && ! waived "CHANGELOG.md"; then
    note_missing "CHANGELOG.md" \
      "user-facing code changed (e.g. $user_facing) but no changelog entry was added"
  fi
fi

# ---------------------------------------------------------------------------
# Rule B — mapped surfaces must move with the code they describe
# ---------------------------------------------------------------------------

if [ -f "$map_file" ]; then
  while IFS= read -r line || [ -n "$line" ]; do
    # Comments and blanks.
    case "$line" in ''|\#*) continue ;; esac

    pattern="${line%%[[:space:]]*}"
    surface="${line#"$pattern"}"
    surface="${surface#"${surface%%[![:space:]]*}"}"
    surface="${surface%"${surface##*[![:space:]]}"}"
    [ -n "$surface" ] || continue

    any_changed_matching "$pattern" || continue
    changed "$surface" && continue
    waived "$surface" && continue

    note_missing "$surface" "required because a file matching '$pattern' changed"
  done < "$map_file"
fi

# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------

if [ -z "$MISSING" ]; then
  echo "check-docs-sync: every affected surface is accounted for"
  exit 0
fi

cat >&2 << EOF
check-docs-sync: unaccounted documentation surfaces

$MISSING

Each surface above must either change in this pull request, or be waived in the
pull request body with a reason of at least $MIN_REASON characters:

  Docs: <path> — <why this change genuinely does not touch that surface>

The mapping lives in .github/docs-map. If an entry is wrong more often than it
is right, change the entry — do not work around it.
EOF
exit 1
