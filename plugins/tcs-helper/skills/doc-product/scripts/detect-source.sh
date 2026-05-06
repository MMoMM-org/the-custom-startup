#!/usr/bin/env bash
# detect-source.sh — detect settings source files in a repo root
# Bash 3.2 compatible. shellcheck clean.
#
# Usage: detect-source.sh <repo-root>
#
# Output (stdout): one line per detected source, tab-separated:
#   <type>\t<absolute-path>
#
# Types: typescript | jsonschema | pydantic
#
# Exit: always 0. Detection failures (jq missing, etc.) are silently skipped.
#
# Exclusions:
#   - manifest files by name: manifest.json, plugin.json, package.json
#   - pyproject.toml excluded by extension scope (only *.ts, *.json, *.py are scanned)
#   - directories: node_modules/, __pycache__/, .git/, dist/, build/, tests/

set -uo pipefail

# ---------------------------------------------------------------------------
# Arguments
# ---------------------------------------------------------------------------
if [ $# -ne 1 ]; then
  printf 'Usage: detect-source.sh <repo-root>\n' >&2
  exit 1
fi

REPO_ROOT="$1"

if [ ! -d "$REPO_ROOT" ]; then
  printf 'detect-source.sh: directory not found: %s\n' "$REPO_ROOT" >&2
  exit 1
fi

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# Return true if a file basename is a known manifest (to be excluded)
_is_manifest_file() {
  local basename="$1"
  case "$basename" in
    manifest.json|plugin.json|package.json) return 0 ;;
    # defensive: pyproject.toml is .toml so never reaches the *.json filter,
    # but listed here for v2-readiness if .toml scanning is added.
    pyproject.toml) return 0 ;;
  esac
  return 1
}

# ---------------------------------------------------------------------------
# TypeScript detection
# Check for interface keyword: export interface Foo { or interface Foo {
# ---------------------------------------------------------------------------
_detect_typescript() {
  local repo="$1"
  local filepath basename

  while IFS= read -r filepath; do
    [ -z "$filepath" ] && continue

    basename="$(basename "$filepath")"
    _is_manifest_file "$basename" && continue

    # Check for interface declaration (export interface or plain interface)
    if grep -qE \
         '^[[:space:]]*(export[[:space:]]+)?interface[[:space:]]+[A-Za-z_][A-Za-z0-9_]*[[:space:]]*(\{|extends)' \
         "$filepath" 2>/dev/null; then
      printf 'typescript\t%s\n' "$filepath"
    fi
  done < <(find "$repo" \
    \( -name node_modules -o -name __pycache__ -o -name .git \
       -o -name dist -o -name build -o -name tests \) -prune -o \
    -type f -name '*.ts' -print \
    2>/dev/null)
}

# ---------------------------------------------------------------------------
# JSON Schema detection
# Check for top-level object with 'properties' or '$schema' key
# Requires jq; if jq is missing, skip silently (parser handles dep error)
# Excludes known manifest filenames
# ---------------------------------------------------------------------------
_detect_jsonschema() {
  local repo="$1"
  local filepath basename

  # If jq is not available, skip JSON Schema detection entirely
  if ! command -v jq >/dev/null 2>&1; then
    return 0
  fi

  while IFS= read -r filepath; do
    [ -z "$filepath" ] && continue

    basename="$(basename "$filepath")"
    _is_manifest_file "$basename" && continue

    # Use jq to check if the file is a JSON object with 'properties' or '$schema'
    if jq -e 'type == "object" and (has("properties") or has("$schema"))' \
         "$filepath" >/dev/null 2>&1; then
      printf 'jsonschema\t%s\n' "$filepath"
    fi
  done < <(find "$repo" \
    \( -name node_modules -o -name __pycache__ -o -name .git \
       -o -name dist -o -name build -o -name tests \) -prune -o \
    -type f -name '*.json' -print \
    2>/dev/null)
}

# ---------------------------------------------------------------------------
# Pydantic / dataclass detection
# Check for pydantic imports or @dataclass decorator
# ---------------------------------------------------------------------------
_detect_pydantic() {
  local repo="$1"
  local filepath basename

  while IFS= read -r filepath; do
    [ -z "$filepath" ] && continue

    basename="$(basename "$filepath")"
    _is_manifest_file "$basename" && continue

    # Check for pydantic import or dataclass usage
    if grep -qE \
         '^[[:space:]]*(from pydantic[[:space:]]|import pydantic([[:space:]]|$)|@dataclass|from dataclasses[[:space:]])' \
         "$filepath" 2>/dev/null; then
      printf 'pydantic\t%s\n' "$filepath"
    fi
  done < <(find "$repo" \
    \( -name node_modules -o -name __pycache__ -o -name .git \
       -o -name dist -o -name build -o -name tests \) -prune -o \
    -type f -name '*.py' -print \
    2>/dev/null)
}

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
_detect_typescript "$REPO_ROOT"
_detect_jsonschema "$REPO_ROOT"
_detect_pydantic   "$REPO_ROOT"
