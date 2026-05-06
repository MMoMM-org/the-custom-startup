#!/usr/bin/env bash
# parse-ts-settings.sh — extract TypeScript interface fields to a TSV table
#
# Usage: parse-ts-settings.sh <file.ts>
#   env TS_INTERFACE_NAME=<name>  — select a specific interface by name
#
# Output (stdout): TSV with header: name<TAB>type<TAB>default<TAB>description
# [NEEDS REVIEW] hints: stderr (prefixed with "[NEEDS REVIEW]")
# Exit 0: success (even if some fields are [NEEDS DESCRIPTION] / [NEEDS REVIEW])
# Exit 1: file missing, no interface block found
#
# Bash 3.2 compatible: no associative arrays, no mapfile, no ${var,,}.
# macOS awk (One True AWK) compatible.

set -uo pipefail

# ---------------------------------------------------------------------------
# ADR-5: dependency check — pure Bash/awk; no external runtime required.
# ---------------------------------------------------------------------------
if ! command -v awk >/dev/null 2>&1; then
  printf 'ERROR: parse-ts-settings.sh requires awk, which was not found on PATH.\n' >&2
  printf '       awk is needed for text processing during TypeScript interface parsing.\n' >&2
  printf '       Install: brew install gawk (macOS) or apt-get install gawk (Linux)\n' >&2
  exit 1
fi

