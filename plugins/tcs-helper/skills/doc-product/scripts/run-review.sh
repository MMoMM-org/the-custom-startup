#!/usr/bin/env bash
# scripts/run-review.sh — concurrency-bounded review orchestrator
# Invokes reader-test.sh once per (persona, question) tuple, bounded by
# READER_TEST_PARALLEL (default 4). Aggregates results per SDD §722-748.
#
# Args:
#   --page <path>                    Narrow scope to pages matching <path>
#   --since <ref>                    Narrow scope to git-diff-changed pages
#   --save-active-persona-file <p>   Write merged persona set to <p>
#
# Environment:
#   READER_TEST_PARALLEL   Max concurrent subprocesses (default 4)
#   READER_TEST_TIMEOUT    Per-invocation timeout in seconds (default 60)
#   REPO_ROOT_OVERRIDE     Override git rev-parse (for tests)
#   PERSONAS_FILE          Override active persona file (for tests)
#
# Exit codes:
#   0  PASS (or infra-only, per Fixture-4 rule)
#   1  FAIL (at least one required persona has a required-question fail)
#   2  Configuration error (prereq missing, persona file invalid)
#
# Bash 3.2 compatible: no associative arrays, no mapfile, no wait -n.
# macOS awk compatible.

set -euo pipefail

# ---------------------------------------------------------------------------
# Locate script dir and skill root
# ---------------------------------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LIB="${SCRIPT_DIR}/lib-personas.sh"
READER_TEST="${SCRIPT_DIR}/reader-test.sh"

if [ ! -f "$LIB" ]; then
  printf 'ERROR: lib-personas.sh not found at %s\n' "$LIB" >&2
  exit 2
fi
if [ ! -f "$READER_TEST" ]; then
  printf 'ERROR: reader-test.sh not found at %s\n' "$READER_TEST" >&2
  exit 2
fi

# shellcheck disable=SC1090,SC1091
source "$LIB"

# ---------------------------------------------------------------------------
# Parse arguments
# ---------------------------------------------------------------------------
PAGE_FILTER=""
SINCE_REF=""
SAVE_ACTIVE_PERSONA_FILE=""

while [ $# -gt 0 ]; do
  case "$1" in
    --page)
      PAGE_FILTER="${2:?--page requires an argument}"
      shift 2
      ;;
    --since)
      SINCE_REF="${2:?--since requires an argument}"
      shift 2
      ;;
    --save-active-persona-file)
      SAVE_ACTIVE_PERSONA_FILE="${2:?--save-active-persona-file requires an argument}"
      shift 2
      ;;
    *)
      printf 'ERROR: unknown argument: %s\n' "$1" >&2
      exit 2
      ;;
  esac
done

READER_TEST_PARALLEL="${READER_TEST_PARALLEL:-4}"
READER_TEST_TIMEOUT="${READER_TEST_TIMEOUT:-60}"

# ---------------------------------------------------------------------------
# Prereq checks
# ---------------------------------------------------------------------------
if ! command -v jq >/dev/null 2>&1; then
  printf 'ERROR: jq is required but not on PATH; install with: brew install jq\n' >&2
  exit 2
fi

# SC2016: backtick in message is literal, not a subshell
# shellcheck disable=SC2016
if ! command -v claude >/dev/null 2>&1; then
  printf 'ERROR: review mode requires the `claude` CLI; install via `npm install -g @anthropic-ai/claude-code` and authenticate with `claude /login`\n' >&2
  exit 2
fi

# ---------------------------------------------------------------------------
# Tempdir (sandbox-safe: manual mkdir under known-writable base)
# ---------------------------------------------------------------------------
_make_tmpdir() {
  local base="/tmp/claude-501"
  if [ ! -d "$base" ]; then
    base="${TMPDIR:-/tmp}"
  fi
  local d="${base}/run-review-$$-${RANDOM}"
  mkdir -p "$d"
  printf '%s\n' "$d"
}

TMPDIR_RUN="$(_make_tmpdir)"
# shellcheck disable=SC2064
trap 'rm -rf "$TMPDIR_RUN"' EXIT

# ---------------------------------------------------------------------------
# Resolve active persona set
# ---------------------------------------------------------------------------
ACTIVE_PERSONA_FILE=""

if [ -n "${PERSONAS_FILE:-}" ]; then
  # Test override: use the provided file directly
  ACTIVE_PERSONA_FILE="$PERSONAS_FILE"
