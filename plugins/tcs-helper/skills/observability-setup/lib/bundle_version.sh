#!/usr/bin/env bash
# skills/observability-setup/lib/bundle_version.sh — read the observability
# bundle's version marker.
#
# spec 019 (observability rollout across active repos), Phase 1, T1.1.
# Adopts the spec-012 bundle-versioning pattern (SDD/ADR-3): a version
# marker beside the bundle's sources, in the same `h<N>` convention as
# plugins/tcs-git-helpers/templates/githooks/tcs-git-helpers-version —
# deliberately not the plugin's semver (see
# plugins/tcs-git-helpers/README.md:34 for why). T1.2's
# lib/bundle_install.sh sources this file to stamp the marker into
# $HOME/.claude/observability/ at install time; a later drift check compares
# an installed copy of this same marker against this one (SDD/ADR-3).
#
# The bundle's *sources* are unrelated and untouched here — this file only
# reads the version marker (templates/observability/
# tcs-helper-observability-version). It does not copy anything.
#
# bash 3.2 compatible (CON-1): PCRE \d/\s/\b and bounded quantifiers
# `^.{m,n}$` silently match nothing inside `[[ =~ ]]` under bash 3.2's regex
# engine (this machine's /bin/bash is 3.2.57, and CI runs a macos-latest
# leg). Uses [[:digit:]] instead.

# _observability_bundle_version [<version_file>]
#
#   $1 (optional): path to the marker file. Defaults to this bundle's own
#   template marker, resolved relative to THIS file's own location (not
#   $CLAUDE_PLUGIN_ROOT, which does not reach every caller — see
#   plugins/tcs-git-helpers/skills/git-setup/lib/install_files.sh:32-35 for
#   the same fallback shape).
#
#   On success: prints the version (e.g. "h1") to stdout, exit 0.
#   On failure: prints a clear, non-empty error to stderr, exit 1, and
#   NOTHING on stdout. An empty string on stdout is deliberately never
#   returned — a drift check comparing an empty string against an expected
#   version would silently treat "absent/broken" as "matches", which is the
#   specific failure this contract guards against.
#
#   The absent-marker and malformed-marker error messages are textually
#   distinguishable (one names "not found", the other "malformed"), so a
#   caller can tell "nothing installed yet" apart from "something is
#   broken".
_observability_bundle_version() {
  local version_file="$1"

  if [ -z "$version_file" ]; then
    local script_dir
    script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    version_file="$script_dir/../../../templates/observability/tcs-helper-observability-version"
  fi

  if [ ! -f "$version_file" ]; then
    printf 'ERROR: observability bundle version marker not found: %s\n' "$version_file" >&2
    return 1
  fi

  # `cat` followed by `$(...)` strips only TRAILING newlines, so an embedded
  # newline from a second line of content survives into $content — exactly
  # what the multi-line check below needs to see.
  local content
  content="$(cat "$version_file")"

  case "$content" in
    *$'\n'*)
      printf 'ERROR: observability bundle version marker malformed (must be a single line): %s\n' "$version_file" >&2
      return 1
      ;;
  esac

  if [[ ! "$content" =~ ^h[[:digit:]]+$ ]]; then
    printf 'ERROR: observability bundle version marker malformed (expected h<N>, got %s): %s\n' "$content" "$version_file" >&2
    return 1
  fi

  printf '%s\n' "$content"
}
