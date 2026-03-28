---
title: "Phase 1: Foundation and Getting Started"
status: pending
version: "1.0"
phase: 1
---

# Phase 1: Foundation and Getting Started

## Phase Context

**GATE**: Read all referenced files before starting this phase.

**Specification References**:
- `[ref: SDD/Directory Map]` — full file inventory and destination paths
- `[ref: SDD/Constraints]` — CON-1 through CON-5 (Markdown only, scope boundaries, namespace rules)
- `[ref: PRD/Feature 1]` — accurate v2 plugin references
- `[ref: PRD/Feature 2]` — tcs-patterns plugin documented

**Key Decisions**:
- ADR-1: Create `getting-started/`, `reference/`, `guides/`, `about/` subdirectories under `docs/`
- ADR-4: Read `docs/installation.md` as source before rewriting — do not paraphrase from memory

**Dependencies**:
- None — this is the first phase

---

## Tasks

Establishes the directory structure and the new user's primary entry point: `getting-started/`.

- [ ] **T1.1 Create directory scaffold** `[activity: documentation]`

  1. Prime: Read `docs/XDD/specs/006-docs-rewrite/solution.md` Directory Map section `[ref: SDD/Directory Map]`
  2. Test: Confirm none of the 4 subdirectories exist yet under `docs/`
  3. Implement: Create `docs/getting-started/`, `docs/reference/`, `docs/guides/`, `docs/about/` (empty directories with a `.gitkeep` each so they appear in git)
  4. Validate: `ls docs/` shows 4 new subdirectories alongside existing `XDD/`, `ai/`, `templates/`
  5. Success: Directory scaffold in place `[ref: SDD/Directory Map]`

- [ ] **T1.2 Write getting-started/index.md** `[activity: documentation]`

  1. Prime: Read `docs/plugins.md` (current 3-plugin description) and `README.md` (value prop section) `[ref: PRD/Feature 4 — IA]`
  2. Test: List what the page must contain: what is TCS, 4-plugin map (tcs-workflow · tcs-team · tcs-helper · tcs-patterns), when to use each, link to installation
  3. Implement: Write `docs/getting-started/index.md` — overview for a new user who has never seen TCS; no install steps (those are in installation.md); end with clear next steps
  4. Validate: Contains all 4 plugin names with correct namespaces; no mention of `tcs-start`; links to `installation.md` and `../reference/plugins.md`
  5. Success: A new user reading this file understands what TCS is and what to install `[ref: PRD/Primary User Journey step 1]`

- [ ] **T1.3 Write getting-started/installation.md** `[activity: documentation]`

  1. Prime: Read `docs/installation.md` (current) and `install.sh` first 80 lines to verify wizard prompts `[ref: PRD/Feature 1 — plugin name accuracy]`
  2. Test: Verify actual plugin identifiers in `plugins/*/`.claude-plugin/plugin.json`; confirm install commands match marketplace identifiers
  3. Implement: Rewrite `docs/getting-started/installation.md` — install script method first, marketplace method second; show all 4 plugins with correct namespaces (`tcs-workflow@the-custom-startup` etc.); tcs-patterns listed as optional with link to `../guides/tcs-patterns.md`
  4. Validate: `grep "tcs-start" docs/getting-started/installation.md` returns 0 results; all 4 plugin install commands present
  5. Success:
    - [ ] All install commands use `tcs-workflow@the-custom-startup` namespace `[ref: PRD/AC Feature 1]`
    - [ ] tcs-patterns listed as optional install `[ref: PRD/Feature 2]`

- [ ] **T1.4 Write CHANGELOG.md** `[activity: documentation]` `[parallel: true]`

  1. Prime: Check if `CHANGELOG.md` exists at repo root; read git log for key v2 milestones: `git log --oneline -20` `[ref: PRD/Should Have — CHANGELOG]`
  2. Test: List what v2.0 entry must contain: plugin rename (tcs-start → tcs-workflow), new tcs-patterns plugin, XDD workflow addition, docs restructure
  3. Implement: Create or update `CHANGELOG.md` at repo root; use Keep a Changelog format (`## [4.0.0] - 2026-03-28`); v2.0 section covers the 4 key changes; note prior history as "see git log"
  4. Validate: File exists at repo root (not inside docs/); v2.0 entry mentions all 4 key changes; format follows Keep a Changelog
  5. Success: CHANGELOG.md at repo root with accurate v2 entry `[ref: PRD/Should Have — CHANGELOG; SDD/ADR-3]`

- [ ] **T1.5 Phase 1 Validation** `[activity: validate]`

  - Run `grep -r "tcs-start" docs/getting-started/ --include="*.md"` → expect 0 results
  - Confirm `docs/getting-started/` has 3 files: `index.md`, `installation.md`, `quick-start.md` is NOT yet present (comes in Phase 3)
  - Confirm `CHANGELOG.md` exists at repo root
  - Confirm 4 subdirectories created under `docs/`
