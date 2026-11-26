#!/bin/bash
# skill_fetch.sh — fetch skill files at one pinned commit into a staging dir.
# Used by skill-import, which scans the staged files before installing any.
#
# Usage: skill_fetch.sh <owner/repo> <sha> <staging-dir> <path>...
#
# Each <path> is a directory (fetched recursively) or a file, relative to the
# repo root; files land at the same relative path under <staging-dir>. Every
# request names <sha>, a full 40-hex commit id, so a branch that moves
# between review and install cannot change what is installed.
#
# Prints FETCHED<TAB><path> per file and SKIPPED<TAB><path><TAB>symlink for
# symlinks, which could point outside the skill. Writes
# <staging-dir>/.tcs-import.json: source, sha, paths, files, fetched_at.
#
# Exit: 0 ok, 2 usage (including a non-SHA ref), 3 fetch failed: tree
# truncated, nothing matched, unsafe path or a failed download.

set -u

repo="${1:-}"; sha="${2:-}"; stage="${3:-}"
if [ "$#" -lt 4 ] || [ -z "$repo" ] || [ -z "$stage" ]; then
  echo "usage: skill_fetch.sh <owner/repo> <sha> <staging-dir> <path>..." >&2
  exit 2
fi
shift 3
if ! printf '%s' "$sha" | grep -Eq '^[0-9a-f]{40}$'; then
  echo "skill_fetch: '$sha' is not a full commit SHA; resolve it first (gh api repos/$repo/commits/<ref> -q .sha)" >&2
  exit 2
fi

tree=$(gh api "repos/$repo/git/trees/$sha?recursive=1" 2>/dev/null) || {
  echo "skill_fetch: cannot read the tree of $repo at $sha" >&2; exit 3; }
if [ "$(printf '%s' "$tree" | jq -r '.truncated' 2>/dev/null)" = "true" ]; then
  echo "skill_fetch: the tree of $repo is truncated; fetching would miss files" >&2
  exit 3
fi

entries=$(printf '%s' "$tree" | jq -r '.tree[] | select(.type == "blob") | [.path, .mode] | @tsv' 2>/dev/null) || entries=""

mkdir -p "$stage" || exit 3
files=()
for want in "$@"; do
  want="${want%/}"
  matched=0
  while IFS="$(printf '\t')" read -r path mode; do
    [ -n "$path" ] || continue
    case "$path" in
      "$want"|"$want"/*) ;;
      *) continue ;;
    esac
    matched=1
    case "/$path/" in
      */../*|*/./*) echo "skill_fetch: unsafe path in tree: $path" >&2; exit 3 ;;
    esac
    if [ "$mode" = "120000" ]; then
      printf 'SKIPPED\t%s\tsymlink\n' "$path"
      continue
    fi
    enc=$(jq -rn --arg p "$path" '$p | split("/") | map(@uri) | join("/")')
    mkdir -p "$stage/$(dirname "$path")" || exit 3
    if ! gh api -H 'Accept: application/vnd.github.raw+json' \
         "repos/$repo/contents/$enc?ref=$sha" > "$stage/$path" 2>/dev/null; then
      echo "skill_fetch: download failed: $path" >&2
      exit 3
    fi
    [ "$mode" = "100755" ] && chmod +x "$stage/$path"
    files+=("$path")
    printf 'FETCHED\t%s\n' "$path"
  done <<EOF
$entries
EOF
  if [ "$matched" -eq 0 ]; then
    echo "skill_fetch: nothing at $want in $repo at $sha" >&2
    exit 3
  fi
done

# ${files[@]+...}: an empty array is "unbound" under set -u in bash 3.2.
jq -n --arg source "$repo" --arg sha "$sha" \
  --arg at "$(date -u +%Y-%m-%dT%H:%M:%SZ)" --argjson n "$#" \
  '{source: $source, sha: $sha, fetched_at: $at,
    paths: ($ARGS.positional | .[:$n]),
    files: ($ARGS.positional | .[$n:])}' \
  --args "$@" ${files[@]+"${files[@]}"} > "$stage/.tcs-import.json" || exit 3
