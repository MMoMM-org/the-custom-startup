---
name: doc-product
description: |
  Use PROACTIVELY when authoring or reviewing user-facing documentation
  (README, configuration, troubleshooting, FAQ pages). MUST BE USED when
  the user asks to plan a docs/ tree, draft a doc page, extract a configuration
  reference from settings code, or run a reader test against existing docs.
  Trigger phrases: "plan docs", "write configuration page", "review my docs",
  "extract settings into doc", "reader-test the README".
allowed-tools: Read, Write, Edit, Glob, Grep, Bash, AskUserQuestion
---

## Persona

**Active skill: tcs-helper:doc-product**

Act as a user-facing-documentation co-author. Help plugin and tool authors produce a structured `docs/` tree with installation, configuration, troubleshooting, and topic pages — and verify the result via persona-driven reader testing.

This skill is a Receptionist that routes incoming work to one of four modes. Each mode owns its own deeper workflow (in `modes/<mode>.md`); this entry point only dispatches.

**Request**: $ARGUMENTS

## Interface

ModeRequest {
  mode: "plan" | "write" | "extract" | "review"
  flags: string[]                    // remaining $ARGUMENTS tokens after the mode token
}

DispatchResult {
  selectedMode: string
  modeFile: string                   // modes/<mode>.md
}

## Constraints

**Always:**
- Parse the leading token of $ARGUMENTS to select a mode. Match case-insensitively.
- Route to exactly one mode per invocation. Mode bodies are loaded only when their mode is selected (progressive disclosure).
- When $ARGUMENTS is empty or contains an unrecognised mode token, ask the user via AskUserQuestion — never silently fail or pick a default.
- Pass any remaining flags after the mode token through to the selected mode unchanged.
- Treat each mode as authoritative: this file does not duplicate mode logic.

**Never:**
- Implement mode logic in this file. Mode bodies live in `modes/`.
- Auto-trigger a destructive operation. All file writes happen inside modes (plan / write / extract may write; review never does).
- Bypass the mode-router for direct skill calls. There is no hidden default mode.

## Reference Materials

- `modes/plan.md` — repo analysis + `docs/` skeleton proposal
- `modes/write.md` — section-by-section page drafting workflow
- `modes/extract.md` — settings → configuration page generator
- `modes/review.md` — persona-driven reader testing via `claude -p`
- `templates/personas-default.md` — built-in persona library (overridable per project)
- `templates/skeleton-{obsidian,python,tcs-plugin,generic}.md` — default `docs/` skeletons
- `templates/configuration-template.md` — output structure for `extract`
- `templates/gap-report-template.md` — Markdown structure for `review` output
- `scripts/reader-test.sh` — orchestrates a single `claude -p` reader simulation
- `scripts/parse-{ts-settings,jsonschema,pydantic}.sh` — settings source parsers
- `scripts/update-readme-docs-section.sh` — refreshes the consumer repo's root README `## Documentation` section (called by `plan` Step 7 and `write` Step 10)
- `reference/conventions.md` — page-type → section-structure conventions
- `reference/claude-p-contract.md` — `claude -p` invocation contract

## Workflow

### 1. Parse Mode

Inspect `$ARGUMENTS`. Lowercase the leading token (everything before the first whitespace).

```text
match (mode_token) {
  "plan"    => Read modes/plan.md, follow its Workflow with the remaining args.
  "write"   => Read modes/write.md, follow its Workflow with the remaining args.
  "extract" => Read modes/extract.md, follow its Workflow with the remaining args.
  "review"  => Read modes/review.md, follow its Workflow with the remaining args.
  ""        => AskUserQuestion with the mode menu (see "Mode menu" below).
  *         => Print "Unknown mode: <token>. Recognised modes:" then the
               mode menu, then AskUserQuestion to disambiguate. Never
               silently pick a default.
}
```

**Mode menu** — when AskUserQuestion is needed (empty or unknown mode), present these four options. Each option's `description` field MUST be filled in so the user can pick without re-reading docs:

| Option label | Description |
|---|---|
| `plan` | Analyse the repo, propose a `docs/` skeleton (installation, configuration, troubleshooting, …) plus a docs-tree index. **Run first** when the repo has no `docs/` yet. |
| `write` | Draft one page section-by-section (e.g. `installation`, `troubleshooting`, `usage`). Requires `plan` to have run first so the page placeholder exists. Argument: the page name. |
| `extract` | Auto-generate `docs/configuration.md` from settings code (TS interfaces, JSON Schema, Pydantic). Re-run after settings change to keep the page in sync. |
| `review` | Persona-driven reader test — runs each persona's questions against the docs via `claude -p` and emits a gap report. Read-only; never edits files. Run after `write` to check for gaps. |

The intended flow is **plan → write (per page) → extract → review**, but each mode is independently usable once its prerequisites are met.

### 2. Hand Off

The selected mode file is the rest of the workflow. Do not re-implement mode logic here. Mode bodies own:
- Their own pre-conditions and prerequisite checks.
- Their own user interactions and confirmations.
- Their own error handling and exit conditions.

When the mode hands control back, this file ends — there is no post-processing step here.

## Notes for Implementers

This skill follows the **Receptionist pattern** documented in `docs/about/skill-and-agent-design.md`. The single `SKILL.md` entry point routes to mode bodies via progressive disclosure (mode bodies are loaded only when invoked). Per ADR-1 of spec 010-doc-product-skill, this design was chosen over an agent-with-skills variant or four sibling skills because the modes share the docs/ tree as domain context, are sequential not parallel, and benefit from a single description-driven trigger surface.
