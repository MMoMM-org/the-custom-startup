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

OUTPUT — return ONE raw JSON object and nothing else. Do NOT wrap it in
Markdown code fences (no \`\`\`json). Do NOT add any prose, explanation, or
text before or after the object. The very first character of your reply must
be { and the very last must be }.
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
    # --foreground lets the TERM signal reach the command directly (it is not
    # put in a separate background process group), so a hung claude is killed
    # promptly. -k sends KILL shortly after TERM to reap a child that ignores
    # TERM. Combined with --strict-mcp-config (no MCP children) and the
    # write-to-file capture below, no grandchild can outlive the timeout.
    timeout -k 5 --foreground "$secs" "$@"
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
#
# Two hardening measures guard against an indefinite hang (see the doc-product
# review-mode post-mortem):
#
#   1. --strict-mcp-config with NO --mcp-config starts the subprocess with ZERO
#      MCP servers. The reader-test never needs tools, and an inherited MCP
#      server (e.g. an `npx mcp-image` child of the *invoking* session) would
#      otherwise be spawned, inherit our capture fd, and outlive `claude`.
#
#   2. We capture stdout into a temp FILE instead of a command-substitution
#      pipe, and feed stdin from /dev/null. `$(...)` blocks until every writer
#      of the pipe closes it, so an orphaned MCP grandchild holding the write
#      end keeps the capture open forever even after `claude` exits and the
#      `timeout` fires. A regular file has no such EOF dependency: `cat` of the
#      file returns immediately regardless of any lingering fd holder.
#
# On any failure (timeout, exit non-zero): emit infra-error JSON, exit 0.
# ---------------------------------------------------------------------------
CLAUDE_OUT="${TMPDIR:-/tmp}/doc-product-reader-$$-${RANDOM}.json"
# shellcheck disable=SC2064
trap 'rm -f "$CLAUDE_OUT"' EXIT

RESULT=""
if _run_with_timeout "$READER_TEST_TIMEOUT" \
    claude -p --output-format json --max-turns 1 --strict-mcp-config "$PROMPT" \
    >"$CLAUDE_OUT" 2>/dev/null </dev/null; then
  RESULT="$(cat "$CLAUDE_OUT")"
else
  printf '{"found":"no","answer":null,"unclear":["reader-test infrastructure error"],"guessed":[],"page_used":null,"error":"timeout_or_invocation_failure"}\n'
  exit 0
fi

# ---------------------------------------------------------------------------
# Recover the model's JSON object from a candidate text payload.
#
# The reader is instructed to emit a bare JSON object, but models sometimes
# wrap it in a ```json fence or surround it with prose. This helper tries, in
# order of preference:
#   1. The payload is already a JSON object carrying .found.
#   2. The body of a fenced code block (```json … ``` or ``` … ```).
#   3. The substring from the first "{" to the last "}" (an object embedded in
#      prose).
# The first candidate that parses to JSON with a .found field wins. Prints the
# compacted object on success; prints nothing and returns 1 on failure.
# Bash 3.2 / macOS awk compatible.
# ---------------------------------------------------------------------------
_extract_reader_json() {
  local raw="$1" candidate

  # 1. Already a JSON object with .found.
  if printf '%s' "$raw" | jq -e '.found' >/dev/null 2>&1; then
    printf '%s' "$raw" | jq -c '.'
    return 0
  fi

  # 2. Body between the first and second Markdown code fence. The toggle skips
  #    the opening fence line (which may carry a language tag like ```json) and
  #    stops collecting at the closing fence.
  candidate="$(printf '%s\n' "$raw" | awk '
    /^[[:space:]]*```/ { fence = 1 - fence; next }
    fence { print }
  ')"
  if [ -n "$candidate" ] && printf '%s' "$candidate" | jq -e '.found' >/dev/null 2>&1; then
    printf '%s' "$candidate" | jq -c '.'
    return 0
  fi

  # 3. First "{" through last "}" — recover an object embedded in prose.
  case "$raw" in
    *'{'*'}'*)
      candidate="{${raw#*\{}"        # from first "{" to end
      candidate="${candidate%\}*}"   # drop from last "}" onward
      candidate="${candidate}}"      # re-append the "}"
      if printf '%s' "$candidate" | jq -e '.found' >/dev/null 2>&1; then
        printf '%s' "$candidate" | jq -c '.'
        return 0
      fi
      ;;
  esac

  return 1
}

# ---------------------------------------------------------------------------
# Unwrap claude -p --output-format json envelope and validate inner shape
#
# `claude -p --output-format json` returns a wrapper object:
#   {"type":"result","subtype":"success","result":"<inner-payload-as-string>",...}
# The model's actual answer (with .found etc.) is nested under .result as a
# stringified payload. We:
#   1. Extract the .result string from the outer wrapper (falling back to the
#      raw response when there is no wrapper or no .result — e.g. an error
#      subtype, or a non-envelope reply).
#   2. Recover a JSON object from that payload via _extract_reader_json, which
#      tolerates ```json fences and prose around the object.
#   3. Verify it has the .found field this skill contracts on.
# Any failure → emit the unparseable_response sentinel JSON and exit 0.
# ---------------------------------------------------------------------------
RAW_PAYLOAD="$(printf '%s\n' "$RESULT" | jq -r 'if type == "object" then (.result // empty) else empty end' 2>/dev/null || true)"
if [ -z "$RAW_PAYLOAD" ]; then
  RAW_PAYLOAD="$RESULT"
fi

INNER="$(_extract_reader_json "$RAW_PAYLOAD" 2>/dev/null || true)"
if [ -z "$INNER" ] || ! printf '%s\n' "$INNER" | jq -e '.found' >/dev/null 2>&1; then
  printf '{"found":"no","answer":null,"unclear":["reader-test malformed response"],"guessed":[],"page_used":null,"error":"unparseable_response"}\n'
  exit 0
fi

printf '%s\n' "$INNER"
