#!/usr/bin/env bash
# lib-personas.sh — persona file resolution and YAML-in-Markdown extraction helpers
# Sourceable library; no top-level side effects.
# Bash 3.2 compatible: no associative arrays, no mapfile, no ${var,,}.
# Portable across One True AWK (macOS) and mawk (Linux): no ! negation
# operator, no != in if/pattern contexts (use == 0 and match() instead), and
# NO {n} interval regexes — mawk 1.3.4 ignores them, which silently breaks
# indentation matching. YAML indentation is fixed-width spaces, so all indent
# anchors use literal spaces (e.g. /^  -/, /^      /) instead of [[:space:]]{n}.
#
# Usage: source this file, then call the exported functions.

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

# _skill_root: absolute path to the skills/doc-product directory.
# Computed from BASH_SOURCE so it works regardless of CWD.
_skill_root() {
  local src
  src="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  printf '%s\n' "$(dirname "$src")"
}

# _repo_root: absolute path to the git repo root (or REPO_ROOT_OVERRIDE if set).
# Tests set REPO_ROOT_OVERRIDE to inject a temp dir without needing git.
_repo_root() {
  if [ -n "${REPO_ROOT_OVERRIDE:-}" ]; then
    printf '%s\n' "$REPO_ROOT_OVERRIDE"
    return 0
  fi
  git rev-parse --show-toplevel 2>/dev/null || pwd
}

# _extract_yaml_body <path>
# Strips the Markdown prose and prints just the YAML body.
# Handles YAML inside a fenced code block (```yaml ... ```).
# Falls back to extracting inline YAML starting at the first "personas:"
# or "extends:" key if no fenced block is present.
# macOS awk note: "started && !in_fence" would fail; use "started { print }"
# since in_fence lines are consumed by "next" before reaching the started rule.
_extract_yaml_body() {
  local path="$1"
  awk '
    /^```yaml/ { in_fence=1; next }
    /^```/     { if (in_fence) { in_fence=0; next } }
    in_fence   { print; next }
    /^(extends:|personas:)/ { started=1 }
    started { print }
  ' "$path"
}

# ---------------------------------------------------------------------------
# Public functions
# ---------------------------------------------------------------------------

# resolve_personas_file
# Prints the absolute path to the active persona file.
# Priority: project override (.claude/doc-personas.md) > built-in default.
resolve_personas_file() {
  local repo_root default_path override_path
  repo_root="$(_repo_root)"
  default_path="$(_skill_root)/templates/personas-default.md"
  override_path="${repo_root}/.claude/doc-personas.md"

  if [ -f "$override_path" ]; then
    printf '%s\n' "$override_path"
  else
    printf '%s\n' "$default_path"
  fi
}

# personas_extends_defaults
# Reads the active persona file.
# Returns 0 (true) if it contains an "extends: defaults" directive; 1 otherwise.
# Only project overrides can have extends:; defaults never reference themselves.
personas_extends_defaults() {
  local active_file default_path
  active_file="$(resolve_personas_file)"
  default_path="$(_skill_root)/templates/personas-default.md"

  if [ "$active_file" = "$default_path" ]; then
    return 1
  fi

  grep -qE '^[[:space:]]*extends:[[:space:]]*defaults[[:space:]]*(#.*)?$' "$active_file"
}

