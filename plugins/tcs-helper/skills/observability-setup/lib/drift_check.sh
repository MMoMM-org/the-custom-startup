#!/usr/bin/env bash
# skills/observability-setup/lib/drift_check.sh — drift detection for the
# installed observability bundle.
#
# spec 019 (observability rollout across active repos), Phase 1, T1.3.
#
# CONTRACT SOURCE OF TRUTH — deliberately duplicated, not reused:
#   The three-state contract this file implements (OK / MISSING /
#   DRIFT:<installed>) is defined by
#   plugins/tcs-git-helpers/scripts/lib/drift_check.sh:25-41
#   (drift_check_hook_bundle). That function is NOT called from here for
#   two independent reasons:
#     1. It is generic over the marker's FILENAME under a hardcoded
#        `${repo_path}/.githooks/` segment, not over the marker's
#        directory — this bundle lives at
#        $HOME/.claude/observability/, which has no `.githooks` segment
#        to plug in.
#     2. drift_check.sh belongs to plugin tcs-git-helpers; this file
#        belongs to plugin tcs-helper. A repo-wide search found zero
#        cross-plugin `source` lines, and all six plugins are
#        independently installable — sourcing across that boundary would
#        break tcs-helper when installed without tcs-git-helpers.
#   So this file reproduces the contract exactly (maintainer ruling:
#   mirror the contract, not the code) rather than reusing or
#   generalizing the original. If that contract ever changes, this file
#   must be updated by hand to match it.
#
# THE INSTALLED MARKER IS READ LOOSELY, ON PURPOSE (maintainer ruling):
#   T1.1's _read_observability_bundle_version (bundle_version.sh) REJECTS
#   a malformed marker (exit 1, empty stdout) — that strictness exists so
#   a broken marker can never compare *equal* to the expected version.
#   This file does not reuse that reader for the INSTALLED marker: it
#   mirrors the original comparator's own `head -n 1 | tr -d
#   '[:space:]'`, which accepts anything. A malformed installed marker
#   therefore reports `DRIFT:<raw content>` — never `OK` (garbage never
#   equals the expected version, so the "compares equal to a broken
#   marker" hazard T1.1 guards against cannot arise here) and never a
#   fourth state (the remedy for garbage is the same as for stale:
#   reinstall). The expected version, by contrast, SHOULD be read with
#   the strict reader — it is the plugin's own template marker, which is
#   expected to always be well-formed.
#
# Read-only, exit 0 always: the caller decides what to do with the
# result (SDD/SDD-AC-15 — this file implements the comparator half only;
# T4.1 wires drift into the `status` verb).
#
# bash 3.2 (CON-1): no `[[ =~ ]]` here at all, so the \d/\s/\b and bounded-
# quantifier traps do not apply — this file only ever does literal string
# comparison, matching the original.

# Resolve _bundle_install_target_dir() and $_BUNDLE_INSTALL_MARKER_NAME
# from bundle_install.sh rather than hardcoding "$HOME/.claude/observability"
# and the marker filename a second time here.
# shellcheck source=./bundle_install.sh
# shellcheck disable=SC1091
_DRIFT_CHECK_LIB_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" 2>/dev/null && pwd)" || _DRIFT_CHECK_LIB_DIR=""
if [ -n "$_DRIFT_CHECK_LIB_DIR" ]; then
  . "$_DRIFT_CHECK_LIB_DIR/bundle_install.sh" 2>/dev/null
fi

# _drift_check_observability_bundle <expected_version> [<marker_path>]
#
#   Checks whether the installed observability bundle marker matches
#   <expected_version>.
#
#   Inputs:
#     $1: expected_version (string, e.g. "h1")
#     $2: marker_path (optional; defaults to
#         "$(_bundle_install_target_dir)/$_BUNDLE_INSTALL_MARKER_NAME",
#         i.e. the real installed marker under this environment's $HOME)
#
#   Outputs (via stdout):
#     "OK"                 # installed marker matches expected_version
#     "MISSING"            # marker_path does not exist — nothing installed
#     "DRIFT:<installed>"  # installed marker's raw first-line content,
#                          # whitespace-stripped, differs from
#                          # expected_version (stale OR malformed — both
#                          # get the same remedy: reinstall)
#
#   Exit code: 0 (always; caller decides action)
#   Side effects: none (read-only — never writes, never installs)
_drift_check_observability_bundle() {
  local expected_version="$1"
  local marker_path="$2"

  if [ -z "$marker_path" ]; then
    marker_path="$(_bundle_install_target_dir)/$_BUNDLE_INSTALL_MARKER_NAME"
  fi

  if [ ! -f "$marker_path" ]; then
    printf 'MISSING\n'
    return 0
  fi

  local installed
  installed="$(head -n 1 "$marker_path" | tr -d '[:space:]')"
  if [ "$installed" = "$expected_version" ]; then
    printf 'OK\n'
  else
    printf 'DRIFT:%s\n' "$installed"
  fi
  return 0
}
