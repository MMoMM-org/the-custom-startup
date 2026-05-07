#!/usr/bin/env bash
# scripts/reader-test.sh — orchestrate one claude -p reader simulation
# Args: <persona-id> <question-id> [--dry-run]
#
# Resolves persona description, question text, and pages list from the active
# persona file (project override or built-in default) then invokes claude -p
# with the assembled prompt. In --dry-run mode the prompt is printed to stdout
# without calling claude (useful for testing corpus assembly).
#
# Runtime dependencies:
#   - claude CLI (authenticated): required unless --dry-run is passed.
#   - jq: required for JSON validation.
#   - timeout (GNU coreutils) OR perl: used for per-invocation timeout.
#     On macOS without coreutils installed, perl is used automatically.
#     Install coreutils with: brew install coreutils
#
# Environment variables:
#   READER_TEST_TIMEOUT   Per-invocation timeout in seconds (default: 60).
#   REPO_ROOT_OVERRIDE    Override repo root instead of git rev-parse (tests).
#   PERSONAS_FILE         Override the active persona file path (tests).
#                         T2.5 sets this when pointing reader-test at a merged
#                         persona set assembled by resolve_active_persona_set.
#
# Exit codes:
#   0  Successful completion (includes infrastructure errors — see JSON .error).
#   1  Configuration error: bad persona/question ID, malformed personas file,
#      or missing prereq (claude CLI, jq).
#
# Bash 3.2 compatible: no associative arrays, no mapfile, no ${var,,}.
# macOS awk (One True AWK 20200816) compatible.

set -euo pipefail

# ---------------------------------------------------------------------------
# Arguments
# ---------------------------------------------------------------------------
PERSONA_ID="${1:?usage: $0 <persona-id> <question-id> [--dry-run]}"
QUESTION_ID="${2:?usage: $0 <persona-id> <question-id> [--dry-run]}"
DRY_RUN=0
if [ "${3:-}" = "--dry-run" ]; then
  DRY_RUN=1
fi

READER_TEST_TIMEOUT="${READER_TEST_TIMEOUT:-60}"

# ---------------------------------------------------------------------------
# Locate lib-personas.sh from BASH_SOURCE (sibling in scripts/)
# ---------------------------------------------------------------------------
_script_dir() {
  cd "$(dirname "${BASH_SOURCE[0]}")" && pwd
}
SCRIPT_DIR="$(_script_dir)"
LIB="${SCRIPT_DIR}/lib-personas.sh"

if [ ! -f "$LIB" ]; then
  printf 'ERROR: lib-personas.sh not found at %s\n' "$LIB" >&2
  exit 1
fi

# shellcheck disable=SC1090,SC1091
source "$LIB"

# ---------------------------------------------------------------------------
# Repo root (REPO_ROOT_OVERRIDE for tests; lib exports _repo_root)
# ---------------------------------------------------------------------------
REPO_ROOT="$(_repo_root)"

# ---------------------------------------------------------------------------
# Prereq checks — exit non-zero before any subprocess call
# ---------------------------------------------------------------------------

# jq is required for JSON validation
if ! command -v jq >/dev/null 2>&1; then
  printf 'ERROR: jq is required but not on PATH; install with: brew install jq\n' >&2
  exit 1
fi

# claude CLI is required unless --dry-run
if [ "$DRY_RUN" -eq 0 ]; then
  if ! command -v claude >/dev/null 2>&1; then
    # SC2016: backticks in this string are literal (doc links), not expansions
    # shellcheck disable=SC2016
    printf 'ERROR: review mode requires the `claude` CLI; install via `npm install -g @anthropic-ai/claude-code` and authenticate with `claude /login`\n' >&2
    exit 1
  fi
fi

# ---------------------------------------------------------------------------
# Resolve and validate active persona file
# ---------------------------------------------------------------------------
if [ -n "${PERSONAS_FILE:-}" ]; then
  ACTIVE_PERSONAS="$PERSONAS_FILE"
else
  ACTIVE_PERSONAS="$(resolve_personas_file)"
fi

validate_personas_file "$ACTIVE_PERSONAS" || exit 1

# ---------------------------------------------------------------------------
# Extract persona description and question data
# ---------------------------------------------------------------------------
PERSONA_DESC="$(get_persona_description "$PERSONA_ID" "$ACTIVE_PERSONAS")"
if [ -z "$PERSONA_DESC" ]; then
  printf 'ERROR: persona "%s" not found in %s\n' "$PERSONA_ID" "$ACTIVE_PERSONAS" >&2
  exit 1
fi

QUESTION_TEXT="$(get_question_text "$PERSONA_ID" "$QUESTION_ID" "$ACTIVE_PERSONAS")"
if [ -z "$QUESTION_TEXT" ]; then
  printf 'ERROR: question "%s" not found for persona "%s" in %s\n' \
    "$QUESTION_ID" "$PERSONA_ID" "$ACTIVE_PERSONAS" >&2
  exit 1
