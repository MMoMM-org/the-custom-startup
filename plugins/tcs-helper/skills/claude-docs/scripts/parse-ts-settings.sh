#!/usr/bin/env bash
# parse-ts-settings.sh — extract TypeScript interface fields to a TSV table
#
# Usage: parse-ts-settings.sh <file.ts>
#   env TS_INTERFACE_NAME=<name>  — select a specific interface by name
#
# Output (stdout): TSV with header: name<TAB>type<TAB>default<TAB>description
# [NEEDS REVIEW] hints: stderr (prefixed with "[NEEDS REVIEW] field ...")
# All interface names in file: stderr (one per line, prefixed "interface: <name>")
#
# Exit codes:
#   0 — success (at least one field emitted; markers are OK)
#   1 — file missing
#   2 — no interface found in file
#
# Behaviour:
#   - Reads interface fields (name + type + JSDoc)
#   - Reads paired const DEFAULT_*: <InterfaceName> = { … } for defaults
#   - Missing const value → [NEEDS DEFAULT]
#   - Missing JSDoc → [NEEDS DESCRIPTION]
#   - Generics / keyof / mapped / intersection types → [NEEDS REVIEW]
#   - Union types (A | B) and plain arrays (T[]) → emitted literally
#
# Bash 3.2 compatible: no associative arrays, no mapfile, no ${var,,}.
# macOS awk (One True AWK) compatible.
# Note: multi-line data is passed to awk via a temp file (not -v) to avoid
# the "newline in string" restriction on -v arguments in awk.

# -e omitted: grep/awk/find pipelines return non-zero on no-match; errexit would abort on legitimate empty results.
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
  exit 2
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
    exit 2
  fi
fi

if [ -z "$SELECTED_IFACE" ]; then
  if printf '%s\n' "$INTERFACE_NAMES" | grep -qxF "Settings"; then
    SELECTED_IFACE="Settings"
  else
    SELECTED_IFACE="$(printf '%s\n' "$INTERFACE_NAMES" | head -1)"
  fi
fi

# Always list all interfaces on stderr (one per line, "interface: <name>")
# so the dispatcher can drive AskUserQuestion on multi-interface files.
while IFS= read -r iname; do
  printf 'interface: %s\n' "$iname" >&2
done <<_IFACE_LIST_
$INTERFACE_NAMES
_IFACE_LIST_

IFACE_COUNT="$(printf '%s\n' "$INTERFACE_NAMES" | grep -c '.' || true)"
if [ "$IFACE_COUNT" -gt 1 ]; then
  printf '[INFO] Selected interface: %s  (set TS_INTERFACE_NAME=<name> to override)\n' \
    "$SELECTED_IFACE" >&2
fi

# ---------------------------------------------------------------------------
# Extract const DEFAULT_*: <SELECTED_IFACE> = { … } fields to a temp file.
#
# The temp file holds "fieldname=rawvalue" lines (one per top-level field).
# We write to a file rather than a shell variable so that awk can read it
# as a second input file without hitting the awk -v "newline in string" limit.
# ---------------------------------------------------------------------------
CONST_TMP="$(mktemp "${TMPDIR:-/tmp}/parse-ts-const.XXXXXX")"
# shellcheck disable=SC2064
trap "rm -f '$CONST_TMP'" EXIT

