#!/usr/bin/env bats
# T5.2 — skills/git-audit/SKILL.md contract test
# Validates the markdown contract for /tcs-git-helpers:git-audit.
# This is a static contract test against SKILL.md text — it does NOT execute
# the skill (Claude Code runtime invokes the skill; the python backend is
# tested separately in Phase 3).
#
# Verifies:
#   - SKILL.md exists and is a directory-style skill (not flat .md)
#   - Frontmatter has required fields (name, description, user-invocable, allowed-tools)
#   - Description includes trigger keywords for auto-discovery
#   - Body delegates state-gathering to git_status_audit.py via ${CLAUDE_PLUGIN_ROOT}
#   - All 4 modes (--brief, --cleanup, --json, --overrides) referenced
#   - Workflow + Constraints sections present
#   - Constraints note worktree-checked-out exclusion for --cleanup
#   - Constraints note 24h cache-staleness threshold
#   - Graceful degradation when .githooks/ not installed

PLUGIN_ROOT="${BATS_TEST_DIRNAME}/../.."
SKILL_PATH="${PLUGIN_ROOT}/skills/git-audit/SKILL.md"

# ---------------------------------------------------------------------------
# File existence + structure
# ---------------------------------------------------------------------------

@test "SKILL.md exists at plugins/tcs-git-helpers/skills/git-audit/SKILL.md" {
  [ -f "$SKILL_PATH" ]
}

@test "skills/git-audit is a directory (not a flat skill file)" {
  [ -d "${PLUGIN_ROOT}/skills/git-audit" ]
}

# ---------------------------------------------------------------------------
# Frontmatter — required fields
# ---------------------------------------------------------------------------

@test "frontmatter is fenced by --- delimiters" {
  head -n 1 "$SKILL_PATH" | grep -qE '^---$'
}

@test "frontmatter has name field" {
  awk '/^---$/{c++; next} c==1' "$SKILL_PATH" | grep -qE '^name:[[:space:]]'
}

@test "frontmatter name is 'git-audit'" {
  awk '/^---$/{c++; next} c==1' "$SKILL_PATH" | grep -E '^name:' | grep -qE 'git-audit'
}

@test "frontmatter has description field" {
  awk '/^---$/{c++; next} c==1' "$SKILL_PATH" | grep -qE '^description:[[:space:]]'
}

@test "frontmatter description mentions 'audit' for auto-discovery" {
  awk '/^---$/{c++; next} c==1' "$SKILL_PATH" | grep -E '^description:' | grep -qiE 'audit'
}

@test "frontmatter description mentions trigger keywords (stale|cleanup|override|branch)" {
  desc=$(awk '/^---$/{c++; next} c==1' "$SKILL_PATH" | grep -E '^description:')
  [[ "$desc" =~ stale|cleanup|override|branch ]]
}

@test "frontmatter has user-invocable: true" {
  awk '/^---$/{c++; next} c==1' "$SKILL_PATH" | grep -qE '^user-invocable:[[:space:]]*true'
}

@test "frontmatter has allowed-tools including Bash" {
  awk '/^---$/{c++; next} c==1' "$SKILL_PATH" | grep -E '^allowed-tools:' | grep -q 'Bash'
}

@test "frontmatter has argument-hint field" {
  awk '/^---$/{c++; next} c==1' "$SKILL_PATH" | grep -qE '^argument-hint:'
}

@test "argument-hint references all 4 mode flags" {
  hint=$(awk '/^---$/{c++; next} c==1' "$SKILL_PATH" | grep -E '^argument-hint:')
  [[ "$hint" == *"--brief"* ]]
  [[ "$hint" == *"--cleanup"* ]]
  [[ "$hint" == *"--json"* ]]
  [[ "$hint" == *"--overrides"* ]]
}

@test "frontmatter is valid YAML (parses without error)" {
  command -v python3 >/dev/null || skip "python3 required"
  python3 -c "
import sys, yaml
text = open('$SKILL_PATH').read()
parts = text.split('---')
if len(parts) < 3:
    sys.exit('frontmatter not fenced')
yaml.safe_load(parts[1])
"
}

# ---------------------------------------------------------------------------
# Skill <-> backend consistency (issue #90)
#
# What used to live here: greps for '## Persona', for each of the four mode
# flags by name, and for the words 'branch', 'stale', 'suggestion', 'worktree',
# '24h'. Those are the string-presence trap — a grep for 'branch' in a skill
# about branches cannot fail for any reason worth knowing about, and all of
# them break on a rewording that changes no behaviour.
#
# The skill's real contract is with the python backend it delegates to. These
# derive the expected set from the backend and from the skill itself, so a
# change on one side that the other does not follow fails the build.
# ---------------------------------------------------------------------------

@test "every flag the backend accepts is documented in the skill" {
  # Ask the script for its own interface rather than grepping its source, so
  # this keeps working if the argparse setup is refactored.
  local flags f missing=""
  flags="$(python3 "${PLUGIN_ROOT}/scripts/git_status_audit.py" --help 2>/dev/null \
             | grep -oE -- '--[a-z][a-z-]+' | sort -u)"
  [ -n "$flags" ] || { echo "could not read --help from the backend" >&2; return 1; }

  for f in $flags; do
    case "$f" in --help) continue ;; esac
    grep -qF -- "$f" "$SKILL_PATH" || missing="$missing $f"
  done
  [ -z "$missing" ] || { echo "backend flags undocumented in SKILL.md:$missing" >&2; return 1; }
}

@test "every helper the skill invokes exists" {
  local paths p rel missing=""
  paths="$(grep -oE '\$\{CLAUDE_PLUGIN_ROOT\}/[A-Za-z0-9._/-]+' "$SKILL_PATH" | sort -u)"
  [ -n "$paths" ] || { echo "skill names no helper scripts at all" >&2; return 1; }

  for p in $paths; do
    rel="${p#\$\{CLAUDE_PLUGIN_ROOT\}/}"
    [ -e "${PLUGIN_ROOT}/${rel}" ] || missing="$missing $rel"
  done
  [ -z "$missing" ] || { echo "skill points at missing paths:$missing" >&2; return 1; }
}

# ---------------------------------------------------------------------------
# Architectural lint — not a behavioural test
#
# Kept because it asserts the ABSENCE of something: state-gathering belongs in
# the python backend, and a skill that starts issuing git commands inline has
# drifted from that decision. Prose mentions are fine; command invocations are
# not.
# ---------------------------------------------------------------------------

@test "lint: skill does not re-implement git state-gathering inline" {
  ! grep -qE '^[[:space:]]*git[[:space:]]+(status|rev-parse|branch[[:space:]]+--show-current)' "$SKILL_PATH"
}

# ---------------------------------------------------------------------------
# Sanity — no broken markdown
# ---------------------------------------------------------------------------

@test "SKILL.md is non-empty" {
  [ -s "$SKILL_PATH" ]
}
