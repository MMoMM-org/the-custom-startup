#!/usr/bin/env bash
#
# The Custom Startup — Import Spec
#
# Imports AI-generated content (from Claude.ai, Perplexity, etc.) into a
# spec directory under .start/specs/ as a requirements.md (PRD) or
# solution.md (SDD).
#
# Usage:
#   ./scripts/import-spec.sh [OPTIONS]
#
# Options:
#   --input <file>           Source file (reads from stdin if omitted)
#   --type <prd|sdd>         Document type to create (required)
#   --spec <NNN-name|path>   Target spec directory (interactive if omitted)
#   --new <name>             Create a new spec directory with this name
#   --help

set -euo pipefail

# ==============================================================================
# Helpers
# ==============================================================================

GREEN='\033[0;32m'
YELLOW='\033[0;33m'
CYAN='\033[0;36m'
RED='\033[0;31m'
DIM='\033[2m'
RESET='\033[0m'

info()    { printf "${DIM}  →${RESET} %s\n"    "$*" >&2; }
warn()    { printf "${YELLOW}  !${RESET} %s\n" "$*" >&2; }
error()   { printf "${RED}  ✗${RESET} %s\n"    "$*" >&2; }
success() { printf "${GREEN}  ✓${RESET} %s\n"  "$*" >&2; }
ask()     { printf "${CYAN}  ?${RESET} %s "    "$*" >&2; }

resolve_project_root() {
  if git rev-parse --show-toplevel > /dev/null 2>&1; then
    git rev-parse --show-toplevel
  else
    pwd
  fi
}

# Read a key from .claude/startup.toml, return default if missing.
# Usage: read_startup_conf <root> <key> <default>
read_startup_conf() {
  local root="$1" key="$2" default="$3"
  local conf="$root/.claude/startup.toml"
  if [[ -f "$conf" ]]; then
    local val
    val=$(grep "^${key}[[:space:]]*=" "$conf" \
      | sed 's/[^=]*=[[:space:]]*"\?\([^"]*\)"\?.*/\1/' \
      | head -1)
    echo "${val:-$default}"
  else
    echo "$default"
  fi
}

# Find the specs directory (creating default if none exist).
# Priority: startup.toml → the-custom-startup/specs → .start/specs → docs/specs
resolve_specs_dir() {
  local root="$1"
  local conf_dir
  conf_dir=$(read_startup_conf "$root" "specs_dir" "")
  if [[ -n "$conf_dir" ]]; then
    local abs_dir="$root/$conf_dir"
    [[ -d "$abs_dir" ]] && echo "$abs_dir" && return
    # Configured but not yet created — return it (caller will mkdir)
    echo "$abs_dir" && return
  fi
  if [[ -d "$root/the-custom-startup/specs" ]]; then
    echo "$root/the-custom-startup/specs"
  elif [[ -d "$root/.start/specs" ]]; then
    echo "$root/.start/specs"
  elif [[ -d "$root/docs/specs" ]]; then
    echo "$root/docs/specs"
  else
    # Default: the-custom-startup/specs (will be created)
    echo "$root/the-custom-startup/specs"
  fi
}

list_specs() {
  local specs_dir="$1"
  local entry
  for entry in "$specs_dir"/*/; do
    [[ -d "$entry" ]] && basename "$entry"
  done
}

select_spec() {
  local specs_dir="$1"
  local specs=()
  local name
  while IFS= read -r name; do
    specs+=("$name")
  done < <(list_specs "$specs_dir")

  if [[ ${#specs[@]} -eq 0 ]]; then
    echo ""
    return
  fi

  printf "${CYAN}  Available specs:${RESET}\n" >&2
  local i=1
  local s
  for s in "${specs[@]}"; do
    printf "  ${CYAN}%d)${RESET} %s\n" "$i" "$s" >&2
    (( i++ ))
  done
  printf "  ${CYAN}%d)${RESET} Create new spec\n" "$i" >&2
  echo "" >&2
  ask "Select spec [1-$i]:"
  local choice
  read -r choice </dev/tty
  local idx=$(( choice - 1 ))
  if [[ $idx -eq ${#specs[@]} ]]; then
    echo "__new__"
  elif [[ $idx -lt 0 || $idx -ge ${#specs[@]} ]]; then
    error "Invalid choice"
    exit 1
  else
    echo "${specs[$idx]}"
  fi
}

# Generate the next spec ID (NNN format)
next_spec_id() {
  local specs_dir="$1"
  local max=0
  local entry
  for entry in "$specs_dir"/*/; do
    [[ -d "$entry" ]] || continue
    local base; base=$(basename "$entry")
    local num; num=$(echo "$base" | grep -oE '^[0-9]+' || echo "0")
    if [[ "$num" -gt "$max" ]]; then
      max="$num"
    fi
  done
  printf "%03d" $(( max + 1 ))
}