awk -v iface="$SELECTED_IFACE" '
  BEGIN { in_const = 0; depth = 0; buf = "" }

  !in_const {
    # Match: (export )? const <ANYNAME>: <iface> =
    # We build the pattern as a string comparison after splitting the line.
    line = $0
    # Strip leading whitespace and optional "export"
    sub(/^[[:space:]]*(export[[:space:]]+)?/, "", line)
    # Must start with "const "
    if (substr(line, 1, 6) != "const ") next
    sub(/^const[[:space:]]+/, "", line)
    # Skip the const name
    n = split(line, parts, /[[:space:]:=]/)
    # Find the type annotation (first non-empty token after the name)
    # line after name: rest starts after the name token
    name_end = index(line, parts[1]) + length(parts[1])
    rest = substr(line, name_end)
    # Strip whitespace and leading colon
    sub(/^[[:space:]]*:[[:space:]]*/, "", rest)
    # The type name is the next identifier token
    n2 = split(rest, tparts, /[[:space:]=]/)
    tname = tparts[1]
    # Remove trailing non-identifier chars (e.g. trailing comma)
    sub(/[^A-Za-z0-9_].*$/, "", tname)
    if (tname == iface) {
      in_const = 1
      depth    = 0
      buf      = ""
      # Count braces on this declaration line
      line_len = length($0)
      for (ci = 1; ci <= line_len; ci++) {
        ch = substr($0, ci, 1)
        if (ch == "{") depth++
        if (ch == "}" && depth > 0) depth--
      }
    }
    next
  }

  in_const {
    line_len = length($0)
    for (ci = 1; ci <= line_len; ci++) {
      ch = substr($0, ci, 1)
      if (ch == "{") {
        depth++
        if (depth > 1) buf = buf ch
      } else if (ch == "}") {
        if (depth == 1) {
          flush_field(buf)
          buf      = ""
          in_const = 0
          break
        } else {
          depth--
          buf = buf ch
        }
      } else if (ch == "," && depth == 1) {
        flush_field(buf)
        buf = ""
      } else {
        buf = buf ch
      }
    }
  }

  function flush_field(raw,    colon_pos, fname, fval) {
    gsub(/^[[:space:]]+|[[:space:]]+$/, "", raw)
    if (raw == "") return
    if (match(raw, /^\/\//)) return
    colon_pos = index(raw, ":")
    if (colon_pos == 0) return
    fname = substr(raw, 1, colon_pos - 1)
    fval  = substr(raw, colon_pos + 1)
    gsub(/^[[:space:]]+|[[:space:]]+$/, "", fname)
    gsub(/^[[:space:]]+|[[:space:]]+$/, "", fval)
    sub(/[,;][[:space:]]*$/, "", fval)
    gsub(/^[[:space:]]+|[[:space:]]+$/, "", fval)
    if (fname == "") return
    print fname "=" fval
  }
' "$TS_FILE" > "$CONST_TMP"

# ---------------------------------------------------------------------------
# Main awk pass: parse interface fields + JSDoc; look up defaults from
# CONST_TMP (read as ARGV[1] before the main file, using FNR/FILENAME trick).
#
# awk reads two files:
#   File 1 ($CONST_TMP): pre-loads the const lookup table (fname → value)
#   File 2 ($TS_FILE):   the actual TypeScript source
# ---------------------------------------------------------------------------
awk -v target="$SELECTED_IFACE" -v const_file="$CONST_TMP" \
    -v ts_source="$TS_FILE" \
'
  BEGIN {
    in_iface      = 0
    depth         = 0
    in_jsdoc      = 0
    jsdoc_buf     = ""
    pending_jsdoc = ""
    loading_const = 1
    printf "name\ttype\tdefault\tdescription\n"
  }

  # -------------------------------------------------------------------------
  # File 1: load the const key=value pairs into const_val[]
  # -------------------------------------------------------------------------
  loading_const && FILENAME == const_file {
    eq = index($0, "=")
    if (eq > 0) {
      k = substr($0, 1, eq - 1)
      v = substr($0, eq + 1)
      const_val[k] = v
    }
    next
  }

  # Switch to parsing mode once we reach the TS source file
  FILENAME == ts_source { loading_const = 0 }

  # -------------------------------------------------------------------------
  # File 2: TypeScript source — same state machine as before
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

  # --- Single-line JSDoc --------------------------------------------------
  match($0, /^[[:space:]]*\/\*\*.*\*\//) {
    line = $0
    sub(/^[[:space:]]*\/\*\*[[:space:]]*/, "", line)
    sub(/[[:space:]]*\*\/.*$/, "", line)
    sub(/^[[:space:]]*\*[[:space:]]*/, "", line)
    gsub(/[[:space:]]+/, " ", line)
    sub(/^[[:space:]]+|[[:space:]]+$/, "", line)
    pending_jsdoc = line
    in_jsdoc = 0
    jsdoc_buf = ""
    next
  }

  # --- Start of multi-line JSDoc ------------------------------------------
  !in_jsdoc && match($0, /^[[:space:]]*\/\*\*/) {
    in_jsdoc  = 1
    jsdoc_buf = ""
    next
  }

  # --- Inside JSDoc block -------------------------------------------------
  in_jsdoc {
    if (match($0, /\*\//)) {
      line = $0
      sub(/[[:space:]]*\*\/.*$/, "", line)
      sub(/^[[:space:]]*\*[[:space:]]*/, "", line)
      gsub(/[[:space:]]+/, " ", line)
      sub(/^[[:space:]]+|[[:space:]]+$/, "", line)
      if (length(line) > 0) {
        jsdoc_buf = (length(jsdoc_buf) > 0 ? jsdoc_buf " " line : line)
      }
      pending_jsdoc = jsdoc_buf
      in_jsdoc  = 0
      jsdoc_buf = ""
    } else {
      line = $0
      sub(/^[[:space:]]*\*[[:space:]]*/, "", line)
      gsub(/[[:space:]]+/, " ", line)
      sub(/^[[:space:]]+|[[:space:]]+$/, "", line)
      if (length(line) > 0) {
        jsdoc_buf = (length(jsdoc_buf) > 0 ? jsdoc_buf " " line : line)
      }
    }
    next
  }

  # --- Track brace depth / detect interface end ---------------------------
  {
    line_len = length($0)
    exited = 0
    for (ci = 1; ci <= line_len; ci++) {
      ch = substr($0, ci, 1)
      if (ch == "{") depth++
      if (ch == "}") {
        depth--
        if (depth == 0) { in_iface = 0; exited = 1; break }
      }
    }
    if (exited) next
  }

  !in_iface { next }

  # --- Skip blank / comment / lone-brace lines ----------------------------
  /^[[:space:]]*(\{|\})?[[:space:]]*$/ { next }
  /^[[:space:]]*\/\//                  { next }

  # --- Field line ---------------------------------------------------------
  match($0, /^[[:space:]]*(readonly[[:space:]]+)?[A-Za-z_][A-Za-z0-9_]*[?]?[[:space:]]*:/) {
    line = $0
    sub(/^[[:space:]]*(readonly[[:space:]]+)?/, "", line)

    fname = line
    sub(/[?]?[[:space:]]*:.*$/, "", fname)

    ftype = line
    sub(/^[^:]*:[[:space:]]*/, "", ftype)
    sub(/[[:space:]]*[;,][[:space:]]*$/, "", ftype)
    # Guard: strip any = initializer (invalid TS but be defensive)
    eq_pos = index(ftype, " = ")
    if (eq_pos > 0) { ftype = substr(ftype, 1, eq_pos - 1) }
    sub(/[[:space:]]+$/, "", ftype)

    # Type complexity classification
    needs_review = 0
    if (match(ftype, /<[^>]/))                                needs_review = 1
    if (match(ftype, /\[.*[[:space:]]in[[:space:]]/) ||
        match(ftype, /\[.*[[:space:]]in\]/))                  needs_review = 1
    if (match(ftype, /\{[[:space:]]*\[/))                     needs_review = 1
    if (match(ftype, /&/))                                    needs_review = 1
    if (match(ftype, /^keyof[[:space:]]/))                    needs_review = 1

    # Default from const lookup
    fdefault = "[NEEDS DEFAULT]"
    if (fname in const_val) { fdefault = const_val[fname] }

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
  /^[[:space:]]*[^[:space:]]/ { pending_jsdoc = "" }
' "$CONST_TMP" "$TS_FILE"
