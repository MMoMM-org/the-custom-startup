---
title: "Phase 2: XDD Skill Family Renames"
status: pending
version: "1.0"
phase: 2
---

# Phase 2: XDD Skill Family Renames

## Phase Context

**GATE**: Read all referenced files before starting this phase. Phase 1 must be complete.

**Specification References**:
- `[ref: SDD/Building Block View/Directory Map/tcs-workflow; lines: 175-218]` — xdd-* rename targets
- `[ref: SDD/Interface Specifications/Skill Frontmatter Contracts; lines: 285+]` — updated frontmatter per skill
- `[ref: SDD/Constraints/CON-4]` — skill-author mandatory for all skill modifications
- `[ref: PRD/Feature 11]` — XDD skill family (xdd, xdd-prd, xdd-sdd, xdd-plan, xdd-meta)
- `[ref: PRD/Implementation Principles]` — skill-author for all new/modified skills

**Key Decisions**:
- ADR-1: git mv for renames — preserves history. Apply same approach: `git mv skills/specify skills/xdd`, etc.
- CON-4: After rename, each skill's SKILL.md must be updated via `/tcs-helper:skill-author` — no hand-crafting.
- All 5 renames are independent of each other → `[parallel: true]`

**Dependencies**:
- Phase 1 complete (plugin directory exists as `tcs-workflow`, `docs/XDD/` exists, migration done)

---

## Tasks

Renames the specify-* skill family to xdd-* using `git mv`, then updates each SKILL.md via `skill-author` to reference the new names, updated paths (`docs/XDD/specs/`), and updated invocation patterns. All 5 rename tasks are fully independent and can run in parallel.

- [ ] **T2.1 Rename specify/ → xdd/ and update SKILL.md** `[activity: backend-api]` `[parallel: true]`

  1. Prime: Read `plugins/tcs-workflow/skills/specify/SKILL.md` (post-Phase-1 path). Note all internal references to old skill names (`/specify-requirements`, `/specify-solution`, `/specify-plan`). `[ref: SDD/Directory Map; line: 205-206]`
  2. Test: `plugins/tcs-workflow/skills/xdd/` exists; `plugins/tcs-workflow/skills/specify/` is absent. `xdd/SKILL.md` frontmatter `name: xdd`. References to sub-skills use new names: `/xdd-prd`, `/xdd-sdd`, `/xdd-plan`. Invocable as `tcs-workflow:xdd`. `[ref: PRD/Feature 11/AC-11.1]`
  3. Implement: `git mv plugins/tcs-workflow/skills/specify plugins/tcs-workflow/skills/xdd`. Invoke `/tcs-helper:skill-author` to update `SKILL.md`: rename frontmatter `name: xdd`, update all sub-skill invocations to new names, update any `docs/specs/` references to `docs/XDD/specs/`. `[ref: SDD/CON-4]`
  4. Validate: `git log --follow plugins/tcs-workflow/skills/xdd/SKILL.md` shows pre-rename history. `rg "specify-requirements|specify-solution|specify-plan" plugins/tcs-workflow/skills/xdd/` returns 0. Frontmatter `name: xdd`. `[ref: PRD/Feature 11/AC-11.1]`
  5. Success: `skills/xdd/SKILL.md` exists with updated frontmatter and references `[ref: PRD/Feature 11/AC-11.1]`; git history preserved `[ref: SDD/ADR-1]`; updated via skill-author `[ref: SDD/CON-4]`

- [ ] **T2.2 Rename specify-requirements/ → xdd-prd/ and update SKILL.md** `[activity: backend-api]` `[parallel: true]`

  1. Prime: Read `plugins/tcs-workflow/skills/specify-requirements/SKILL.md`. Note current docs path references (`.start/specs/`, `docs/specs/`). Note skill name in frontmatter. `[ref: SDD/Directory Map; line: 209-210]`
  2. Test: `plugins/tcs-workflow/skills/xdd-prd/` exists; `specify-requirements/` absent. `SKILL.md` frontmatter `name: xdd-prd`. All path references use `docs/XDD/specs/`. Invocable as `tcs-workflow:xdd-prd`. `[ref: PRD/Feature 11/AC-11.2]`
  3. Implement: `git mv plugins/tcs-workflow/skills/specify-requirements plugins/tcs-workflow/skills/xdd-prd`. Invoke `/tcs-helper:skill-author` to update frontmatter and all path references to `docs/XDD/specs/`. `[ref: SDD/CON-4]`
  4. Validate: Git history intact. `rg "specify-requirements\|.start/specs" plugins/tcs-workflow/skills/xdd-prd/` returns 0. Frontmatter `name: xdd-prd`. `[ref: PRD/Feature 11/AC-11.2]`
  5. Success: `skills/xdd-prd/SKILL.md` updated with new name and correct paths `[ref: PRD/Feature 11/AC-11.2]`; authored via skill-author `[ref: SDD/CON-4]`