# validate_personas_file <path>
# Parses the YAML body and validates required fields.
# Exits non-zero with a clear stderr message on any violation.
# macOS awk compatibility: uses == 0 instead of !, match() instead of !/pattern/.
validate_personas_file() {
  local path="$1"

  if [ ! -f "$path" ]; then
    printf 'ERROR: persona file not found: %s\n' "$path" >&2
    return 1
  fi

  local yaml
  yaml="$(_extract_yaml_body "$path")"

  if [ -z "$yaml" ]; then
    printf 'ERROR: persona file has no parseable YAML body: %s\n' "$path" >&2
    return 1
  fi

  printf '%s\n' "$yaml" | awk '
    BEGIN {
      persona_id   = ""
      has_required = 0
      has_desc     = 0
      has_questions = 0
      question_id  = ""
      q_has_req    = 0
      q_has_text   = 0
      q_has_pages  = 0
      in_persona   = 0
      in_question  = 0
      q_count      = 0
      errors       = 0
    }

    function flush_question(pid, qid) {
      if (in_question == 0) return
      if (q_has_req == 0) {
        printf "ERROR: persona \"%s\" question \"%s\" missing field: required\n", pid, qid > "/dev/stderr"
        errors++
      }
      if (q_has_text == 0) {
        printf "ERROR: persona \"%s\" question \"%s\" missing field: text\n", pid, qid > "/dev/stderr"
        errors++
      }
      if (q_has_pages == 0) {
        printf "ERROR: persona \"%s\" question \"%s\" missing field: pages\n", pid, qid > "/dev/stderr"
        errors++
      }
    }

    function flush_persona(pid) {
      if (in_persona == 0) return
      if (has_required == 0) {
        printf "ERROR: persona \"%s\" missing field: required\n", pid > "/dev/stderr"
        errors++
      }
      if (has_desc == 0) {
        printf "ERROR: persona \"%s\" missing field: description\n", pid > "/dev/stderr"
        errors++
      }
      if (has_questions == 0) {
        printf "ERROR: persona \"%s\" has no questions list\n", pid > "/dev/stderr"
        errors++
      } else if (q_count == 0) {
        printf "ERROR: persona \"%s\" has zero questions\n", pid > "/dev/stderr"
        errors++
      }
    }

    # Persona-level id line: exactly 2 spaces before "- id:"
    /^  -[[:space:]]+id:[[:space:]]+/ {
      # Skip if indent is 6+ (question-level lines also match the above)
      if (match($0, /^      /)) { next }
      flush_question(persona_id, question_id)
      flush_persona(persona_id)
      in_persona   = 1
      in_question  = 0
      q_count      = 0
      has_required = 0
      has_desc     = 0
      has_questions = 0
      question_id  = ""
      q_has_req    = 0
      q_has_text   = 0
      q_has_pages  = 0
      line = $0
      sub(/^.*id:[[:space:]]+/, "", line)
      persona_id = line
      next
    }

    # Question-level id line: exactly 6 spaces before "- id:"
    /^      -[[:space:]]+id:[[:space:]]+/ {
      flush_question(persona_id, question_id)
      in_question = 1
      q_count++
      q_has_req   = 0
      q_has_text  = 0
      q_has_pages = 0
      line = $0
      sub(/^.*id:[[:space:]]+/, "", line)
      question_id = line
      next
    }

    # Persona-level fields (indent 4)
    /^    required:[[:space:]]/ { if (in_question == 0) has_required = 1 }
    /^    description:/         { if (in_question == 0) has_desc = 1 }
    /^    questions:/           { has_questions = 1 }

    # Question-level fields (indent 8)
    /^        required:[[:space:]]/ { q_has_req = 1 }
    /^        text:[[:space:]]/     { q_has_text = 1 }
    /^        pages:/               { q_has_pages = 1 }

    END {
      flush_question(persona_id, question_id)
      flush_persona(persona_id)
      exit (errors > 0 ? 1 : 0)
    }
  '
}

# list_persona_ids <path>
# Prints persona IDs one per line in source order.
list_persona_ids() {
  local path="$1"
  _extract_yaml_body "$path" | awk '
    /^  -[[:space:]]+id:[[:space:]]+/ {
      if (match($0, /^      /)) { next }
      line = $0
      sub(/^.*id:[[:space:]]+/, "", line)
      print line
    }
  '
}

# list_question_ids <persona_id> <path>
# Prints question IDs for the named persona, one per line.
list_question_ids() {
  local persona_id="$1"
  local path="$2"
  _extract_yaml_body "$path" | awk -v pid="$persona_id" '
    /^  -[[:space:]]+id:[[:space:]]+/ {
      if (match($0, /^      /)) { next }
      line = $0
      sub(/^.*id:[[:space:]]+/, "", line)
      in_persona = (line == pid)
    }
    in_persona && /^      -[[:space:]]+id:[[:space:]]+/ {
      line = $0
      sub(/^.*id:[[:space:]]+/, "", line)
      print line
    }
  '
}

