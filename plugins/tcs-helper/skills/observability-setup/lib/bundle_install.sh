#!/usr/bin/env bash
#
# skills/observability-setup/lib/bundle_install.sh — install the
# observability bundle into $HOME/.claude/observability/.
#
# spec 019 (observability rollout across active repos), Phase 1, T1.2.
# SDD/ADR-2: one versioned copy per environment ($HOME covers both the
# container's gitignored docker home and a real host home with a single
# expression), referenced everywhere by the same $HOME-relative command
# string. No absolute path is baked into any target.
#
# SOURCE RESOLUTION (ADR-2, and the precedent it names):
#   The bundle's source is NOT $CLAUDE_PLUGIN_ROOT — this repo has already
#   recorded that variable does not reach a Bash-tool subprocess, which is
#   exactly what this skill's helper scripts run as (spec-018's ADR-1 exists
#   because of that gap). Instead the source is resolved the way
#   git-setup's own lib/install_files.sh resolves its plugin root
#   (plugins/tcs-git-helpers/skills/git-setup/lib/install_files.sh:32-35):
#   relative to THIS FILE's own location, via ${BASH_SOURCE[0]}.
#
#   This file lives one level below the skill's own base directory
#   (skills/observability-setup/lib/, base is skills/observability-setup/),
#   so resolution is two steps: find the skill base directory first, then
#   apply ADR-2's "../../scripts/observability relative to the skill base
#   directory" from there — giving
#   plugins/tcs-helper/scripts/observability/, the one place the bundle
#   sources actually live (never modified by this file — install is a
#   one-way copy FROM there).
#
# WHAT GETS COPIED, AND WHY logwrite.sh IS NOT OPTIONAL:
#   Every adapter in the bundle (log_agent.sh, log_instructions.sh,
#   log_skill.sh, selfcheck.sh, timed-wrapper.sh) self-locates via
#   ${BASH_SOURCE[0]} and sources "logwrite.sh" relative to ITSELF, not via
#   any plugin-root variable. That is exactly what makes copying them
#   elsewhere safe — and exactly why omitting logwrite.sh from the install
#   set would break every one of them silently: each adapter's own
#   CON-4/CON-5 contract makes it fail open (exit 0, nothing on stdout or
#   stderr) when it cannot source its writer, so a bundle missing
#   logwrite.sh looks like "the hook ran and recorded nothing," not an
#   error. README.md is copied too, verbatim, so the installed copy is
#   self-documenting at its new home, not just at the plugin's.
#
# HALF OF THE git-setup PRECEDENT, NOT ALL OF IT:
#   plugins/tcs-git-helpers/skills/git-setup/lib/install_files.sh:104-141 is
#   a three-part idiom: sed-substitute scripts carrying version banners,
#   cp verbatim the ones that must stay byte-equal, then write the version
#   marker atomically (printf > .tmp, then mv). None of the observability
#   bundle's scripts carry a version placeholder, so only the cp-verbatim
#   half and the atomic marker write apply here — running the sed
#   substitution over scripts that must execute byte-identical from their
#   new home would corrupt them.
#
# TEST SEAM (maintainer-pinned): the marker write is its own function,
# _write_bundle_marker <version> <marker_path>, so a test can source this
# file and redefine JUST that function to `return 1` — not shim `mv` on
# PATH (would shadow every other move in the installer) and not a `trap`
# (tests interruption, a different property). _install_observability_bundle
# calls it as the LAST step, after every file has already been copied, so a
# stubbed failure there proves the marker is never left claiming a version
# whose files did not finish installing.
#
# SOURCEABLE AND EXECUTABLE, DELIBERATELY BOTH:
#   Sourcing this file (what the test above needs, and what a skill script
#   that wants to call _install_observability_bundle itself would do) runs
#   ONLY the path resolution and function/variable definitions below —
#   nothing is written to disk as a side effect of sourcing. The guard at
#   the bottom of this file runs the install AND exits with its status, but
#   only when this file is executed directly (bash bundle_install.sh), not
#   when it is sourced. Matches lib/bundle_version.sh: a library file, not
#   a script with unconditional top-level side effects (unlike
#   install_files.sh, which the harness only ever runs as its own process).
#
# bash 3.2 (CON-1): no associative arrays, no ${var^^}. No `[[ =~ ]]` here —
# the version string is opaque to this file; bundle_version.sh already
# validated its shape when it was read.

