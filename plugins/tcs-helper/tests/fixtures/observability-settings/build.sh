#!/bin/bash
# plugins/tcs-helper/tests/fixtures/observability-settings/build.sh
#
# Build synthetic target-repository states for spec 019 Phase 2 (the
# registration editor). T2.1.
#
# Bash 3.2 compatible (CON-1). No network. Idempotent (each scenario rebuilt
# fresh).
#
# Usage: build.sh [OUT_DIR]
#   OUT_DIR - destination root; default = $(mktemp -d ...)
#
# On success: prints OUT_DIR on stdout. Tests consume that path.
#
# WHY A NEW BUILDER RATHER THAN plugins/tcs-git-helpers/tests/fixtures/repos/build.sh:
#   That builder models git-workflow states (merge/rebase/branch topology) for
#   tcs-git-helpers' own commands. These fixtures model `.claude/settings*.json`
#   CONTENT states for tcs-helper's observability-setup feature -- an
#   unrelated axis with an unrelated consumer. Reusing the git-helpers builder
#   would couple two independently-publishable plugins for no shared benefit,
#   and the task instructions reserve plugins/tcs-git-helpers/ from
#   modification here. Helpers below (_init_repo, _commit) intentionally
#   duplicate that file's minimal git-identity pattern rather than sourcing
#   it, matching how build.sh itself is self-contained.
#
# LAYOUT:
#   $OUT_DIR/<scenario>/       - the target directory (a repo, or for
#                                not-a-repository, a plain directory).
#   $OUT_DIR/<scenario>.home/  - a fake $HOME, ONLY for the two scenarios
#                                whose classification depends on the
#                                installed bundle version at
#                                $HOME/.claude/observability/ (see the
#                                foreign-plus-ours-current/-older comment
#                                below for why this pairing exists).
#
# Scenarios produced (plan/phase-2.md T2.1, 13 fixtures: the plan named 10,
# a TDD gate on 2026-09-08 added 3 -- not-a-repository,
# ignored-file-but-not-backup, valid-json-wrong-shape):
#   absent/                          - no settings file
#   empty-object/                    - {}
#   foreign-only/                    - hooks present, none in our namespace
#   foreign-plus-ours-current/       - foreign entries AND ours, bundle at current version
#   foreign-plus-ours-older/         - foreign entries AND ours, bundle at an older version
#   malformed/                       - unparseable (not valid JSON at all)
#   non-ascii/                       - valid, non-ASCII values in foreign content
#   same-event-names-populated/      - foreign entries under the SAME event names we register
#   write-path-not-ignored/          - .claude/settings.local.json NOT ignored by version control
#   already-configured-observability/ - this shipping repo's real hand-made legacy state
#   not-a-repository/                - a plain directory, no .git/
#   ignored-file-but-not-backup/     - settings.local.json ignored by exact name, .bak is not
#   valid-json-wrong-shape/          - parses cleanly, wrong TYPE (hooks a string)
#
# All repos use deterministic identity + timestamps so SHAs are reproducible.

set -euo pipefail

OUT_DIR="${1:-}"
if [ -z "$OUT_DIR" ]; then
  OUT_DIR=$(mktemp -d "${TMPDIR:-/tmp}/tcs-observability-settings-fixtures.XXXXXX")
fi
mkdir -p "$OUT_DIR"

# --- Deterministic identity & dates ---------------------------------------
export GIT_AUTHOR_NAME="tcs-fixture"
export GIT_AUTHOR_EMAIL="fixture@tcs.invalid"
export GIT_COMMITTER_NAME="$GIT_AUTHOR_NAME"
export GIT_COMMITTER_EMAIL="$GIT_AUTHOR_EMAIL"
export GIT_AUTHOR_DATE="2026-01-01T00:00:00+0000"
export GIT_COMMITTER_DATE="$GIT_AUTHOR_DATE"

# Avoid host-config leak (gpgsign, hooksPath, etc.) and a failed `git init`
# falling back to a parent .git/ and leaking commits onto the working branch.
export GIT_CONFIG_GLOBAL=/dev/null
export GIT_CONFIG_SYSTEM=/dev/null

# The real plugin's current bundle version marker (spec-012 pattern, h<N>).
# Read dynamically -- like build_with_tcs_current in the git-helpers
# builder -- so the "current" fixture tracks the real value instead of a
# literal that goes stale the next time the marker is bumped.
_THIS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
_PLUGIN_ROOT="$(cd "$_THIS_DIR/../../.." && pwd)"
_MARKER_FILE="$_PLUGIN_ROOT/templates/observability/tcs-helper-observability-version"
if [ -f "$_MARKER_FILE" ]; then
  CURRENT_BUNDLE_VERSION="$(cat "$_MARKER_FILE")"