# ---------------------------------------------------------------------------
# Argument validation
# ---------------------------------------------------------------------------
if [ $# -lt 1 ]; then
  printf 'Usage: parse-ts-settings.sh <file.ts>\n' >&2
  exit 1
fi

TS_FILE="$1"

if [ ! -f "$TS_FILE" ]; then
  printf 'ERROR: file not found: %s\n' "$TS_FILE" >&2
  exit 1
fi

# ---------------------------------------------------------------------------
# Discover interface names in the file (preserve source order)
# ---------------------------------------------------------------------------
_find_interface_names() {
  awk '
    /^[[:space:]]*(export[[:space:]]+)?interface[[:space:]]+[A-Za-z_][A-Za-z0-9_]*/ {
      line = $0
      sub(/^[[:space:]]*(export[[:space:]]+)?interface[[:space:]]+/, "", line)
      n = split(line, parts, /[[:space:]{<]/)
      if (n > 0) print parts[1]
    }
  ' "$TS_FILE"
}

INTERFACE_NAMES="$(_find_interface_names)"

if [ -z "$INTERFACE_NAMES" ]; then
  printf 'ERROR: no interface block found in %s\n' "$TS_FILE" >&2
  exit 1
fi

# ---------------------------------------------------------------------------
# Select which interface to parse
# ---------------------------------------------------------------------------
SELECTED_IFACE=""

if [ -n "${TS_INTERFACE_NAME:-}" ]; then
  if printf '%s\n' "$INTERFACE_NAMES" | grep -qxF "$TS_INTERFACE_NAME"; then
    SELECTED_IFACE="$TS_INTERFACE_NAME"
  else
    printf 'ERROR: interface "%s" not found in %s\n' "$TS_INTERFACE_NAME" "$TS_FILE" >&2
    printf '       Available interfaces: %s\n' \
      "$(printf '%s\n' "$INTERFACE_NAMES" | tr '\n' ' ')" >&2
    exit 1
  fi
fi

if [ -z "$SELECTED_IFACE" ]; then
  if printf '%s\n' "$INTERFACE_NAMES" | grep -qxF "Settings"; then
    SELECTED_IFACE="Settings"
  else
    SELECTED_IFACE="$(printf '%s\n' "$INTERFACE_NAMES" | head -1)"
  fi
fi

# List all interfaces on stderr for dispatcher awareness (multi-interface files).
IFACE_COUNT="$(printf '%s\n' "$INTERFACE_NAMES" | grep -c '.' || true)"
if [ "$IFACE_COUNT" -gt 1 ]; then
  printf '[INFO] Multiple interfaces found in %s:\n' "$TS_FILE" >&2
  while IFS= read -r iname; do
    if [ "$iname" = "$SELECTED_IFACE" ]; then
      printf '  -> %s  (selected)\n' "$iname" >&2
    else
      printf '     %s\n' "$iname" >&2
    fi
  done <<_IFACE_LIST_
$INTERFACE_NAMES
_IFACE_LIST_
  printf '[INFO] Set TS_INTERFACE_NAME=<name> to select a different interface.\n' >&2
fi

# ---------------------------------------------------------------------------
# Main parsing: single awk pass over the file.
#
# State machine:
#   in_iface=0 — scanning for the target interface declaration
#   in_iface=1, depth>=0 — inside the interface body
#
# JSDoc accumulation:
#   in_jsdoc=0/1 — inside a /** ... */ block
#   jsdoc_buf — text collected from JSDoc lines
#   pending_jsdoc — completed JSDoc to attach to next field
#
# Type complexity (→ [NEEDS REVIEW]):
#   - Generic: Foo<T>   (match "<" followed by non-">")
#   - Mapped: [K in S]  (match "[" ... "in ")
#   - Intersection: A & B
#   Union (T | U) is simple — emit literal.
#   Plain array (T[]) is simple.
#
# Output: TSV to stdout; [NEEDS REVIEW] hints to /dev/stderr.
# ---------------------------------------------------------------------------
awk -v target="$SELECTED_IFACE" '
  BEGIN {
    in_iface      = 0
    depth         = 0
    in_jsdoc      = 0
    jsdoc_buf     = ""
    pending_jsdoc = ""
    printf "name\ttype\tdefault\tdescription\n"
  }

  # -------------------------------------------------------------------------
  # Before entering the interface: look for its declaration line
  # -------------------------------------------------------------------------
  !in_iface {
    if (match($0, /^[[:space:]]*(export[[:space:]]+)?interface[[:space:]]+/)) {
      iname = $0
      sub(/^[[:space:]]*(export[[:space:]]+)?interface[[:space:]]+/, "", iname)
      n = split(iname, parts, /[[:space:]{<]/)
      iname = (n > 0 ? parts[1] : "")
      if (iname == target) {
        in_iface = 1
        depth    = 0
        # Count braces on the declaration line itself
        line_len = length($0)
        for (ci = 1; ci <= line_len; ci++) {
          ch = substr($0, ci, 1)
          if (ch == "{") depth++
          if (ch == "}" && depth > 0) depth--
        }
      }
    }
    next
  }

  # -------------------------------------------------------------------------
  # Inside interface body (in_iface == 1)
  # -------------------------------------------------------------------------

  # --- Single-line JSDoc: /** ... */ on one line ---------------------------
  match($0, /^[[:space:]]*\/\*\*.*\*\//) {
    line = $0
    sub(/^[[:space:]]*\/\*\*[[:space:]]*/, "", line)
    sub(/[[:space:]]*\*\/.*$/, "", line)
    pending_jsdoc = line
    in_jsdoc = 0
    jsdoc_buf = ""
    next
  }

  # --- Start of multi-line JSDoc block ------------------------------------
  !in_jsdoc && match($0, /^[[:space:]]*\/\*\*/) {
    in_jsdoc = 1
    jsdoc_buf = ""
    next
  }

  # --- Inside JSDoc block -------------------------------------------------
  in_jsdoc {
    if (match($0, /\*\//)) {
      line = $0
      sub(/[[:space:]]*\*\/.*$/, "", line)
      sub(/^[[:space:]]*\*[[:space:]]*/, "", line)
      if (length(line) > 0) {
        jsdoc_buf = (length(jsdoc_buf) > 0 ? jsdoc_buf " " line : line)
      }
      pending_jsdoc = jsdoc_buf
      in_jsdoc = 0
      jsdoc_buf = ""
    } else {
      line = $0
      sub(/^[[:space:]]*\*[[:space:]]*/, "", line)
      if (length(line) > 0) {
        jsdoc_buf = (length(jsdoc_buf) > 0 ? jsdoc_buf " " line : line)
      }
    }
    next
  }

  # --- Track brace depth and detect interface end -------------------------
  # depth starts at 1 (for the opening { of the interface).
  # When depth drops to 0, we have hit the matching closing brace.
  {
    line_len = length($0)
    exited = 0
    for (ci = 1; ci <= line_len; ci++) {
      ch = substr($0, ci, 1)
      if (ch == "{") depth++
      if (ch == "}") {
        depth--
        if (depth == 0) {
          # Hit the closing brace of the interface itself
          in_iface = 0
          exited   = 1
          break
        }
      }
    }
    if (exited) next
  }

  # After brace counting, if we left the interface, skip
  !in_iface { next }

  # --- Skip lines that are only braces, blank, or comments ---------------
  /^[[:space:]]*(\{|\})?[[:space:]]*$/ { next }
  /^[[:space:]]*\/\// { next }

  # --- Field line: [readonly] identifier[?]: <type> [= <default>][;] -----
  match($0, /^[[:space:]]*(readonly[[:space:]]+)?[A-Za-z_][A-Za-z0-9_]*[?]?[[:space:]]*:/) {
    line = $0
    sub(/^[[:space:]]*(readonly[[:space:]]+)?/, "", line)

    # Field name (strip optional ?)
    fname = line
    sub(/[?]?[[:space:]]*:.*$/, "", fname)

    # Everything after the first colon
    after = line
    sub(/^[^:]*:[[:space:]]*/, "", after)
    # Strip trailing semicolons and whitespace
    sub(/[[:space:]]*;[[:space:]]*$/, "", after)
    sub(/[[:space:]]*,[[:space:]]*$/, "", after)

    # Split on " = " for type and default
    fdefault = ""
    ftype    = after
    eq_pos   = index(after, " = ")
    if (eq_pos > 0) {
      ftype    = substr(after, 1, eq_pos - 1)
      fdefault = substr(after, eq_pos + 3)
      sub(/[,;[:space:]]*$/, "", fdefault)
      # Complex default: contains { or (
      if (match(fdefault, /[{(]/)) {
        fdefault = "[NEEDS REVIEW]"
      }
    }

    # Trim trailing whitespace from type
    sub(/[[:space:]]+$/, "", ftype)

    # Type complexity classification
    needs_review = 0
    if (match(ftype, /<[^>]/))           needs_review = 1  # generic
    if (match(ftype, /\[.*in[[:space:]]/) || match(ftype, /\[.*in\]/)) needs_review = 1  # mapped
    if (match(ftype, /\{[[:space:]]*\[/)) needs_review = 1  # mapped shorthand
    if (match(ftype, /&/))               needs_review = 1  # intersection

    fdesc = (length(pending_jsdoc) > 0 ? pending_jsdoc : "[NEEDS DESCRIPTION]")

    if (needs_review) {
      printf "%s\t%s\t%s\t%s\n", fname, "[NEEDS REVIEW]", fdefault, fdesc
      printf "[NEEDS REVIEW] field \"%s\" has unparseable type: %s\n", \
        fname, ftype > "/dev/stderr"
    } else {
      printf "%s\t%s\t%s\t%s\n", fname, ftype, fdefault, fdesc
    }

    pending_jsdoc = ""
    next
  }

  # --- Other non-blank lines reset pending JSDoc --------------------------
  /^[[:space:]]*[^[:space:]]/ {
    pending_jsdoc = ""
  }
' "$TS_FILE"
