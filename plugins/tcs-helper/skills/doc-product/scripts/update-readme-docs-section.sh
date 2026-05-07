#!/usr/bin/env bash
# scripts/update-readme-docs-section.sh — generate or refresh the consumer
# repo's root README "## Documentation" section based on docs/*.md.
#
# Idempotent: section content is delimited by HTML marker comments so
# subsequent runs can find and rewrite the block precisely without
# touching surrounding README content.
#
# Args:
#   --docs-dir <path>   Directory containing the doc pages (default: $REPO_ROOT/docs)
#   --readme   <path>   README file to update     (default: $REPO_ROOT/README.md)
#   --dry-run           Print proposed result to stdout instead of writing
#   --help              Print usage and exit 0
#
# Environment:
#   REPO_ROOT_OVERRIDE  Override repo root resolution (used by tests)
#
# Page ordering:
#   1. Canonical order if matched: installation, setup, configuration, usage,
#      template-syntax, instructions-json, troubleshooting, faq.
#   2. Anything else: alphabetical, after the canonical pages.
#   3. Excluded by default: README.md (tree index), CLAUDE.md, AGENTS.md,
#      CONSTITUTION.md (AI/project metadata, not user-facing docs).
#
# Page summary extraction (per page):
#   1. H1 (first "# Title" line) → bullet title.
#   2. Blockquote immediately following H1 (consecutive "> " lines, after
#      optional blank lines) → bullet summary. Joined, trimmed, and capped
#      at the first sentence (split on ". ").
#   3. If no blockquote, no summary is emitted (bullet is just the title link).
#
# Insertion behaviour:
#   1. README has marker pair (start + end)        → replace block content.
#   2. README has unmarked "## Documentation"      → emit warning, leave alone.
#   3. README has "## License"                     → insert block before it.
#   4. None of the above                           → append at end of README.
#   5. README does not exist                       → emit notice, exit 0.
#
# Exit codes:
#   0  Action taken or no-op (warnings still exit 0; not a build break).
#   1  Configuration error (bad arguments, unwritable README).
#
# Bash 3.2 compatible. macOS awk (One True AWK) compatible.

set -euo pipefail

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
MARK_START='<!-- doc-product:documentation:start -->'
MARK_END='<!-- doc-product:documentation:end -->'

# Canonical page ordering (one filename stem per line)
CANONICAL_ORDER='installation
setup
configuration
usage
template-syntax
instructions-json
troubleshooting
faq'

# Files in docs/ that are AI/project metadata, not user-facing pages.
# README.md is also excluded (it is the docs-tree index).
EXCLUDED_FILES='README.md
CLAUDE.md
AGENTS.md
CONSTITUTION.md'

# ---------------------------------------------------------------------------
# Arguments
# ---------------------------------------------------------------------------
DOCS_DIR=""
README=""
DRY_RUN=0

_usage() {
  sed -n '2,/^$/p' "$0" | sed 's/^# \{0,1\}//'
}

while [ $# -gt 0 ]; do
  case "$1" in
    --docs-dir)
      DOCS_DIR="${2:?--docs-dir requires an argument}"
      shift 2
      ;;
    --readme)
      README="${2:?--readme requires an argument}"
      shift 2
      ;;
    --dry-run)
      DRY_RUN=1
      shift
      ;;
    --help|-h)
      _usage
      exit 0
      ;;
    *)
      printf 'ERROR: unknown argument: %s\n' "$1" >&2
      exit 1
      ;;
  esac
done

# ---------------------------------------------------------------------------
# Resolve repo root (for default paths)
# ---------------------------------------------------------------------------
REPO_ROOT=""
if [ -n "${REPO_ROOT_OVERRIDE:-}" ]; then
  REPO_ROOT="$REPO_ROOT_OVERRIDE"
elif command -v git >/dev/null 2>&1; then
  REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || true)"
fi
[ -z "$REPO_ROOT" ] && REPO_ROOT="$(pwd)"

[ -z "$DOCS_DIR" ] && DOCS_DIR="${REPO_ROOT}/docs"
[ -z "$README" ]   && README="${REPO_ROOT}/README.md"