else
  CURRENT_BUNDLE_VERSION="h1"
fi
# Deliberately hardcoded, not "current minus one": h0 sorts below any real
# h<N> marker this bundle will ever ship (mirrors build_with_tcs_older's
# fixed v0.9.0 literal in the git-helpers builder).
OLDER_BUNDLE_VERSION="h0"

# --- Helpers ---------------------------------------------------------------

_init_repo() {
  # $1 = repo dir; creates a working repo with main branch, no remote.
  local dir="$1"
  rm -rf "$dir"
  mkdir -p "$dir"
  git -C "$dir" init -q -b main
  git -C "$dir" config commit.gpgsign false
  git -C "$dir" config tag.gpgsign false
  git -C "$dir" config user.name "$GIT_AUTHOR_NAME"
  git -C "$dir" config user.email "$GIT_AUTHOR_EMAIL"
}

_commit_all() {
  # $1 = repo dir; $2 = subject. Stages everything currently tracked-eligible.
  local dir="$1" subject="$2"
  git -C "$dir" add -A
  git -C "$dir" commit -q -m "$subject"
}

_init_scenario() {
  # $1=repo dir  $2=fixture label  $3=gitignore content (default ".claude/")
  # Common init shape shared by twelve of the thirteen builders below.
  # ${3:-...} rather than $3: phase 1 shipped two libraries that aborted
  # under `set -u` on exactly that mistake (docs/ai/memory/active.md).
  local dir="$1" label="$2" gitignore="${3:-.claude/}"
  _init_repo "$dir"
  printf '%s\n' "$gitignore" > "$dir/.gitignore"
  printf '%s\n' "$label fixture" > "$dir/README.md"
  _commit_all "$dir" "feat: init"
}

# The canonical "ours" registration this feature would write (SDD's
# Runtime View example, byte-for-byte): three hook entries plus the env
# switch, commands pointing into $HOME/.claude/observability/. This string
# is IDENTICAL regardless of which bundle version is installed there --
# ADR-5 deliberately keeps the command opaque to version, so
# foreign-plus-ours-current and foreign-plus-ours-older below ship this
# exact same JSON and differ only in the paired $HOME fixture.
_ours_hooks_json() {
  cat <<'EOF'
  "env": { "CLAUDE_OBSERVABILITY_ENABLED": "1" },
  "hooks": {
    "InstructionsLoaded": [{ "matcher": "", "hooks": [
      { "type": "command", "command": "\"$HOME/.claude/observability/log_instructions.sh\"" }]}],
    "PreToolUse": [{ "matcher": "Skill", "hooks": [
      { "type": "command", "command": "\"$HOME/.claude/observability/log_skill.sh\"" }]}],
    "SubagentStart": [{ "matcher": "", "hooks": [
      { "type": "command", "command": "\"$HOME/.claude/observability/log_agent.sh\"" }]}]
  }
EOF
}

# A foreign hook block: some other tool's registration, never touching our
# namespace. Reused verbatim across several fixtures so the sanity tests can
# grep for one known marker string ("/opt/foreign-audit/hook.sh").
_foreign_hooks_json() {
  cat <<'EOF'
  "hooks": {
    "PreToolUse": [{ "matcher": "Bash", "hooks": [
      { "type": "command", "command": "/opt/foreign-audit/hook.sh" }]}]
  }
EOF
}

# Same shape as _foreign_hooks_json but under the exact event names our
# registration uses (InstructionsLoaded, PreToolUse, SubagentStart) -- for
# same-event-names-populated. Still zero entries in our namespace.
_foreign_hooks_same_events_json() {
  cat <<'EOF'
  "hooks": {
    "InstructionsLoaded": [{ "matcher": "", "hooks": [
      { "type": "command", "command": "/opt/foreign-audit/on-load.sh" }]}],
    "PreToolUse": [{ "matcher": "Write", "hooks": [
      { "type": "command", "command": "/opt/foreign-audit/hook.sh" }]}],
    "SubagentStart": [{ "matcher": "", "hooks": [
      { "type": "command", "command": "/opt/foreign-audit/on-subagent.sh" }]}]
  }
EOF
}

