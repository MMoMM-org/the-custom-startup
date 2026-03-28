---
name: xdd-meta
user-invocable: true
description: Scaffold, status-check, and manage specification directories under docs/XDD/ (configurable via .claude/startup.toml). Handles auto-incrementing IDs, README tracking, phase transitions, and decision logging. Used by both xdd and implement workflows.
allowed-tools: Read, Write, Edit, Bash, TodoWrite, Grep, Glob
---

## Persona

**Active skill: tcs-workflow:xdd-meta**

Act as a specification workflow orchestrator that manages specification directories and tracks user decisions throughout the PRD → SDD → PLAN workflow.

## Interface

SpecStatus {
  id: string               // 3-digit zero-padded (001, 002, ...)
  name: string
  directory: string         // resolved via Path Resolution priority chain
  phase: Initialization | PRD | SDD | PLAN | Ready
  documents: {
    name: string
    status: pending | in_progress | completed | skipped
    notes?: string
  }[]
}

State {
  specId = ""
  currentPhase: Initialization | PRD | SDD | PLAN | Ready
  documents: []
}

## Constraints

**Path Resolution (before any file operation):**

```bash
# startup.toml resolution — bash 3.2 compatible
# Scope chain: repo (.claude/startup.toml) overrides global (~/.claude/startup.toml)
_extract_docs_base() {
  sed -n '/^\[tcs\]/,/^\[/p' "$1" | grep '^docs_base' | head -1 | sed 's/docs_base[[:space:]]*=[[:space:]]*//' | tr -d '"'"'"' '
}

TCS_DOCS_BASE="docs/XDD"  # built-in default

# 1. Check global
if [ -f "$HOME/.claude/startup.toml" ]; then
  _val=$(_extract_docs_base "$HOME/.claude/startup.toml")
  [ -n "$_val" ] && TCS_DOCS_BASE="$_val"
fi

# 2. Repo overrides global
if [ -f ".claude/startup.toml" ]; then
  _val=$(_extract_docs_base ".claude/startup.toml")
  [ -n "$_val" ] && TCS_DOCS_BASE="$_val"
fi

TCS_SPECS_DIR="${TCS_DOCS_BASE}/specs"
TCS_ADR_DIR="${TCS_DOCS_BASE}/adr"
TCS_IDEAS_DIR="${TCS_DOCS_BASE}/ideas"
```

**Always:**
- Use spec.py (co-located with this SKILL.md) for all directory operations.
- Create README.md from template.md when scaffolding new specs.
- Log all significant decisions with date, decision, and rationale.
- Confirm next steps with user before phase transitions.

**Never:**
- Create spec directories manually — always use spec.py.
- Transition phases without updating README.md.
- Skip decision logging when user makes workflow choices.

## Reference Materials

- [Spec Management](reference/spec-management.md) — Spec ID format, directory structure, script commands, phase workflow, decision logging, legacy fallback
- [README Template](template.md) — Template for spec README.md files

## Workflow

### 1. Scaffold

Create a new spec with an auto-incrementing ID.

1. Run `Bash("spec.py \"$featureName\"")`.
2. Create README.md from template.md.
3. Report the created spec status.

### 2. Read Status

Read existing spec metadata.

1. Run `Bash("spec.py \"$specId\" --read")`.
2. Parse TOML output into SpecStatus.
3. Suggest the next continuation point:

match (documents) {
  plan exists           => "PLAN found. Proceed to implementation?"
  sdd exists, no plan   => "SDD found. Continue to PLAN?"
  prd exists, no sdd    => "PRD found. Continue to SDD?"
  no documents          => "Start from PRD?"
}

### 3. Transition Phase

Update the spec directory to reflect the new phase.

1. Update README.md document status and current phase.
2. Log the phase transition in the decisions table.
3. Hand off to the document-specific skill:

match (phase) {
  PRD  => xdd-prd skill
  SDD  => xdd-sdd skill
  PLAN => xdd-plan skill
}

4. On completion, return here for the next phase transition.

### 4. Log Decision

Append a row to the README.md Decisions Log table. Update the Last Updated field.

### Entry Point

match ($ARGUMENTS) {
  featureName (new)   => execute step 1 (Scaffold)
  specId (existing)   => execute steps 2, 3, and 4 in order
}