# ---------------------------------------------------------------------------
# README absence is a notice, not an error
# ---------------------------------------------------------------------------
if [ ! -f "$README" ]; then
  printf 'NOTICE: README not found at %s — skipping Documentation-section update.\n' "$README"
  exit 0
fi

# ---------------------------------------------------------------------------
# docs/ absence is a notice, not an error (mode might run before write)
# ---------------------------------------------------------------------------
if [ ! -d "$DOCS_DIR" ]; then
  printf 'NOTICE: docs/ directory not found at %s — skipping Documentation-section update.\n' "$DOCS_DIR"
  exit 0
fi

# ---------------------------------------------------------------------------
# Build sorted list of pages
# ---------------------------------------------------------------------------
_list_pages() {
  # All docs/*.md files, basename only, excluding metadata files
  ls -1 "$DOCS_DIR"/*.md 2>/dev/null \
    | while IFS= read -r f; do
        base="$(basename "$f")"
        if printf '%s\n' "$EXCLUDED_FILES" | grep -Fxq "$base"; then
          continue
        fi
        printf '%s\n' "$base"
      done
}

PAGES_RAW="$(_list_pages)"
if [ -z "$PAGES_RAW" ]; then
  printf 'NOTICE: no pages found in %s — skipping Documentation-section update.\n' "$DOCS_DIR"
  exit 0
fi

# Sort: canonical order first, then alphabetical for the rest
_sort_pages() {
  local input="$1"
  # Emit canonical-order pages first
  local stem
  while IFS= read -r stem; do
    [ -z "$stem" ] && continue
    if printf '%s\n' "$input" | grep -Fxq "${stem}.md"; then
      printf '%s.md\n' "$stem"
    fi
  done <<EOF
$CANONICAL_ORDER
EOF
  # Then anything else, alphabetical
  printf '%s\n' "$input" | sort | while IFS= read -r p; do
    [ -z "$p" ] && continue
    stem="${p%.md}"
    if ! printf '%s\n' "$CANONICAL_ORDER" | grep -Fxq "$stem"; then
      printf '%s\n' "$p"
    fi
  done
}

PAGES_SORTED="$(_sort_pages "$PAGES_RAW")"

# ---------------------------------------------------------------------------
# Per-page metadata: title (H1) + optional one-line summary (blockquote)
# ---------------------------------------------------------------------------
_extract_title() {
  awk '/^# / { sub(/^# /, ""); print; exit }' "$1"
}

_extract_summary() {
  # Capture consecutive "> " lines that follow the H1 (after optional blanks),
  # collapse whitespace, then truncate to the first sentence (split on ". ").
  awk '
    /^# / { saw_h1 = 1; next }
    saw_h1 && !done {
      if ($0 ~ /^[[:space:]]*$/) {
        if (collecting) { done = 1 }
        next
      }
      if ($0 ~ /^> /) {
        line = $0
        sub(/^> ?/, "", line)
        if (out == "") { out = line } else { out = out " " line }
        collecting = 1
        next
      }
      done = 1
    }
    END { if (out != "") print out }
  ' "$1" \
    | sed -E 's/[[:space:]]+/ /g; s/^[[:space:]]+|[[:space:]]+$//g' \
    | awk '
        {
          # Truncate to first sentence: search for ". " and cut there, keeping the period.
          idx = index($0, ". ")
          if (idx > 0) {
            print substr($0, 1, idx)
          } else {
            print
          }
        }
      '
}

# ---------------------------------------------------------------------------
# Build the section content (without markers)
# ---------------------------------------------------------------------------
_build_section_body() {
  printf '## Documentation\n\n'
  while IFS= read -r page; do
    [ -z "$page" ] && continue
    title="$(_extract_title "${DOCS_DIR}/${page}")"
    [ -z "$title" ] && title="${page%.md}"
    summary="$(_extract_summary "${DOCS_DIR}/${page}")"
    if [ -n "$summary" ]; then
      printf -- '- [%s](docs/%s) — %s\n' "$title" "$page" "$summary"
    else
      printf -- '- [%s](docs/%s)\n' "$title" "$page"
    fi
  done <<EOF
$PAGES_SORTED
EOF
}

SECTION_BODY="$(_build_section_body)"

# Wrap with markers
NEW_BLOCK="${MARK_START}
${SECTION_BODY}
${MARK_END}"

# ---------------------------------------------------------------------------
# Mutate the README
# ---------------------------------------------------------------------------
HAS_MARKED=0
HAS_UNMARKED=0
HAS_LICENSE=0

grep -Fq "$MARK_START" "$README" && grep -Fq "$MARK_END" "$README" && HAS_MARKED=1

if [ "$HAS_MARKED" -eq 0 ]; then
  # Look for a non-marked "## Documentation" heading (must NOT be inside a marker block)
  if grep -Eq '^## Documentation([[:space:]]|$)' "$README"; then
    HAS_UNMARKED=1
  fi
fi

grep -Eq '^## License([[:space:]]|$)' "$README" && HAS_LICENSE=1

_render_replace() {
  # Replace content between (and including) the marker pair.
  # macOS awk forbids newlines in -v values, so we pass the block via a file.
  local block_file
  block_file="$(_block_file)"
  awk -v block_file="$block_file" -v ms="$MARK_START" -v me="$MARK_END" '
    index($0, ms) {
      while ((getline line < block_file) > 0) print line
      close(block_file)
      in_block = 1
      next
    }
    in_block && index($0, me) { in_block = 0; next }
    !in_block { print }
  ' "$README"
}

_render_insert_before_license() {
  local block_file
  block_file="$(_block_file)"
  awk -v block_file="$block_file" '
    !inserted && /^## License([[:space:]]|$)/ {
      while ((getline line < block_file) > 0) print line
      close(block_file)
      print ""
      inserted = 1
    }
    { print }
  ' "$README"
}

# Lazy-create a temp file holding NEW_BLOCK; cleanup via global trap.
_BLOCK_FILE=""
_block_file() {
  if [ -z "$_BLOCK_FILE" ]; then
    _BLOCK_FILE="${TMPDIR:-/tmp}/doc-product-block-$$.txt"
    printf '%s\n' "$NEW_BLOCK" > "$_BLOCK_FILE"
  fi
  printf '%s\n' "$_BLOCK_FILE"
}
trap '[ -n "${_BLOCK_FILE:-}" ] && rm -f "$_BLOCK_FILE"' EXIT

_render_append() {
  cat "$README"
  # Ensure exactly one blank line before the new block
  if [ -n "$(tail -c 1 "$README")" ]; then
    printf '\n'
  fi
  printf '\n%s\n' "$NEW_BLOCK"
}

ACTION=""
NEW_CONTENT=""

if [ "$HAS_UNMARKED" -eq 1 ]; then
  printf 'WARNING: README has a "## Documentation" heading but no doc-product markers.\n' >&2
  printf '         Refusing to overwrite hand-written content. Wrap your section with:\n' >&2
  printf '           %s\n' "$MARK_START" >&2
  printf '           ## Documentation\n           ...\n           %s\n' "$MARK_END" >&2
  printf '         to enable automatic refresh on subsequent /doc-product runs.\n' >&2
  exit 0
fi

if [ "$HAS_MARKED" -eq 1 ]; then
  ACTION="UPDATE"
  NEW_CONTENT="$(_render_replace)"
elif [ "$HAS_LICENSE" -eq 1 ]; then
  ACTION="INSERT (before ## License)"
  NEW_CONTENT="$(_render_insert_before_license)"
else
  ACTION="APPEND"
  NEW_CONTENT="$(_render_append)"
fi

if [ "$DRY_RUN" -eq 1 ]; then
  printf '%s\n' "$NEW_CONTENT"
  printf '\n--- ACTION: %s ---\n' "$ACTION" >&2
  exit 0
fi

# Atomic write: stage to sibling temp file, then mv
TMP_OUT="${README}.doc-product.tmp.$$"
printf '%s\n' "$NEW_CONTENT" > "$TMP_OUT"
mv "$TMP_OUT" "$README"

printf '%s %s\n' "$ACTION" "$README"
