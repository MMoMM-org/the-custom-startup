#!/usr/bin/env bats
# T5.2 — skills/status/SKILL.md contract test
# Validates the markdown contract for /tcs-git-helpers:status.
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
SKILL_PATH="${PLUGIN_ROOT}/skills/status/SKILL.md"

# ---------------------------------------------------------------------------
# File existence + structure
# ---------------------------------------------------------------------------

@test "SKILL.md exists at plugins/tcs-git-helpers/skills/status/SKILL.md" {
  [ -f "$SKILL_PATH" ]
}

@test "skills/status is a directory (not a flat skill file)" {
  [ -d "${PLUGIN_ROOT}/skills/status" ]
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

@test "frontmatter name is 'status'" {
  awk '/^---$/{c++; next} c==1' "$SKILL_PATH" | grep -E '^name:' | grep -qE 'status'
}

@test "frontmatter has description field" {
  awk '/^---$/{c++; next} c==1' "$SKILL_PATH" | grep -qE '^description:[[:space:]]'
}

@test "frontmatter description mentions 'status' for auto-discovery" {
  awk '/^---$/{c++; next} c==1' "$SKILL_PATH" | grep -E '^description:' | grep -qiE 'status'
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
# Body — required sections
# ---------------------------------------------------------------------------

@test "body has Persona section" {
  grep -qE '^##[[:space:]]+Persona' "$SKILL_PATH"
}

@test "body has Interface section" {
  grep -qE '^##[[:space:]]+Interface' "$SKILL_PATH"
}

@test "body has Constraints section" {
  grep -qE '^##[[:space:]]+Constraints' "$SKILL_PATH"
}

@test "body has Workflow section" {
  grep -qE '^##[[:space:]]+Workflow' "$SKILL_PATH"
}

# ---------------------------------------------------------------------------
# Body — delegation to python backend
# ---------------------------------------------------------------------------

@test "body invokes git_status_audit.py via \${CLAUDE_PLUGIN_ROOT}" {
  grep -qE 'python3[[:space:]]+\$\{CLAUDE_PLUGIN_ROOT\}/scripts/git_status_audit\.py' "$SKILL_PATH"
}

@test "body does NOT re-implement git state-gathering inline (no 'git rev-parse' commands in body)" {
  # State-gathering belongs in the python backend; SKILL.md should delegate.
  # We allow mentions in prose, but disallow actual command invocations.
  ! grep -qE '^[[:space:]]*git[[:space:]]+(status|rev-parse|branch[[:space:]]+--show-current)' "$SKILL_PATH"
}

# ---------------------------------------------------------------------------
# Body — all 4 modes referenced
# ---------------------------------------------------------------------------

@test "body references --brief mode" {
  grep -q -- '--brief' "$SKILL_PATH"
}

@test "body references --cleanup mode" {
  grep -q -- '--cleanup' "$SKILL_PATH"
}

@test "body references --json mode" {
  grep -q -- '--json' "$SKILL_PATH"
}

@test "body references --overrides mode" {
  grep -q -- '--overrides' "$SKILL_PATH"
}

@test "body documents default-mode structured sections (branch / PR / stale / version / suggestions)" {
  # Spec compliance: default mode outputs structured sections
  # (branch, PR state, stale branches, plugin version, suggestions).
  grep -qiE 'branch'                  "$SKILL_PATH"
  grep -qiE 'PR[[:space:]]*state|PR'  "$SKILL_PATH"
  grep -qiE 'stale'                   "$SKILL_PATH"
  grep -qiE 'plugin version|version'  "$SKILL_PATH"
  grep -qiE 'suggestion'              "$SKILL_PATH"
}

# ---------------------------------------------------------------------------
# Constraints — specific guarantees
# ---------------------------------------------------------------------------

@test "constraints note 24h cache-staleness threshold" {
  # Either '24h', 'cache stale', or 'stale-cache' phrasing acceptable.
  grep -qiE '24h|stale[- ]cache|cache.*stale' "$SKILL_PATH"
}

@test "constraints mention worktree-checked-out exclusion for --cleanup" {
  grep -qiE 'worktree' "$SKILL_PATH"
}

@test "body notes graceful degradation when .githooks/ not installed" {
  # Body should mention either "tcs-git-helpers not installed" or pointer to setup skill.
  grep -qiE 'not installed|tcs-git-helpers:setup|run.*setup' "$SKILL_PATH"
}

# ---------------------------------------------------------------------------
# Sanity — no broken markdown
# ---------------------------------------------------------------------------

@test "SKILL.md is non-empty" {
  [ -s "$SKILL_PATH" ]
}

@test "SKILL.md has at least 30 lines (substantive content)" {
  line_count=$(wc -l < "$SKILL_PATH")
  [ "$line_count" -ge 30 ]
}