# get_persona_description <persona_id> <path>
# Prints the full multi-line description for the persona.
get_persona_description() {
  local persona_id="$1"
  local path="$2"
  _extract_yaml_body "$path" | awk -v pid="$persona_id" '
    /^  -[[:space:]]+id:[[:space:]]+/ {
      if (match($0, /^      /)) { next }
      line = $0
      sub(/^.*id:[[:space:]]+/, "", line)
      in_persona = (line == pid)
      in_desc = 0
    }
    in_persona && /^    description:/ {
      in_desc = 1
      next
    }
    # End description on the next 4-space field (but not 6-space continuation)
    in_persona && in_desc && /^    [a-z]/ {
      in_desc = 0
    }
    in_persona && in_desc {
      line = $0
      sub(/^      /, "", line)
      printf "%s\n", line
    }
  '
}

# get_question_text <persona_id> <question_id> <path>
# Prints the question text (without surrounding quotes).
get_question_text() {
  local persona_id="$1"
  local question_id="$2"
  local path="$3"
  _extract_yaml_body "$path" | awk -v pid="$persona_id" -v qid="$question_id" '
    /^  -[[:space:]]+id:[[:space:]]+/ {
      if (match($0, /^      /)) { next }
      line = $0
      sub(/^.*id:[[:space:]]+/, "", line)
      in_persona = (line == pid)
      in_question = 0
    }
    in_persona && /^      -[[:space:]]+id:[[:space:]]+/ {
      line = $0
      sub(/^.*id:[[:space:]]+/, "", line)
      in_question = (line == qid)
    }
    in_question && /^        text:[[:space:]]/ {
      line = $0
      sub(/^[[:space:]]*text:[[:space:]]*/, "", line)
      gsub(/^"/, "", line)
      gsub(/"$/, "", line)
      print line
      exit
    }
  '
}

# get_question_pages <persona_id> <question_id> <path>
# Prints the pages list, one path per line.
get_question_pages() {
  local persona_id="$1"
  local question_id="$2"
  local path="$3"
  _extract_yaml_body "$path" | awk -v pid="$persona_id" -v qid="$question_id" '
    /^  -[[:space:]]+id:[[:space:]]+/ {
      if (match($0, /^      /)) { next }
      line = $0
      sub(/^.*id:[[:space:]]+/, "", line)
      in_persona = (line == pid)
      in_question = 0
      in_pages = 0
    }
    in_persona && /^      -[[:space:]]+id:[[:space:]]+/ {
      line = $0
      sub(/^.*id:[[:space:]]+/, "", line)
      in_question = (line == qid)
      in_pages = 0
    }
    in_question && /^        pages:[[:space:]]*\[/ {
      # Inline list: pages: [a, b, c]
      line = $0
      sub(/^[[:space:]]*pages:[[:space:]]*\[/, "", line)
      gsub(/\][[:space:]]*$/, "", line)
      n = split(line, items, /,[[:space:]]*/);
      for (i = 1; i <= n; i++) {
        item = items[i]
        gsub(/^[[:space:]]+/, "", item)
        gsub(/[[:space:]]+$/, "", item)
        if (length(item) > 0) print item
      }
      in_pages = 0
      exit
    }
    in_question && /^        pages:[[:space:]]*$/ {
      in_pages = 1
      next
    }
    in_question && in_pages && /^          -[[:space:]]+/ {
      line = $0
      sub(/^[[:space:]]*-[[:space:]]+/, "", line)
      gsub(/[[:space:]]+$/, "", line)
      print line
    }
    in_question && in_pages && /^        [a-z]/ { in_pages = 0 }
  '
}

# get_question_required <persona_id> <question_id> <path>
# Prints "true" or "false".
get_question_required() {
  local persona_id="$1"
  local question_id="$2"
  local path="$3"
  _extract_yaml_body "$path" | awk -v pid="$persona_id" -v qid="$question_id" '
    /^  -[[:space:]]+id:[[:space:]]+/ {
      if (match($0, /^      /)) { next }
      line = $0
      sub(/^.*id:[[:space:]]+/, "", line)
      in_persona = (line == pid)
      in_question = 0
    }
    in_persona && /^      -[[:space:]]+id:[[:space:]]+/ {
      line = $0
      sub(/^.*id:[[:space:]]+/, "", line)
      in_question = (line == qid)
    }
    in_question && /^        required:[[:space:]]/ {
      line = $0
      sub(/^[[:space:]]*required:[[:space:]]*/, "", line)
      print line
      exit
    }
  '
}

# get_persona_required <persona_id> <path>
# Prints "true" or "false".
get_persona_required() {
  local persona_id="$1"
  local path="$2"
  _extract_yaml_body "$path" | awk -v pid="$persona_id" '
    /^  -[[:space:]]+id:[[:space:]]+/ {
      if (match($0, /^      /)) { next }
      line = $0
      sub(/^.*id:[[:space:]]+/, "", line)
      in_persona = (line == pid)
      in_question = 0
    }
    in_persona && /^      -[[:space:]]+id:[[:space:]]+/ {
      in_question = 1
    }
    in_persona && /^    required:[[:space:]]/ {
      if (in_question == 0) {
        line = $0
        sub(/^[[:space:]]*required:[[:space:]]*/, "", line)
        print line
        exit
      }
    }
  '
}

# ---------------------------------------------------------------------------
# resolve_active_persona_set
# Emits a canonical persona YAML body to stdout per ADR-4 merge rules:
#   - No override     → emit defaults verbatim
#   - Override, no extends: → emit override verbatim (replace)
#   - Override with extends: defaults → merge: start from defaults,
#     replace any default persona whose id matches one in the override,
#     then append any new personas from the override.
# The emitted output is the YAML body only (no Markdown prose wrapper).
# ---------------------------------------------------------------------------
resolve_active_persona_set() {
  local repo_root default_path override_path
  repo_root="$(_repo_root)"
  default_path="$(_skill_root)/templates/personas-default.md"
  override_path="${repo_root}/.claude/doc-personas.md"

  # Case 1: No override — emit defaults verbatim
  if [ ! -f "$override_path" ]; then
    _extract_yaml_body "$default_path"
    return 0
  fi

  # Case 2: Override exists but no extends: — replace entirely
  if personas_extends_defaults; then
    : # fall through to case 3
  else
    _extract_yaml_body "$override_path"
    return 0
  fi

  # Case 3: Override with extends: defaults — merge
  # For each default persona: emit override version if id matches, else emit default.
  # Then append override personas whose id is not in defaults.
  local default_yaml override_yaml
  default_yaml="$(_extract_yaml_body "$default_path")"
  override_yaml="$(_extract_yaml_body "$override_path")"

  # Collect persona IDs from each source (newline-separated)
  local default_ids override_ids
  default_ids="$(printf '%s\n' "$default_yaml" | awk '
    /^  -[[:space:]]+id:[[:space:]]+/ {
      if (match($0, /^      /)) { next }
      line = $0; sub(/^.*id:[[:space:]]+/, "", line); print line
    }
  ')"
  override_ids="$(printf '%s\n' "$override_yaml" | awk '
    /^  -[[:space:]]+id:[[:space:]]+/ {
      if (match($0, /^      /)) { next }
      line = $0; sub(/^.*id:[[:space:]]+/, "", line); print line
    }
  ')"

  # _extract_persona_block <id> <yaml_body>
  # Prints lines from "  - id: <id>" up to (not including) next "  - id:" at indent 2.
  _extract_persona_block() {
    local pid="$1"
    local yaml_body="$2"
    printf '%s\n' "$yaml_body" | awk -v pid="$pid" '
      /^  -[[:space:]]+id:[[:space:]]+/ {
        if (match($0, /^      /)) { next }
        line = $0; sub(/^.*id:[[:space:]]+/, "", line)
        if (line == pid) { printing = 1 } else { if (printing) exit; printing = 0 }
      }
      printing { print }
    '
  }

  printf 'personas:\n'

  # Emit defaults (replaced by override version when id matches)
  local pid
  while IFS= read -r pid; do
    if printf '%s\n' "$override_ids" | grep -qxF "$pid"; then
      _extract_persona_block "$pid" "$override_yaml"
    else
      _extract_persona_block "$pid" "$default_yaml"
    fi
  done <<EOF
$default_ids
EOF

  # Append override-only personas (not present in defaults)
  while IFS= read -r pid; do
    if printf '%s\n' "$default_ids" | grep -qxF "$pid"; then
      : # already emitted above
    else
      _extract_persona_block "$pid" "$override_yaml"
    fi
  done <<EOF
$override_ids
EOF
}