else
  # Write merged persona YAML to a temp file so reader-test.sh can consume it
  MERGED_YAML_FILE="${TMPDIR_RUN}/active-personas.md"
  resolve_active_persona_set > "$MERGED_YAML_FILE"

  # Wrap in Markdown fenced block so validate_personas_file and _extract_yaml_body can parse it
  ACTIVE_PERSONA_FILE="${TMPDIR_RUN}/active-personas-wrapped.md"
  printf '# Active Personas\n\n```yaml\n' > "$ACTIVE_PERSONA_FILE"
  cat "$MERGED_YAML_FILE" >> "$ACTIVE_PERSONA_FILE"
  printf '```\n' >> "$ACTIVE_PERSONA_FILE"
fi

# Optionally save the merged persona file
if [ -n "$SAVE_ACTIVE_PERSONA_FILE" ]; then
  cp "$ACTIVE_PERSONA_FILE" "$SAVE_ACTIVE_PERSONA_FILE"
fi

# Validate
if ! validate_personas_file "$ACTIVE_PERSONA_FILE"; then
  exit 2
fi

# ---------------------------------------------------------------------------
# Determine persona source label
# ---------------------------------------------------------------------------
REPO_ROOT="$(_repo_root)"
PERSONA_SOURCE_LABEL="defaults"
if [ -n "${PERSONAS_FILE:-}" ]; then
  PERSONA_SOURCE_LABEL="test fixture"
elif [ -f "${REPO_ROOT}/.claude/doc-personas.md" ]; then
  PERSONA_SOURCE_LABEL="project override at \`.claude/doc-personas.md\`"
fi

# ---------------------------------------------------------------------------
# Resolve scope: collect page paths that are in-scope
# ---------------------------------------------------------------------------
_resolve_scope_pages() {
  if [ -n "$PAGE_FILTER" ]; then
    # Single page filter: normalize to just filename for intersection check
    printf '%s\n' "$PAGE_FILTER"
    return
  fi

  if [ -n "$SINCE_REF" ]; then
    # Pages changed since the given git ref
    git diff --name-only "${SINCE_REF}...HEAD" 2>/dev/null \
      | grep '^docs/.*\.md$' \
      || true
    return
  fi

  # Default: all docs/*.md under the repo root
  find "${REPO_ROOT}/docs" -name '*.md' 2>/dev/null \
    | sed "s|^${REPO_ROOT}/||" \
    | sort \
    || true
}

SCOPE_PAGES="$(_resolve_scope_pages)"

# _page_in_scope <page_path>
# Returns 0 if the page intersects the current scope filter.
_page_in_scope() {
  local page="$1"

  # No filter at all → everything is in scope
  if [ -z "$PAGE_FILTER" ] && [ -z "$SINCE_REF" ]; then
    return 0
  fi

  if [ -z "$SCOPE_PAGES" ]; then
    return 1
  fi

  # Check whether any scope page matches (basename or full path match)
  local page_base
  page_base="$(basename "$page")"
  local scope_line
  while IFS= read -r scope_line; do
    [ -z "$scope_line" ] && continue
    local scope_base
    scope_base="$(basename "$scope_line")"
    if [ "$page" = "$scope_line" ] || [ "$page_base" = "$scope_base" ]; then
      return 0
    fi
  done <<EOF
$SCOPE_PAGES
EOF
  return 1
}

# ---------------------------------------------------------------------------
# Build work plan: (persona_id, question_id) tuples whose pages intersect scope
# ---------------------------------------------------------------------------
WORK_PLAN_FILE="${TMPDIR_RUN}/work-plan.txt"
printf '' > "$WORK_PLAN_FILE"

PERSONA_IDS="$(list_persona_ids "$ACTIVE_PERSONA_FILE")"

PAGES_TESTED_SET="${TMPDIR_RUN}/pages-tested.txt"
printf '' > "$PAGES_TESTED_SET"

while IFS= read -r persona_id; do
  [ -z "$persona_id" ] && continue
  QUESTION_IDS="$(list_question_ids "$persona_id" "$ACTIVE_PERSONA_FILE")"

  while IFS= read -r question_id; do
    [ -z "$question_id" ] && continue
    QUESTION_PAGES="$(get_question_pages "$persona_id" "$question_id" "$ACTIVE_PERSONA_FILE")"

    # Check if any of this question's pages intersects the scope
    INCLUDE=0
    while IFS= read -r qpage; do
      [ -z "$qpage" ] && continue
      if _page_in_scope "$qpage"; then
        INCLUDE=1
        # Record this page as tested
        printf '%s\n' "$qpage" >> "$PAGES_TESTED_SET"
      fi
    done <<EOF
$QUESTION_PAGES
EOF

    if [ "$INCLUDE" -eq 1 ]; then
      printf '%s %s\n' "$persona_id" "$question_id" >> "$WORK_PLAN_FILE"
    fi
  done <<EOF
$QUESTION_IDS
EOF
done <<EOF
$PERSONA_IDS
EOF