# Prompt for a new spec name and create the directory
create_new_spec() {
  local specs_dir="$1"
  mkdir -p "$specs_dir"
  local id; id=$(next_spec_id "$specs_dir")
  ask "New spec name (e.g. my-feature):"
  local spec_name
  read -r spec_name </dev/tty
  spec_name=$(echo "$spec_name" | tr '[:upper:]' '[:lower:]' | tr ' ' '-' | tr -cd 'a-z0-9-')
  local dir="$specs_dir/${id}-${spec_name}"
  mkdir -p "$dir"
  # Initialize README
  cat > "$dir/README.md" << EOF
# Spec: ${id}-${spec_name}

| Field | Value |
|-------|-------|
| Status | Draft |
| Created | $(date +%Y-%m-%d) |

## Documents

| Document | Status |
|----------|--------|
| requirements.md | - |
| solution.md | - |
| plan/ | - |
EOF
  success "Created spec directory: $dir" >&2
  echo "$dir"
}

# Document type → filename mapping (bash 3.2 compatible, no declare -A)
doc_filename() {
  local doc_type="$1"
  case "$doc_type" in
    prd) echo "requirements.md" ;;
    sdd) echo "solution.md" ;;
    *)   echo "" ;;
  esac
}

doc_label() {
  local doc_type="$1"
  case "$doc_type" in
    prd) echo "Product Requirements Document (PRD)" ;;
    sdd) echo "Solution Design Document (SDD)" ;;
    *)   echo "Document" ;;
  esac
}

# ==============================================================================
# Argument parsing
# ==============================================================================

INPUT_FILE=""
DOC_TYPE=""
SPEC_ARG=""
NEW_SPEC_NAME=""

parse_args() {
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --input)
        INPUT_FILE="${2:?--input requires a file path}"
        shift ;;
      --type)
        DOC_TYPE="${2:?--type requires prd|sdd}"
        shift ;;
      --spec)
        SPEC_ARG="${2:?--spec requires a value}"
        shift ;;
      --new)
        NEW_SPEC_NAME="${2:?--new requires a spec name}"
        shift ;;
      --help|-h)
        cat << 'EOF'
The Custom Startup — Import Spec

Usage:
  import-spec.sh --type <prd|sdd> [OPTIONS]

Options:
  --input <file>           Source Markdown file (reads stdin if omitted)
  --type <prd|sdd>         Document type: prd = requirements.md, sdd = solution.md
  --spec <NNN-name|path>   Target spec directory (interactive if omitted)
  --new <name>             Create a new spec directory with this name
  --help                   Show this help

Examples:
  # Import a PRD from Claude.ai output (interactive spec selection)
  ./scripts/import-spec.sh --type prd --input prd-output.md

  # Import Perplexity research as SDD into existing spec
  ./scripts/import-spec.sh --type sdd --spec 001-my-feature --input perplexity.md

  # Create new spec and import PRD from stdin
  cat prd.md | ./scripts/import-spec.sh --type prd --new my-feature

  # Import from clipboard (macOS)
  pbpaste | ./scripts/import-spec.sh --type prd --new my-feature
EOF
        exit 0 ;;
      *)
        error "Unknown option: $1"
        exit 1 ;;
    esac
    shift
  done
}