# _foreign_hooks_json and _ours_hooks_json each open their own top-level
# "hooks" object; concatenating them verbatim into one JSON document would
# produce two "hooks" keys in the same object, which every JSON parser
# resolves last-wins -- silently dropping the foreign entry these fixtures
# exist to model. This helper merges the two into ONE "hooks" object, same
# shape as _foreign_hooks_same_events_json: the foreign entry sits in
# PreToolUse alongside ours (Bash matcher next to Skill), following how
# same-event-names-populated already models two entries under one event
# name. Used by foreign-plus-ours-current/-older, which ship this exact
# same JSON (ADR-5 keeps the command opaque to bundle version) and differ
# only in the paired $HOME fixture.
_foreign_plus_ours_hooks_json() {
  cat <<'EOF'
  "env": { "CLAUDE_OBSERVABILITY_ENABLED": "1" },
  "hooks": {
    "InstructionsLoaded": [{ "matcher": "", "hooks": [
      { "type": "command", "command": "\"$HOME/.claude/observability/log_instructions.sh\"" }]}],
    "PreToolUse": [
      { "matcher": "Bash", "hooks": [
        { "type": "command", "command": "/opt/foreign-audit/hook.sh" }]},
      { "matcher": "Skill", "hooks": [
        { "type": "command", "command": "\"$HOME/.claude/observability/log_skill.sh\"" }]}
    ],
    "SubagentStart": [{ "matcher": "", "hooks": [
      { "type": "command", "command": "\"$HOME/.claude/observability/log_agent.sh\"" }]}]
  }
EOF
}

# --- Scenario 1: absent -----------------------------------------------------
build_absent() {
  local repo="$OUT_DIR/absent"
  _init_scenario "$repo" "absent"
  # No .claude/ directory at all -- deliberately absent.
}

# --- Scenario 2: empty-object -----------------------------------------------
build_empty_object() {
  local repo="$OUT_DIR/empty-object"
  _init_scenario "$repo" "empty-object"

  mkdir -p "$repo/.claude"
  printf '{}\n' > "$repo/.claude/settings.local.json"
  # Deliberately NOT git-added: this file is gitignored by design (ADR-1).
}

# --- Scenario 3: foreign-only ------------------------------------------------
build_foreign_only() {
  local repo="$OUT_DIR/foreign-only"
  _init_scenario "$repo" "foreign-only"

  mkdir -p "$repo/.claude"
  {
    echo "{"
    _foreign_hooks_json
    echo "}"
  } > "$repo/.claude/settings.local.json"
}

# --- Scenario 4: foreign-plus-ours-current ----------------------------------
build_foreign_plus_ours_current() {
  local repo="$OUT_DIR/foreign-plus-ours-current"
  local home="$OUT_DIR/foreign-plus-ours-current.home"

  _init_scenario "$repo" "foreign-plus-ours-current"

  mkdir -p "$repo/.claude"
  {
    echo "{"
    _foreign_plus_ours_hooks_json
    echo "}"
  } > "$repo/.claude/settings.local.json"

  # The paired $HOME: the installed bundle marker is at the CURRENT plugin
  # version, so this repo's "ours" entries classify as ours-current.
  rm -rf "$home"
  mkdir -p "$home/.claude/observability"
  printf '%s\n' "$CURRENT_BUNDLE_VERSION" > "$home/.claude/observability/tcs-helper-observability-version"
}

# --- Scenario 5: foreign-plus-ours-older -------------------------------------
build_foreign_plus_ours_older() {
  local repo="$OUT_DIR/foreign-plus-ours-older"
  local home="$OUT_DIR/foreign-plus-ours-older.home"

  _init_scenario "$repo" "foreign-plus-ours-older"

  mkdir -p "$repo/.claude"
  # Byte-identical registration JSON to foreign-plus-ours-current -- ADR-5
  # keeps the command string opaque to bundle version, so the only thing
  # that distinguishes "current" from "older" is the paired $HOME below.
  {
    echo "{"
    _foreign_plus_ours_hooks_json
    echo "}"
  } > "$repo/.claude/settings.local.json"

  rm -rf "$home"
  mkdir -p "$home/.claude/observability"
  printf '%s\n' "$OLDER_BUNDLE_VERSION" > "$home/.claude/observability/tcs-helper-observability-version"
}

# --- Scenario 6: malformed ---------------------------------------------------
build_malformed() {
  local repo="$OUT_DIR/malformed"
  _init_scenario "$repo" "malformed"

  mkdir -p "$repo/.claude"
  # Deliberately unparseable: truncated mid-object, not just "wrong shape".
  printf '{\n  "hooks": {\n    "InstructionsLoaded": [\n' > "$repo/.claude/settings.local.json"
}

# --- Scenario 7: non-ascii ---------------------------------------------------
build_non_ascii() {
  local repo="$OUT_DIR/non-ascii"
  _init_scenario "$repo" "non-ascii"

  mkdir -p "$repo/.claude"
  cat > "$repo/.claude/settings.local.json" <<'EOF'
{
  "env": { "TEAM_LABEL": "Équipe-Café-日本語" },
  "hooks": {
    "Notification": [{ "matcher": "", "hooks": [
      { "type": "command", "command": "/opt/Café-Tools/notify.sh" }]}]
  }
}
EOF
}