# Deduplicate pages tested
PAGES_TESTED=""
if [ -s "$PAGES_TESTED_SET" ]; then
  PAGES_TESTED="$(sort -u "$PAGES_TESTED_SET" | tr '\n' ',' | sed 's/,$//')"
fi

# ---------------------------------------------------------------------------
# Execute work plan with concurrency limit (Bash 3.2: poll jobs -p | wc -l)
# ---------------------------------------------------------------------------
RESULTS_DIR="${TMPDIR_RUN}/results"
mkdir -p "$RESULTS_DIR"

_wait_for_slot() {
  while true; do
    # Count background jobs
    local job_count
    job_count="$(jobs -p 2>/dev/null | wc -l | tr -d ' ')"
    if [ "${job_count:-0}" -lt "$READER_TEST_PARALLEL" ]; then
      break
    fi
    # Poll: wait for any job to finish (Bash 3.2: no wait -n)
    # Sleep briefly to avoid busy-spin
    sleep 0.05
  done
}

while IFS=' ' read -r p_id q_id; do
  [ -z "$p_id" ] && continue
  _wait_for_slot

  (
    OUT_FILE="${RESULTS_DIR}/${p_id}---${q_id}.json"
    result=""
    if result="$(
      PERSONAS_FILE="$ACTIVE_PERSONA_FILE" \
      READER_TEST_TIMEOUT="$READER_TEST_TIMEOUT" \
      bash "$READER_TEST" "$p_id" "$q_id" 2>/dev/null
    )"; then
      printf '%s\n' "$result" > "$OUT_FILE"
    else
      # reader-test exits non-zero only on config errors (bad ID etc.)
      # Treat as infra error to avoid losing the tuple
      printf '{"found":"no","answer":null,"unclear":["reader-test config error"],"guessed":[],"page_used":null,"error":"invocation_error"}\n' > "$OUT_FILE"
    fi
  ) &
done < "$WORK_PLAN_FILE"

# Wait for all background jobs to finish
wait

# ---------------------------------------------------------------------------
# Aggregate results per SDD §722-748
# ---------------------------------------------------------------------------
# Build tuples JSON array and compute outcome

TUPLES_JSON="[]"
OUTCOME="PASS"

# Process each result file
for result_file in "${RESULTS_DIR}"/*.json; do
  [ -f "$result_file" ] || continue

  # Extract persona_id and question_id from filename: persona_id---question_id.json
  filename="$(basename "$result_file" .json)"
  p_id="${filename%---*}"
  q_id="${filename##*---}"

  result_json="$(cat "$result_file")"

  # Determine persona required and question required
  persona_req="$(get_persona_required "$p_id" "$ACTIVE_PERSONA_FILE" 2>/dev/null || printf 'false')"
  question_req="$(get_question_required "$p_id" "$q_id" "$ACTIVE_PERSONA_FILE" 2>/dev/null || printf 'false')"

  # Add tuple to array
  TUPLE_OBJ="$(printf '%s' "$result_json" | jq \
    --arg pid "$p_id" \
    --arg qid "$q_id" \
    --arg preq "$persona_req" \
    --arg qreq "$question_req" \
    '. + {persona_id: $pid, question_id: $qid, persona_required: ($preq == "true"), question_required: ($qreq == "true")}')"

  TUPLES_JSON="$(printf '%s\n%s' "$TUPLES_JSON" "$TUPLE_OBJ" | jq -s '.[0] + [.[1]]')"

  # Apply SDD §722-748 FAIL logic:
  # FAIL iff required persona has required question with found in {partial, no} AND no error
  has_error="$(printf '%s' "$result_json" | jq -r '.error // empty' 2>/dev/null || true)"
  found_val="$(printf '%s' "$result_json" | jq -r '.found // "no"' 2>/dev/null || true)"

  if [ -z "$has_error" ] && \
     [ "$persona_req" = "true" ] && \
     [ "$question_req" = "true" ] && \
     { [ "$found_val" = "no" ] || [ "$found_val" = "partial" ]; }; then
    OUTCOME="FAIL"
  fi
done

# ---------------------------------------------------------------------------
# Emit aggregate JSON to stdout
# ---------------------------------------------------------------------------
printf '%s\n' "$TUPLES_JSON" | jq \
  --arg outcome "$OUTCOME" \
  --arg source "$PERSONA_SOURCE_LABEL" \
  --arg pages "$PAGES_TESTED" \
  '{
    outcome: $outcome,
    persona_source: $source,
    pages_tested: (if ($pages | length) > 0 then ($pages | split(",")) else [] end),
    tuples: .
  }'

# ---------------------------------------------------------------------------
# Exit code: 0=PASS, 1=FAIL
# ---------------------------------------------------------------------------
if [ "$OUTCOME" = "FAIL" ]; then
  exit 1
fi
exit 0