_BUNDLE_INSTALL_LIB_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" 2>/dev/null && pwd)" || _BUNDLE_INSTALL_LIB_DIR=""

# Skill base directory: one level up from lib/.
_BUNDLE_INSTALL_SKILL_BASE_DIR=""
if [ -n "$_BUNDLE_INSTALL_LIB_DIR" ]; then
  _BUNDLE_INSTALL_SKILL_BASE_DIR="$(cd "$_BUNDLE_INSTALL_LIB_DIR/.." 2>/dev/null && pwd)" || _BUNDLE_INSTALL_SKILL_BASE_DIR=""
fi

# ADR-2's source path, applied from the skill base directory (not from
# lib/, and not from $CLAUDE_PLUGIN_ROOT — see header above).
_BUNDLE_INSTALL_SOURCE_DIR=""
if [ -n "$_BUNDLE_INSTALL_SKILL_BASE_DIR" ]; then
  _BUNDLE_INSTALL_SOURCE_DIR="$(cd "$_BUNDLE_INSTALL_SKILL_BASE_DIR/../../scripts/observability" 2>/dev/null && pwd)" || _BUNDLE_INSTALL_SOURCE_DIR=""
fi

# Reads _read_observability_bundle_version. Ground truth for the marker
# format and its two distinguishable failure modes (absent vs malformed) —
# sourced, never reimplemented.
# shellcheck source=./bundle_version.sh
# shellcheck disable=SC1091
if [ -n "$_BUNDLE_INSTALL_LIB_DIR" ]; then
  . "$_BUNDLE_INSTALL_LIB_DIR/bundle_version.sh" 2>/dev/null
fi

_BUNDLE_INSTALL_MARKER_NAME="tcs-helper-observability-version"

# _bundle_install_target_dir
#
#   Prints the bundle's install directory. Resolved at CALL time, not at
#   source time: a caller installing into another environment's home (a
#   container's gitignored docker home, per ADR-2) may set HOME and call
#   this, or set _BUNDLE_INSTALL_TARGET_DIR to pin an explicit path.
#   _BUNDLE_INSTALL_TARGET_DIR is otherwise unset — this file assigns it
#   nothing at source time — so the default branch below is live for every
#   caller that does not opt into an override.
_bundle_install_target_dir() {
  printf '%s' "${_BUNDLE_INSTALL_TARGET_DIR:-${HOME}/.claude/observability}"
}

# The executable scripts in the bundle (gated by T1.4's CI check; README is
# installed but not gated, so a prose fix does not force a version bump).
_BUNDLE_INSTALL_SCRIPTS="logwrite.sh log_agent.sh log_instructions.sh log_skill.sh selfcheck.sh timed-wrapper.sh"

# The complete install set. Order does not matter (each file is copied
# independently) but logwrite.sh is listed first as documentation of the
# dependency every other entry has on it.
_BUNDLE_INSTALL_FILES="$_BUNDLE_INSTALL_SCRIPTS README.md"

# _write_bundle_marker <version> <marker_path>
#
# Atomic marker write, mirroring install_files.sh:130-132: write
# <marker_path>.tmp, then mv it into place. `mv` within the same directory
# is a single rename on every filesystem this bundle targets, so the
# marker file is never observed in a partially-written state.
#
# Factored out on its own, not inlined into _install_observability_bundle,
# so a test can source this file and redefine exactly this one function —
# the pinned fault-injection seam.
_write_bundle_marker() {
  local version="$1" marker_path="$2"
  printf '%s\n' "$version" > "${marker_path}.tmp" 2>/dev/null || return 1
  mv "${marker_path}.tmp" "$marker_path" 2>/dev/null || return 1
  return 0
}

