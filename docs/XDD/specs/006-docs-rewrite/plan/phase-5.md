---
title: "Phase 5: README, Cleanup, and Validation"
status: completed
version: "1.0"
phase: 5
---

# Phase 5: README, Cleanup, and Validation

## Phase Context

**GATE**: Read all referenced files before starting this phase. All phases 1-4 must be complete.

**Specification References**:
- `[ref: SDD/ADR-2]` — Clean delete: no redirects or symlinks for old paths
- `[ref: SDD/Constraints CON-3]` — README.md must retain ASCII header and "What's different" fork section
- `[ref: SDD/Quality Requirements]` — 0 tcs-start references; correct structure; link integrity
- `[ref: SDD/Acceptance Criteria]` — all 10 EARS criteria must pass

**Key Decisions**:
- ADR-2: Delete old files only after confirming new versions are in place (verify each new path exists before deleting old)
- ADR-3: CHANGELOG.md at repo root (already done in Phase 1; verify it's there before touching README)
- CON-3: Preserve ASCII art header verbatim in README.md

**Dependencies**:
- All of Phases 1, 2, 3, and 4 must be complete before starting this phase
- T5.1 (README rewrite) and T5.2 (deletions) can run in parallel, but T5.3 (link check) depends on both

---

## Tasks

Completes the rewrite: new README, delete all old files, verify link integrity, run final quality checks.

- [x] **T5.1 Rewrite README.md** `[activity: documentation]`

  1. Prime: Read current `README.md` — note the ASCII art header (preserve verbatim) and "What's different" section (update, not delete); read `docs/getting-started/index.md` (T1.2) for value prop language to reuse `[ref: SDD/CON-3; SDD/Cross-Document Link Map]`
  2. Test: List what must change: (a) plugin count 3→4, (b) `tcs-start` → `tcs-workflow`, (c) feature list updated (XDD, tcs-patterns), (d) "What's different" section updated with v2 changes, (e) Quick Start commands use v2 namespace, (f) links to new doc paths
  3. Implement: Rewrite `README.md` — keep ASCII art verbatim; update value prop for 4-plugin v2; update install example; update Quick Start commands; link to `docs/getting-started/index.md`; update "What's different" to mention v2 additions (XDD, tcs-patterns); add link to `CHANGELOG.md`
  4. Validate: ASCII art header intact; `grep "tcs-start" README.md` → 0 results; all doc links point to new paths in `docs/getting-started/` or `docs/reference/`
  5. Success:
    - [ ] ASCII header preserved verbatim `[ref: SDD/CON-3]`
    - [ ] "What's different" section updated and links to `about/sources.md` `[ref: PRD/Feature 5]`
    - [ ] All doc links point to new IA paths `[ref: SDD/Cross-Document Link Map]`

- [x] **T5.2 Delete old files** `[activity: documentation]` `[parallel: true]`

  1. Prime: Read `docs/XDD/specs/006-docs-rewrite/solution.md` "Files to delete" list; verify each replacement file exists at its new path before deleting its old counterpart `[ref: SDD/ADR-2; SDD/Directory Map]`
  2. Test: For each file to delete, confirm the replacement exists:
     - `docs/index.md` → superseded by `docs/getting-started/index.md` ✓?
     - `docs/concepts.md` → content folded into getting-started/index.md ✓?
     - `docs/workflow.md` → replaced by `docs/getting-started/workflow.md` ✓?
     - `docs/skills.md` → replaced by `docs/reference/skills.md` ✓?
     - `docs/plugins.md` → replaced by `docs/reference/plugins.md` ✓?
     - `docs/agents.md` → replaced by `docs/reference/agents.md` ✓?
     - `docs/output-styles.md` → replaced by `docs/reference/output-styles.md` ✓?
     - `docs/installation.md` → replaced by `docs/getting-started/installation.md` ✓?
     - `docs/multi-ai-workflow.md` → moved to `docs/guides/multi-ai-workflow.md` ✓?
     - `docs/statusline.md` + `statusline-starship.md` + `statusline-starship-reddit.md` → merged to `docs/guides/statusline.md` ✓?
     - `docs/PHILOSOPHY.md` → superseded by `docs/about/the-custom-philosophy.md` ✓?
     - `docs/the-custom-philosophy.md` → moved to `docs/about/` ✓?
     - `docs/PRINCIPLES.md` → moved to `docs/about/principles.md` ✓?
  3. Implement: Delete all confirmed-replaced files; delete `docs/concept/` and `docs/concept/v2/` directories (content already promoted in Phase 4); delete `docs/index.md` and `docs/concepts.md`
  4. Validate: `ls docs/` → shows only: `getting-started/` `reference/` `guides/` `about/` `XDD/` `ai/` `templates/`; no loose `.md` files at `docs/` root
  5. Success:
    - [ ] `docs/` root contains no loose `.md` files `[ref: SDD/Quality Requirements]`
    - [ ] `docs/concept/` and `docs/concept/v2/` deleted `[ref: PRD/Feature 4 — promote then delete]`

- [x] **T5.3 Link integrity check** `[activity: validate]`

  1. Prime: Understand which docs link to which — read `docs/XDD/specs/006-docs-rewrite/solution.md` Cross-Document Link Map
  2. Test: For each link in the Link Map, verify source file and destination file both exist
  3. Implement: Scan for broken links:
     ```bash
     # Find all markdown links pointing into docs/
     grep -rn "](docs/" docs/ README.md --include="*.md"
     # For each link found, verify the target file exists
     ```
     Fix any broken links found (update path, not delete the link).
  4. Validate: All internal doc links resolve; no references to deleted file paths (`docs/workflow.md`, `docs/skills.md`, etc.)
  5. Success: Zero broken internal links `[ref: SDD/Quality Requirements — link integrity]`

- [x] **T5.4 Final quality validation** `[activity: validate]`

  Run all acceptance criteria checks from the SDD:

  ```bash
  # AC: Plugin name accuracy
  grep -r "tcs-start" docs/ README.md --include="*.md"   # expect: 0 results

  # AC: Completeness — skill count (adjust pattern to match actual heading structure)
  grep -c "^### \`\|^#### \`" docs/reference/skills.md    # expect: ≥ 20

  # AC: Completeness — xdd skills
  for skill in xdd xdd-meta xdd-prd xdd-sdd xdd-plan xdd-tdd; do
    grep -l "$skill" docs/reference/xdd.md && echo "$skill ✓" || echo "$skill MISSING"
  done

  # AC: Structure
  ls docs/   # expect: getting-started/ reference/ guides/ about/ XDD/ ai/ templates/ (no loose .md files)

  # AC: CHANGELOG exists at root
  test -f CHANGELOG.md && echo "CHANGELOG ✓" || echo "CHANGELOG MISSING"

  # AC: Attribution
  grep "rsmdt\|the-startup" docs/about/sources.md         # expect: match found
  ```

  5. Success: All SDD Acceptance Criteria pass `[ref: SDD/Acceptance Criteria — all 10 EARS criteria]`

- [x] **T5.5 Update spec README** `[activity: validate]`

  1. Update `docs/XDD/specs/006-docs-rewrite/README.md`:
     - Set `plan/` status to `completed`
     - Set Current Phase to `Ready`
     - Log final decision: "Implementation complete, all acceptance criteria pass"
  2. Commit all changes with message: `docs(rewrite): complete TCS v2 documentation restructure`
