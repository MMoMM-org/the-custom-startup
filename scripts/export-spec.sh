#!/usr/bin/env bash
#
# The Custom Startup — Export Spec
#
# Exports a spec from .start/specs/ as a portable Markdown prompt
# that can be pasted into Claude.ai, Perplexity, or any other AI tool.
#
# Usage:
#   ./scripts/export-spec.sh [OPTIONS]
#
# Options:
#   --spec <NNN-name|path>   Spec to export (interactive selection if omitted)
#   --output <file>          Write to file instead of stdout
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

# Resolve project root (git root or cwd)
resolve_project_root() {
  if git rev-parse --show-toplevel > /dev/null 2>&1; then
    git rev-parse --show-toplevel
  else
    pwd
  fi
}

# Find the specs directory (.start/specs/ preferred, docs/specs/ legacy fallback)
resolve_specs_dir() {
  local root="$1"
  if [[ -d "$root/.start/specs" ]]; then
    echo "$root/.start/specs"
  elif [[ -d "$root/docs/specs" ]]; then
    echo "$root/docs/specs"
  else
    echo ""
  fi
}

# List available specs, return names (one per line)
list_specs() {
  local specs_dir="$1"
  local entry
  for entry in "$specs_dir"/*/; do
    [[ -d "$entry" ]] && basename "$entry"
  done
}

# Interactive spec selection
select_spec() {
  local specs_dir="$1"
  local specs=()
  local name
  while IFS= read -r name; do
    specs+=("$name")
  done < <(list_specs "$specs_dir")

  if [[ ${#specs[@]} -eq 0 ]]; then
    error "No specs found in $specs_dir"
    exit 1
  fi

  if [[ ${#specs[@]} -eq 1 ]]; then
    echo "${specs[0]}"
    return
  fi

  printf "${CYAN}  Available specs:${RESET}\n" >&2
  local i=1
  local s
  for s in "${specs[@]}"; do
    printf "  ${CYAN}%d)${RESET} %s\n" "$i" "$s" >&2
    (( i++ ))
  done
  echo "" >&2
  ask "Select spec [1-${#specs[@]}]:"
  local choice
  read -r choice </dev/tty
  local idx=$(( choice - 1 ))
  if [[ $idx -lt 0 || $idx -ge ${#specs[@]} ]]; then
    error "Invalid choice"
    exit 1
  fi
  echo "${specs[$idx]}"
}

# Read a file if it exists, return empty string otherwise
read_file_safe() {
  local path="$1"
  [[ -f "$path" ]] && cat "$path" || true
}

# ==============================================================================
# Export assembler
# ==============================================================================

assemble_export() {
  local spec_dir="$1"
  local spec_name
  spec_name=$(basename "$spec_dir")

  # Read README for spec title and status
  local readme_content
  readme_content=$(read_file_safe "$spec_dir/README.md")

  local prd_content
  prd_content=$(read_file_safe "$spec_dir/requirements.md")

  local sdd_content
  sdd_content=$(read_file_safe "$spec_dir/solution.md")

  # Collect plan files
  local plan_content=""
  if [[ -d "$spec_dir/plan" ]]; then
    local plan_readme
    plan_readme=$(read_file_safe "$spec_dir/plan/README.md")
    [[ -n "$plan_readme" ]] && plan_content+="$plan_readme"$'\n\n'
    local phase_file
    for phase_file in "$spec_dir/plan"/phase-*.md; do
      [[ -f "$phase_file" ]] || continue
      local phase_name
      phase_name=$(basename "$phase_file" .md)
      plan_content+="### Phase: $phase_name"$'\n\n'
      plan_content+=$(cat "$phase_file")
      plan_content+=$'\n\n'
    done
  fi

  # Detect what's available
  local has_prd=false has_sdd=false has_plan=false
  [[ -n "$prd_content" ]] && has_prd=true
  [[ -n "$sdd_content" ]] && has_sdd=true
  [[ -n "$plan_content" ]] && has_plan=true

  # Build the export document
  cat << EOF
# Spec Export: $spec_name

> This document was exported from a The Custom Startup spec directory.
> It contains the specification context for use in external AI tools.
> To import AI-generated output back into the project, use:
>
>     ./scripts/import-spec.sh --type prd|sdd --input <output.md>

---

EOF

  if [[ "$has_prd" == "true" ]]; then
    cat << EOF
## Product Requirements

$prd_content

---

EOF
  fi

  if [[ "$has_sdd" == "true" ]]; then
    cat << EOF
## Solution Design

$sdd_content

---

EOF
  fi

  if [[ "$has_plan" == "true" ]]; then
    cat << EOF
## Implementation Plan

$plan_content

---

EOF
  fi

  if [[ "$has_prd" == "false" && "$has_sdd" == "false" && "$has_plan" == "false" ]]; then
    warn "Spec directory exists but contains no documents yet: $spec_dir"
    cat << EOF
## Note

No specification documents found in this spec directory.
Start with \`/start:specify\` or \`/start:brainstorm\` to create them.
EOF
  fi

  cat << EOF

---

*Exported from: $spec_dir*
EOF
}

# ==============================================================================
# Argument parsing
# ==============================================================================

SPEC_ARG=""
OUTPUT_FILE=""

parse_args() {
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --spec)
        SPEC_ARG="${2:?--spec requires a value}"
        shift ;;
      --output)
        OUTPUT_FILE="${2:?--output requires a file path}"
        shift ;;
      --help|-h)
        cat << 'EOF'
The Custom Startup — Export Spec

Usage:
  export-spec.sh [OPTIONS]

Options:
  --spec <NNN-name|path>   Spec to export (interactive if omitted)
  --output <file>          Write export to file (default: stdout)
  --help                   Show this help

Examples:
  # Interactive selection, output to stdout
  ./scripts/export-spec.sh

  # Export specific spec to file
  ./scripts/export-spec.sh --spec 001-my-feature --output /tmp/spec-export.md

  # Pipe into pbcopy (macOS clipboard)
  ./scripts/export-spec.sh --spec 001-my-feature | pbcopy
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

  local project_root
  project_root=$(resolve_project_root)

  local specs_dir
  specs_dir=$(resolve_specs_dir "$project_root")

  if [[ -z "$specs_dir" ]]; then
    error "No specs directory found (.start/specs/ or docs/specs/)"
    echo "  Run /start:specify to create your first spec." >&2
    exit 1
  fi

  # Resolve spec directory
  local spec_dir=""
  if [[ -n "$SPEC_ARG" ]]; then
    # Direct path or name under specs_dir
    if [[ -d "$SPEC_ARG" ]]; then
      spec_dir="$SPEC_ARG"
    elif [[ -d "$specs_dir/$SPEC_ARG" ]]; then
      spec_dir="$specs_dir/$SPEC_ARG"
    else
      error "Spec not found: $SPEC_ARG"
      exit 1
    fi
  else
    local spec_name
    spec_name=$(select_spec "$specs_dir")
    spec_dir="$specs_dir/$spec_name"
  fi

  info "Exporting: $spec_dir"

  # Assemble and output
  local export_content
  export_content=$(assemble_export "$spec_dir")

  if [[ -n "$OUTPUT_FILE" ]]; then
    echo "$export_content" > "$OUTPUT_FILE"
    success "Exported to: $OUTPUT_FILE"
  else
    echo "$export_content"
  fi
}

main "$@"