# _install_observability_bundle
#
# Installs, or updates, the observability bundle at
# $HOME/.claude/observability/. SDD-AC-8: given setup has already run at an
# older bundle version, running it again reports an update rather than an
# install, and the old files are replaced in place, never duplicated —
# every entry in the install set is copy-and-overwrite by a fixed filename,
# so there is nothing that could accumulate as a second copy.
#
# Prints one status line to stdout on success (install vs. already-up-to-
# date vs. updated, per SDD-AC-8) and a one-line, non-empty error to stderr
# identifying the failed step on failure.
#
# Returns 0 on success. Returns 1 if the bundle source directory cannot be
# resolved or is missing, if the source version marker cannot be read, if
# any single file fails to copy, or if the marker write fails — in every
# failure case, nothing under the target directory claims a version that
# does not match what is actually on disk there.
_install_observability_bundle() {
  if [ -z "$_BUNDLE_INSTALL_SOURCE_DIR" ] || [ ! -d "$_BUNDLE_INSTALL_SOURCE_DIR" ]; then
    printf '[observability-setup] ERROR: bundle source directory not found: %s\n' "${_BUNDLE_INSTALL_SOURCE_DIR:-<unresolved>}" >&2
    return 1
  fi

  local new_version
  new_version="$(_read_observability_bundle_version 2>/dev/null)" || new_version=""
  if [ -z "$new_version" ]; then
    printf '[observability-setup] ERROR: could not read the bundle source version marker\n' >&2
    return 1
  fi

  local target_dir; target_dir="$(_bundle_install_target_dir)"
  local marker_path="$target_dir/$_BUNDLE_INSTALL_MARKER_NAME"

  # Read BEFORE any file is touched, so this reflects what was actually
  # installed a moment ago, not a mid-install state.
  local previous_version=""
  if [ -f "$marker_path" ]; then
    previous_version="$(_read_observability_bundle_version "$marker_path" 2>/dev/null)" || previous_version=""
  fi

  mkdir -p "$target_dir" 2>/dev/null || {
    printf '[observability-setup] ERROR: could not create %s\n' "$target_dir" >&2
    return 1
  }

  local f
  for f in $_BUNDLE_INSTALL_FILES; do
    if [ ! -f "$_BUNDLE_INSTALL_SOURCE_DIR/$f" ]; then
      printf '[observability-setup] ERROR: bundle source file missing: %s\n' "$_BUNDLE_INSTALL_SOURCE_DIR/$f" >&2
      return 1
    fi
    # -p: byte-verbatim copy (no sed substitution — see header) that also
    # preserves the source's permission bits, so an adapter that is +x in
    # the plugin stays +x at its installed home instead of silently losing
    # its executable bit on the copy.
    cp -p "$_BUNDLE_INSTALL_SOURCE_DIR/$f" "$target_dir/$f" 2>/dev/null || {
      printf '[observability-setup] ERROR: failed to install %s\n' "$f" >&2
      return 1
    }
  done

  # Last step, deliberately: everything above has already landed on disk,
  # so a failure here (including the fault-injection test's stub) is the
  # ONLY way this function can return non-zero after files were copied —
  # and it is exactly the case that must leave no marker behind.
  if ! _write_bundle_marker "$new_version" "$marker_path"; then
    printf '[observability-setup] ERROR: failed to write the bundle version marker\n' >&2
    return 1
  fi

  if [ -n "$previous_version" ] && [ "$previous_version" != "$new_version" ]; then
    printf '[observability-setup] Updated observability bundle %s -> %s at %s\n' "$previous_version" "$new_version" "$target_dir"
  elif [ -n "$previous_version" ]; then
    printf '[observability-setup] Observability bundle already up to date (%s) at %s\n' "$new_version" "$target_dir"
  else
    printf '[observability-setup] Installed observability bundle %s into %s\n' "$new_version" "$target_dir"
  fi
  return 0
}

# Executed directly (bash bundle_install.sh): perform the install and exit
# with its status. Sourcing this file (the bats test seam, or a caller that
# wants to invoke _install_observability_bundle itself) runs none of this —
# only the definitions above.
if [ "${BASH_SOURCE[0]:-}" = "${0:-}" ]; then
  _install_observability_bundle
  exit $?
fi