# --- Scenario 8: same-event-names-populated ----------------------------------
build_same_event_names_populated() {
  local repo="$OUT_DIR/same-event-names-populated"
  _init_scenario "$repo" "same-event-names-populated"

  mkdir -p "$repo/.claude"
  {
    echo "{"
    _foreign_hooks_same_events_json
    echo "}"
  } > "$repo/.claude/settings.local.json"
}

# --- Scenario 9: write-path-not-ignored --------------------------------------
build_write_path_not_ignored() {
  local repo="$OUT_DIR/write-path-not-ignored"
  # Ignores something unrelated -- NOT .claude/, NOT settings.local.json.
  _init_scenario "$repo" "write-path-not-ignored" "node_modules/"
  # .claude/settings.local.json intentionally absent: the hazard this
  # fixture proves is about the WRITE PATH's ignore status, independent of
  # whether a file is there yet.
}

# --- Scenario 10: already-configured-observability ---------------------------
# The shipping repository's own real, hand-made state (measured 2026-09-08,
# see plan/phase-2.md T2.1). NOT settings.local.json -- settings.json, which
# is what collides with ADR-1 (write target) and ADR-5 (path namespace):
# these commands point at an in-repo path, not $HOME/.claude/observability/.
# Legacy shape, pending the phase-4 migration; this fixture is the state
# that migration passes through, so it must keep existing after phase 4
# lands, not be deleted.
build_already_configured_observability() {
  local repo="$OUT_DIR/already-configured-observability"
  _init_scenario "$repo" "already-configured-observability"

  mkdir -p "$repo/.claude"
  cat > "$repo/.claude/settings.json" <<'EOF'
{
  "env": { "CLAUDE_OBSERVABILITY_ENABLED": "1" },
  "hooks": {
    "InstructionsLoaded": [{ "matcher": "", "hooks": [
      { "type": "command", "command": "\"$CLAUDE_PROJECT_DIR/plugins/tcs-helper/scripts/observability/log_instructions.sh\"" }]}],
    "PreToolUse": [{ "matcher": "Skill", "hooks": [
      { "type": "command", "command": "\"$CLAUDE_PROJECT_DIR/plugins/tcs-helper/scripts/observability/log_skill.sh\"" }]}],
    "SubagentStart": [{ "matcher": "", "hooks": [
      { "type": "command", "command": "\"$CLAUDE_PROJECT_DIR/plugins/tcs-helper/scripts/observability/log_agent.sh\"" }]}]
  }
}
EOF
  # This repo's settings.local.json genuinely holds no hooks at all --
  # reproduced here, not omitted, so a detector that looks at the wrong
  # file finds nothing and would (wrongly) call this repo clean.
  printf '{\n  "permissions": { "allow": ["Bash(git:*)"] }\n}\n' \
    > "$repo/.claude/settings.local.json"
}

# --- Scenario 11: not-a-repository -------------------------------------------
build_not_a_repository() {
  local dir="$OUT_DIR/not-a-repository"
  rm -rf "$dir"
  mkdir -p "$dir"
  printf '%s\n' "just a directory, no .git/ here" > "$dir/README.md"
  # No git init at all -- distinct from "absent", which IS a repository.
}

# --- Scenario 12: ignored-file-but-not-backup --------------------------------
build_ignored_file_but_not_backup() {
  local repo="$OUT_DIR/ignored-file-but-not-backup"
  # Names the exact file, NOT the directory -- so the sibling .bak path is
  # not covered by this pattern.
  _init_scenario "$repo" "ignored-file-but-not-backup" ".claude/settings.local.json"

  mkdir -p "$repo/.claude"
  printf '{}\n' > "$repo/.claude/settings.local.json"
}

# --- Scenario 13: valid-json-wrong-shape -------------------------------------
build_valid_json_wrong_shape() {
  local repo="$OUT_DIR/valid-json-wrong-shape"
  _init_scenario "$repo" "valid-json-wrong-shape"

  mkdir -p "$repo/.claude"
  # Parses cleanly under json.load -- "hooks" is a string, not an object.
  # Distinct from malformed/, which fails to parse at all.
  printf '{\n  "hooks": "not-an-object"\n}\n' > "$repo/.claude/settings.local.json"
}

# --- Driver -------------------------------------------------------------

build_absent
build_empty_object
build_foreign_only
build_foreign_plus_ours_current
build_foreign_plus_ours_older
build_malformed
build_non_ascii
build_same_event_names_populated
build_write_path_not_ignored
build_already_configured_observability
build_not_a_repository
build_ignored_file_but_not_backup
build_valid_json_wrong_shape

printf '%s\n' "$OUT_DIR"