- [ ] **T2.3 Rename specify-solution/ → xdd-sdd/ and update SKILL.md** `[activity: backend-api]` `[parallel: true]`

  1. Prime: Read `plugins/tcs-workflow/skills/specify-solution/SKILL.md`. Note path references and sub-skill invocations. `[ref: SDD/Directory Map; line: 211-212]`
  2. Test: `plugins/tcs-workflow/skills/xdd-sdd/` exists; `specify-solution/` absent. `SKILL.md` frontmatter `name: xdd-sdd`. Path references use `docs/XDD/specs/`. Invocable as `tcs-workflow:xdd-sdd`. `[ref: PRD/Feature 11/AC-11.3]`
  3. Implement: `git mv plugins/tcs-workflow/skills/specify-solution plugins/tcs-workflow/skills/xdd-sdd`. Invoke `/tcs-helper:skill-author` to update frontmatter and paths. `[ref: SDD/CON-4]`
  4. Validate: Git history intact. `rg "specify-solution\|.start/specs" plugins/tcs-workflow/skills/xdd-sdd/` returns 0. Frontmatter `name: xdd-sdd`. `[ref: PRD/Feature 11/AC-11.3]`
  5. Success: `skills/xdd-sdd/SKILL.md` updated `[ref: PRD/Feature 11/AC-11.3]`; authored via skill-author `[ref: SDD/CON-4]`

- [ ] **T2.4 Rename specify-plan/ → xdd-plan/ and update SKILL.md** `[activity: backend-api]` `[parallel: true]`

  1. Prime: Read `plugins/tcs-workflow/skills/specify-plan/SKILL.md` and its `reference/`, `templates/`, `examples/` subdirectories. Note all path references and skill invocations. `[ref: SDD/Directory Map; line: 213-214]`
  2. Test: `plugins/tcs-workflow/skills/xdd-plan/` exists; `specify-plan/` absent. `SKILL.md` frontmatter `name: xdd-plan`. Plan output path uses `docs/XDD/specs/`. Invocable as `tcs-workflow:xdd-plan`. `[ref: PRD/Feature 11/AC-11.4]`
  3. Implement: `git mv plugins/tcs-workflow/skills/specify-plan plugins/tcs-workflow/skills/xdd-plan`. Invoke `/tcs-helper:skill-author` to update frontmatter and all path references including those in `reference/` and `templates/` subdirs. `[ref: SDD/CON-4]`
  4. Validate: Git history intact for all subdir files. `rg "specify-plan\|.start/specs" plugins/tcs-workflow/skills/xdd-plan/` returns 0. Frontmatter `name: xdd-plan`. `[ref: PRD/Feature 11/AC-11.4]`
  5. Success: `skills/xdd-plan/` fully renamed and updated `[ref: PRD/Feature 11/AC-11.4]`; subdirectory references updated `[ref: SDD/CON-4]`

- [ ] **T2.5 Rename/update xdd-meta/ SKILL.md for startup.toml resolution** `[activity: backend-api]` `[parallel: true]`

  1. Prime: Read `plugins/tcs-workflow/skills/xdd-meta/SKILL.md` (already renamed in Phase 1 from `specify-meta`). Re-read `[ref: SDD/Interface Specifications/startup.toml Schema; lines: 265-283]` for resolution logic. This task adds the actual startup.toml-aware path resolution that was specified in T1.2. `[ref: SDD/Directory Map; line: 207-208]`
  2. Test: `xdd-meta/SKILL.md` frontmatter `name: xdd-meta`. Resolution algorithm: (1) check `.claude/startup.toml` for `docs_base`; (2) fall back to `docs/XDD`. Derived paths: `{docs_base}/specs`, `{docs_base}/adr`, `{docs_base}/ideas`. All bash resolution uses only bash 3.2 constructs (grep/sed, no TOML library). `[ref: PRD/Feature 15/AC-15.3]`
  3. Implement: Invoke `/tcs-helper:skill-author` to update `xdd-meta/SKILL.md`: add startup.toml resolution bash block (read `[tcs]` section with `grep`/`sed`); export `TCS_DOCS_BASE`, `TCS_SPECS_DIR`, `TCS_ADR_DIR`, `TCS_IDEAS_DIR` for downstream skills; update all spec-directory references. `[ref: SDD/CON-4, CON-1]`
  4. Validate: Manual test: with `.claude/startup.toml` containing `docs_base = "custom"`, xdd-meta resolves to `custom/specs`. Without file, resolves to `docs/XDD/specs`. `rg "\.start/specs\|docs/specs[^/]" plugins/tcs-workflow/skills/xdd-meta/` returns 0. `[ref: PRD/Feature 15/AC-15.3]`
  5. Success: `xdd-meta` reads startup.toml and exposes `TCS_*` env vars `[ref: PRD/Feature 15/AC-15.3]`; bash 3.2 compatible `[ref: SDD/CON-1]`; authored via skill-author `[ref: SDD/CON-4]`

- [ ] **T2.6 Phase 2 Validation** `[activity: validate]`

  - `ls plugins/tcs-workflow/skills/` — `xdd/`, `xdd-prd/`, `xdd-sdd/`, `xdd-plan/`, `xdd-meta/` present; `specify/`, `specify-requirements/`, `specify-solution/`, `specify-plan/` absent.
  - `rg "specify-requirements|specify-solution|specify-plan|specify/" plugins/tcs-workflow/skills/xdd*/` returns 0.
  - `rg "\.start/specs" plugins/tcs-workflow/skills/` returns 0.
  - All 5 renamed skills: frontmatter `name:` field matches directory name.
  - Git history intact: `git log --follow plugins/tcs-workflow/skills/xdd-prd/SKILL.md` shows pre-rename commits.
  - xdd-meta resolution: `.claude/startup.toml` with custom `docs_base` resolves correctly.
  - All Phase 2 PRD acceptance criteria: Feature 11 (AC-11.1–AC-11.5) verifiably met.
