---
title: "Phase 1: Skill Scaffold and Mode Router"
status: pending
version: "1.0"
phase: 1
---

# Phase 1: Skill Scaffold and Mode Router

## Phase Context

**GATE**: Read all referenced files before starting this phase.

**Specification References**:
- `[ref: SDD/Building Block View — Directory Map]` — directory layout
- `[ref: SDD/Interface Specifications — Skill Frontmatter Contract]` — frontmatter
- `[ref: SDD/Interface Specifications — Mode Routing Contract]` — mode dispatch
- `[ref: SDD/ADR-1]` — mode-router rationale
- `[ref: SDD/ADR-7]` — single slash command
- `[ref: PRD/Feature 1-4 user stories]` — what each mode must eventually do (this phase only routes; modes implemented in P2-P4)

**Key Decisions**:
- ADR-1 mode-router: SKILL.md routes via progressive disclosure to `modes/{plan,write,extract,review}.md`. Mode bodies are NOT implemented in this phase — they exist only as placeholders that print "TODO P2/P3/P4".
- ADR-7 single slash: only `/doc-product` is registered. No `/doc-plan` etc.
- TCS conventions: PICS layout, frontmatter with `Use PROACTIVELY`/`MUST BE USED` description, minimal `allowed-tools`.

**Dependencies**:
- None (this is the entry phase).

---

## Tasks

This phase delivers an installable, discoverable skill that auto-triggers on appropriate prompts and dispatches to mode files (which print TODO stubs in this phase). Verifiable outcome: `/doc-product plan` resolves and prints "Phase 2 placeholder", proving the router works end-to-end.

- [ ] **T1.1 Skill Directory Skeleton and Frontmatter** `[activity: build-feature]`

  1. **Prime**: Read `plugins/tcs-helper/skills/skill-author/SKILL.md` and `plugins/tcs-helper/skills/finish-branch/SKILL.md` for PICS structure reference. Read `~/.claude/rules/authoring.md` for description-quality rules. `[ref: SDD/Implementation Context — Code Context]`
  2. **Test**: Author the skill skeleton structure on a fresh branch. Verify (via `find plugins/tcs-helper/skills/doc-product`) that the directory tree matches SDD §Directory Map exactly: SKILL.md + modes/ + templates/ + scripts/ + reference/ subdirs all present. Verify the SKILL.md frontmatter is valid YAML with `name: doc-product`, the SDD-specified description (containing "Use PROACTIVELY" and "MUST BE USED" plus 5 trigger phrases), and `allowed-tools: Read, Write, Edit, Glob, Grep, Bash, AskUserQuestion`.
  3. **Implement**: Create the directory tree under `plugins/tcs-helper/skills/doc-product/`. Author SKILL.md with the frontmatter from SDD §Skill Frontmatter Contract; the body sections will be filled in T1.2.
  4. **Validate**: Run `/skill-author audit plugins/tcs-helper/skills/doc-product/SKILL.md` — must pass frontmatter, description, and structure checks. Verify the file is < 150 lines (skeleton only).
  5. **Success**:
     - [ ] Directory tree matches SDD/Directory Map `[ref: SDD/Directory Map]`
     - [ ] Frontmatter is valid and matches SDD §Skill Frontmatter Contract `[ref: SDD/Interface — Skill Frontmatter Contract]`
     - [ ] `/skill-author` audit passes with no FAIL items
     - [ ] Description contains all required trigger phrases per `~/.claude/rules/authoring.md`

- [ ] **T1.2 SKILL.md Mode Router Workflow** `[activity: build-feature]`

  1. **Prime**: Read SDD §Solution Strategy and §Mode Routing Contract. `[ref: SDD/Solution Strategy]` `[ref: SDD/Mode Routing Contract]`
  2. **Test**: Add tests as a Markdown checklist inside SKILL.md (TCS skill testing pattern: pressure scenarios, not unit tests). Pressure cases:
     - Invocation `$ARGUMENTS = ""` → Skill must AskUserQuestion listing four modes.
     - Invocation `$ARGUMENTS = "plan"` → Skill must Read `modes/plan.md` and follow its workflow.
     - Invocation `$ARGUMENTS = "REVIEW --page installation"` (mixed case + flags) → match "review" case-insensitively, hand off to `modes/review.md` with the remaining args.
     - Invocation `$ARGUMENTS = "garbage"` → Skill must list recognised modes via AskUserQuestion, never silently fail.
  3. **Implement**: Author the Workflow section of SKILL.md per the SDD example in §Implementation Examples — Mode Router. Use the PICS layout (Persona / Interface / Constraints / Reference Materials, then Workflow). Body must contain the mode-router `match` block and the hand-off instruction. Keep SKILL.md under ~150 lines; deeper logic lives in `modes/`.
  4. **Validate**: Manually test the four pressure scenarios by invoking the skill in a Claude Code session (after T1.3 plugin bump). Each scenario must produce the documented behaviour. Re-run `/skill-author audit`.
  5. **Success**:
     - [ ] All four pressure scenarios produce documented behaviour `[ref: SDD/Acceptance Criteria — Mode dispatch]`
     - [ ] SKILL.md size < 200 lines
     - [ ] Mode-router section in body matches SDD §Implementation Examples — Mode Router

- [ ] **T1.3 Mode-File Stubs and Plugin Manifest Bump** `[activity: build-feature]` `[parallel: true]`

  1. **Prime**: Read `plugins/tcs-helper/.claude-plugin/plugin.json` to know the current version. Read repo memory feedback `feedback_no-manual-marketplace-sync` (in `~/.claude/projects/.../memory/`).
  2. **Test**: After implementation, the four mode-stub files must exist and each must print a clear "Phase N (P2 / P3 / P4) — not yet implemented; this stub will be replaced in [phase]" message when read. Verify the plugin.json minor version bumps cleanly (e.g. 3.2.0 → 3.3.0). Verify after pushing to the marketplace branch and restarting Claude Code, `/doc-product` appears in the slash menu.
  3. **Implement**:
     - Create `modes/plan.md`, `modes/write.md`, `modes/extract.md`, `modes/review.md` as stubs with frontmatter (none) and a single body line "TODO: implemented in Phase N — see docs/XDD/specs/010-doc-product-skill/plan/phase-N.md".
     - Bump `plugins/tcs-helper/.claude-plugin/plugin.json` `version` field by minor (3.2.0 → 3.3.0). Do NOT manually copy to cache or marketplace dirs.
  4. **Validate**: Skill appears in `/` menu after Claude Code restart. Each mode hand-off prints the stub message. Plugin version is the new value.
  5. **Success**:
     - [ ] Four mode-stub files exist with TODO messages
     - [ ] plugin.json version incremented per `feedback_no-manual-marketplace-sync` memory
     - [ ] Skill appears in `/` menu after Claude Code restart `[ref: SDD/Deployment View — Plugin Manifest Update]`

- [ ] **T1.4 Phase 1 Validation** `[activity: validate]`

  - Re-run `/skill-author audit` on the full doc-product skill directory.
  - Run all four mode-router pressure scenarios end-to-end via the slash menu.
  - Verify against the SDD §Acceptance Criteria — Mode dispatch criteria.
  - Confirm the plugin.json version bump did NOT involve manual cache/marketplace copies (per memory).
  - If any deviation from SDD was required, log it in the Deviations section below.

---

## Deviations

(None yet. Recorded here when implementation discovers a needed deviation from SDD.)