# ==============================================================================
# Main
# ==============================================================================

main() {
  parse_args "$@"

  # Validate type
  if [[ -z "$DOC_TYPE" ]]; then
    error "--type is required (prd or sdd)"
    echo "  Run with --help for usage." >&2
    exit 1
  fi
  local filename; filename=$(doc_filename "$DOC_TYPE")
  if [[ -z "$filename" ]]; then
    error "Unknown type: $DOC_TYPE (use prd or sdd)"
    exit 1
  fi
  local label; label=$(doc_label "$DOC_TYPE")

  # Read input
  local content=""
  if [[ -n "$INPUT_FILE" ]]; then
    if [[ ! -f "$INPUT_FILE" ]]; then
      error "Input file not found: $INPUT_FILE"
      exit 1
    fi
    content=$(cat "$INPUT_FILE")
    info "Reading from: $INPUT_FILE"
  elif [[ ! -t 0 ]]; then
    content=$(cat)
    info "Reading from stdin"
  else
    error "No input provided. Use --input <file> or pipe content via stdin."
    echo "  Run with --help for usage." >&2
    exit 1
  fi

  if [[ -z "$content" ]]; then
    error "Input is empty"
    exit 1
  fi

  # Resolve project root and specs dir
  local project_root; project_root=$(resolve_project_root)
  local specs_dir; specs_dir=$(resolve_specs_dir "$project_root")

  # Resolve spec directory
  local spec_dir=""

  if [[ -n "$NEW_SPEC_NAME" ]]; then
    # Create new spec with given name
    mkdir -p "$specs_dir"
    local id; id=$(next_spec_id "$specs_dir")
    local safe_name
    safe_name=$(echo "$NEW_SPEC_NAME" | tr '[:upper:]' '[:lower:]' | tr ' ' '-' | tr -cd 'a-z0-9-')
    spec_dir="$specs_dir/${id}-${safe_name}"
    mkdir -p "$spec_dir"
    cat > "$spec_dir/README.md" << EOF
# Spec: ${id}-${safe_name}

| Field | Value |
|-------|-------|
| Status | Draft |
| Created | $(date +%Y-%m-%d) |

## Documents

| Document | Status |
|----------|--------|
| requirements.md | - |
| solution.md | - |
| plan/ | - |
EOF
    success "Created spec: $spec_dir"

  elif [[ -n "$SPEC_ARG" ]]; then
    if [[ -d "$SPEC_ARG" ]]; then
      spec_dir="$SPEC_ARG"
    elif [[ -d "$specs_dir/$SPEC_ARG" ]]; then
      spec_dir="$specs_dir/$SPEC_ARG"
    else
      error "Spec not found: $SPEC_ARG"
      exit 1
    fi

  else
    # Interactive selection
    local selected; selected=$(select_spec "$specs_dir")
    if [[ "$selected" == "__new__" || -z "$selected" ]]; then
      spec_dir=$(create_new_spec "$specs_dir")
    else
      spec_dir="$specs_dir/$selected"
    fi
  fi

  # Check for existing document
  local target_file="$spec_dir/$filename"
  if [[ -f "$target_file" ]]; then
    warn "$label already exists: $target_file"
    ask "Overwrite? [y/N]:"
    local answer
    read -r answer </dev/tty
    case "$answer" in
      [yY]|[yY][eE][sS]) ;;
      *)
        info "Aborted — file not overwritten"
        exit 0 ;;
    esac
  fi

  # Write the document
  printf '%s\n' "$content" > "$target_file"
  success "Imported $label: $target_file"

  echo "" >&2
  info "Next steps:"
  case "$DOC_TYPE" in
    prd) echo "  1. Review requirements.md and refine with /start:specify" >&2
         echo "  2. Create solution design: /start:specify-solution" >&2 ;;
    sdd) echo "  1. Review solution.md and refine with /start:specify-solution" >&2
         echo "  2. Create implementation plan: /start:specify-plan" >&2 ;;
  esac
  echo "" >&2
}

main "$@"
