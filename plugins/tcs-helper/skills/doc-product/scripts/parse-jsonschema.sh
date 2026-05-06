#!/usr/bin/env bash
# parse-jsonschema.sh — JSON Schema settings parser
# Bash 3.2 compatible.
#
# Usage: parse-jsonschema.sh <schema.json>
#
# Output: TSV on stdout with header:
#   name<TAB>type<TAB>default<TAB>description
# One row per top-level properties.* field.
#
# Exit codes:
#   0 — success (may include [NEEDS DESCRIPTION] markers)
#   1 — file not found
#   2 — jq not on PATH
#   3 — schema has no top-level "properties" object

set -euo pipefail

# ---------------------------------------------------------------------------
# Dependency check — must run before any file I/O (ADR-5)
# ---------------------------------------------------------------------------
if ! command -v jq > /dev/null 2>&1; then
  printf 'error: jq not found\n' >&2
  printf 'reason: parsing JSON Schema requires jq for safe field extraction\n' >&2
  printf 'install: brew install jq  (macOS)  |  apt-get install jq  (Linux)\n' >&2
  exit 2
fi

# ---------------------------------------------------------------------------
# Argument / file check
# ---------------------------------------------------------------------------
if [ "$#" -lt 1 ]; then
  printf 'usage: parse-jsonschema.sh <schema.json>\n' >&2
  exit 1
fi

SCHEMA_FILE="$1"

if [ ! -f "$SCHEMA_FILE" ]; then
  printf 'error: file not found: %s\n' "$SCHEMA_FILE" >&2
  exit 1
fi

# ---------------------------------------------------------------------------
# Validate that schema has a top-level "properties" object
# ---------------------------------------------------------------------------
has_properties="$(jq 'if .properties and (.properties | type) == "object" then "yes" else "no" end' "$SCHEMA_FILE" -r)"

if [ "$has_properties" != "yes" ]; then
  printf 'error: schema has no top-level "properties" object — cannot extract settings\n' >&2
  exit 3
fi

# ---------------------------------------------------------------------------
# Emit TSV header
# ---------------------------------------------------------------------------
printf 'name\ttype\tdefault\tdescription\n'

# ---------------------------------------------------------------------------
# Walk properties and emit one TSV row per field.
#
# Type resolution (in priority order):
#   1. If "enum" key present: "enum: \"v1\" | \"v2\" | ..."  (quoted JSON strings)
#   2. If "type" is an array: join elements with " | "
#   3. If "type" is a string: use as-is
#   4. No type info: empty string
#
# Default: jq -c renders the value as compact JSON (strings remain quoted).
# Description: field "description" or "[NEEDS DESCRIPTION]" if absent.
# ---------------------------------------------------------------------------
jq -r '
  .properties | to_entries[] |
  .key as $name |
  .value as $prop |

  # --- type resolution ---
  (
    if $prop | has("enum") then
      "enum: " + ([$prop.enum[] | @json] | join(" | "))
    elif $prop | has("type") then
      if ($prop.type | type) == "array" then
        ($prop.type | join(" | "))
      else
        $prop.type
      end
    else
      ""
    end
  ) as $type |

  # --- default resolution ---
  (
    if $prop | has("default") then
      $prop.default | tojson
    else
      ""
    end
  ) as $default |

  # --- description resolution ---
  (
    if $prop | has("description") then
      $prop.description
    else
      "[NEEDS DESCRIPTION]"
    end
  ) as $description |

  [$name, $type, $default, $description] | @tsv
' "$SCHEMA_FILE"
