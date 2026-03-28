---
title: "Phase 2: Reference Layer"
status: pending
version: "1.0"
phase: 2
---

# Phase 2: Reference Layer

## Phase Context

**GATE**: Read all referenced files before starting this phase.

**Specification References**:
- `[ref: SDD/Directory Map — reference/]` — 5 files: skills.md, plugins.md, agents.md, output-styles.md, xdd.md
- `[ref: SDD/ADR-4]` — SKILL.md is source of truth; read actual files, never recall
- `[ref: PRD/Feature 3]` — XDD workflow documented (all 6 XDD skills)
- `[ref: SDD/Acceptance Criteria — Completeness]` — 20 tcs-workflow skills listed

**Key Decisions**:
- ADR-4: Glob `plugins/tcs-workflow/skills/*/SKILL.md` to get exact skill names and descriptions before writing `reference/skills.md`
- ADR-4: Read `plugins/tcs-workflow/skills/xdd*/SKILL.md` files before writing `reference/xdd.md`

**Dependencies**:
- Phase 1 complete (directory scaffold exists)
- T2.1, T2.2, T2.3, T2.4, T2.5 are all independent and can run in parallel

---

## Tasks

Builds the authoritative reference layer — the docs users bookmark for ongoing use.

- [ ] **T2.1 Write reference/skills.md** `[activity: documentation]`

  1. Prime: Glob `plugins/tcs-workflow/skills/*/SKILL.md`; read each file's `name` and `description` frontmatter; count to confirm 20 skills; note which are user-invocable vs. autonomous `[ref: SDD/ADR-4; PRD/AC — 20 skills listed]`
  2. Test: List all 20 skill names from actual SKILL.md files; group by category (XDD · Core · Maintain); confirm no skill is missed
  3. Implement: Rewrite `docs/reference/skills.md` — decision tree at top (matches current structure but updated), command reference table with correct plugin namespace (`tcs-workflow:`), all 20 skills described; XDD skills have their own subsection
  4. Validate: `grep -c "^###\|^#### " docs/reference/skills.md` ≥ 20; `grep "tcs-start" docs/reference/skills.md` → 0 results
  5. Success:
    - [ ] Exactly 20 tcs-workflow skills listed `[ref: PRD/AC — Completeness]`
    - [ ] All skill invocations use `tcs-workflow:` namespace `[ref: SDD/CON-5]`

- [ ] **T2.2 Write reference/plugins.md** `[activity: documentation]` `[parallel: true]`

  1. Prime: Read `docs/plugins.md` (current); read `plugins/*/`.claude-plugin/plugin.json` for all 4 plugins to get exact names, versions, descriptions `[ref: PRD/Feature 2; SDD/ADR-4]`
  2. Test: Confirm 4 plugin names; confirm tcs-patterns is entirely absent from current docs/plugins.md; note tcs-helper description
  3. Implement: Rewrite `docs/reference/plugins.md` — 4 sections (tcs-workflow, tcs-team, tcs-helper, tcs-patterns); each with: what it does, install command, skill/agent list summary, link to relevant guide; tcs-patterns section lists all 17 skills by category
  4. Validate: File describes exactly 4 plugins; `grep "tcs-start" docs/reference/plugins.md` → 0 results; tcs-patterns section present
  5. Success:
    - [ ] All 4 plugins documented `[ref: PRD/Feature 2]`
    - [ ] tcs-patterns section present with 17-skill summary `[ref: PRD/AC Feature 2]`

- [ ] **T2.3 Write reference/xdd.md** `[activity: documentation]` `[parallel: true]`

  1. Prime: Glob `plugins/tcs-workflow/skills/xdd*/SKILL.md`; read each file fully; also read `docs/concept/v2/` files for design rationale `[ref: PRD/Feature 3; SDD/ADR-4]`
  2. Test: List the 6 XDD skills (xdd, xdd-meta, xdd-prd, xdd-sdd, xdd-plan, xdd-tdd); for each note: purpose, inputs, key outputs; identify any spec directory structure details from the skill files
  3. Implement: Write `docs/reference/xdd.md` — the XDD workflow deep dive; overview of PRD → SDD → PLAN → implement loop; one section per skill; spec directory structure (`docs/XDD/specs/NNN-name/`); `.claude/startup.toml` config for custom spec paths
  4. Validate: All 6 XDD skill names appear; spec directory structure is accurate; no `[NEEDS CLARIFICATION]` markers
  5. Success:
    - [ ] All 6 XDD skills described with purpose and outputs `[ref: PRD/AC Feature 3]`
    - [ ] Spec directory structure documented `[ref: SDD/Constraints CON-1 through CON-6]`

- [ ] **T2.4 Update reference/agents.md** `[activity: documentation]` `[parallel: true]`

  1. Prime: Read `docs/agents.md` (current); note the `PHILOSOPHY.md` link at line referencing philosophy `[ref: SDD/Technical Debt]`
  2. Test: Confirm the one broken link: `PHILOSOPHY.md` → needs updating to `about/the-custom-philosophy.md`; confirm all 15 agents and 8 roles are still accurate
  3. Implement: Copy `docs/agents.md` to `docs/reference/agents.md`; update the `PHILOSOPHY.md` link to `../about/the-custom-philosophy.md`; fix any other `tcs-start` references
  4. Validate: `grep "PHILOSOPHY.md" docs/reference/agents.md` → 0 results; `grep "tcs-start" docs/reference/agents.md` → 0 results
  5. Success: agents.md accurate with correct cross-links `[ref: SDD/Cross-Document Link Map]`

- [ ] **T2.5 Update reference/output-styles.md** `[activity: documentation]` `[parallel: true]`

  1. Prime: Read `docs/output-styles.md` (current) `[ref: SDD/CON-5 — namespace fix]`
  2. Test: Find all occurrences of `tcs-start:` or `start:` in the namespace position; list the correct replacements (`tcs-workflow:`)
  3. Implement: Copy `docs/output-styles.md` to `docs/reference/output-styles.md`; replace all `tcs-start:` and `start:` namespace prefixes with `tcs-workflow:`
  4. Validate: `grep "tcs-start\|start:" docs/reference/output-styles.md` → 0 results
  5. Success: All output-style invocations use `tcs-workflow:` namespace `[ref: SDD/CON-5]`

- [ ] **T2.6 Phase 2 Validation** `[activity: validate]`

  - `ls docs/reference/` → exactly 5 files: `agents.md`, `output-styles.md`, `plugins.md`, `skills.md`, `xdd.md`
  - `grep -r "tcs-start" docs/reference/ --include="*.md"` → 0 results
  - Confirm `reference/skills.md` lists 20 skills (count section headers)
  - Confirm `reference/xdd.md` mentions all 6 XDD skills by name