fi

PAGES="$(get_question_pages "$PERSONA_ID" "$QUESTION_ID" "$ACTIVE_PERSONAS")"

# ---------------------------------------------------------------------------
# Build DOCUMENT CORPUS
# ---------------------------------------------------------------------------
CORPUS=""
PAGE_COUNT=0

while IFS= read -r page; do
  [ -z "$page" ] && continue
  PAGE_COUNT=$((PAGE_COUNT + 1))
  CORPUS="${CORPUS}===== BEGIN PAGE: ${page} =====
"
  if [ -f "${REPO_ROOT}/${page}" ]; then
    CORPUS="${CORPUS}$(cat "${REPO_ROOT}/${page}")"
  else
    CORPUS="${CORPUS}(page not found in repo)"
  fi
  CORPUS="${CORPUS}
===== END PAGE: ${page} =====

"
done <<EOF
$PAGES
EOF

# ---------------------------------------------------------------------------
# Assemble prompt
# ---------------------------------------------------------------------------
PROMPT="You are simulating a real user reading documentation. You have NO context
about this project beyond what is in the DOCUMENT CORPUS below. You MUST
answer strictly from those pages. If something is implied but not explicit,
mark it as 'guessed'. If something is missing, mark it as 'unclear'.

PERSONA: ${PERSONA_DESC}

DOCUMENT CORPUS (contains ${PAGE_COUNT} page(s) the reader has access to):

${CORPUS}

QUESTION: ${QUESTION_TEXT}

OUTPUT (JSON only, no prose):
{
  \"found\": \"yes\" | \"partial\" | \"no\",
  \"answer\": \"<your best answer from the corpus>\",
  \"unclear\": [\"<item the corpus does not clearly explain>\"],
  \"guessed\": [\"<assumption you had to make>\"],
  \"page_used\": \"<the page where you found the answer, or null>\"
}"

# ---------------------------------------------------------------------------
# Dry-run mode: emit prompt and exit
# ---------------------------------------------------------------------------
if [ "$DRY_RUN" -eq 1 ]; then
  printf '%s\n' "$PROMPT"
  exit 0
fi

# ---------------------------------------------------------------------------
# Timeout wrapper: use GNU timeout if available, fall back to perl
# _run_with_timeout <seconds> <cmd> [args...]
# Exits with 124 on timeout (matches GNU timeout convention).
# ---------------------------------------------------------------------------
_run_with_timeout() {
  local secs="$1"
  shift
  if command -v timeout >/dev/null 2>&1; then
    timeout "$secs" "$@"
    return
  fi
  # Perl fallback for macOS without coreutils
  perl -e '
    my $secs = shift;
    my @cmd  = @ARGV;
    my $pid  = fork();
    die "fork failed: $!" unless defined $pid;
    if ($pid == 0) { exec @cmd or die "exec failed: $!"; }
    local $SIG{ALRM} = sub { kill 9, $pid; waitpid($pid, 0); exit 124; };
    alarm($secs);
    waitpid($pid, 0);
    alarm(0);
    my $status = $?;
    exit($status >> 8);
  ' -- "$secs" "$@"
}

# ---------------------------------------------------------------------------
# Invoke claude -p with timeout
# On any failure (timeout, exit non-zero): emit infra-error JSON, exit 0.
# ---------------------------------------------------------------------------
RESULT=""
if ! RESULT="$(_run_with_timeout "$READER_TEST_TIMEOUT" \
    claude -p --output-format json --max-turns 1 "$PROMPT")"; then
  printf '{"found":"no","answer":null,"unclear":["reader-test infrastructure error"],"guessed":[],"page_used":null,"error":"timeout_or_invocation_failure"}\n'
  exit 0
fi

# ---------------------------------------------------------------------------
# Unwrap claude -p --output-format json envelope and validate inner shape
#
# `claude -p --output-format json` returns a wrapper object:
#   {"type":"result","subtype":"success","result":"<inner-JSON-as-string>",...}
# The model's actual JSON (with .found etc.) is nested under .result as a
# stringified payload. We must:
#   1. Extract .result from the outer wrapper.
#   2. Parse it as JSON via `fromjson`.
#   3. Verify it has the .found field this skill contracts on.
# Any failure (no wrapper, no .result, .result not JSON, no .found) → emit
# the unparseable_response sentinel JSON and exit 0.
# ---------------------------------------------------------------------------
INNER="$(printf '%s\n' "$RESULT" | jq -c 'try (.result | fromjson) catch empty' 2>/dev/null || true)"
if [ -z "$INNER" ] || ! printf '%s\n' "$INNER" | jq -e '.found' >/dev/null 2>&1; then
  printf '{"found":"no","answer":null,"unclear":["reader-test malformed response"],"guessed":[],"page_used":null,"error":"unparseable_response"}\n'
  exit 0
fi

printf '%s\n' "$INNER"
