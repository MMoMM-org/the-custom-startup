---
title: "Phase 2: Core Skill Workflow"
status: completed
version: "1.0"
phase: 2
---

# Phase 2: Core Skill Workflow

## Phase Context

**GATE**: Read all referenced files before starting this phase.

**Specification References**:
- `[ref: SDD/Solution Strategy]` — pipeline architecture pattern
- `[ref: SDD/Building Block View/Components]` — 6-phase workflow diagram
- `[ref: SDD/Runtime View/Primary Flow]` — full sequence diagram
- `[ref: SDD/Runtime View/Error Handling]` — error table
- `[ref: SDD/Architecture Decisions]` — all 4 ADRs
- `[ref: SDD/Acceptance Criteria]` — EARS criteria for all features
- Phase 1 deliverables: `reference/categorization.md`, `reference/scoring-rubric.md`, `reference/scope-rules.md`

**Key Decisions**:
- ADR-1: Pure skill — all workflow logic in SKILL.md, reference docs loaded per-phase
- ADR-3: In-place suffixed backups
- ADR-4: Non-blocking secret detection (warn in report)
- Skill frontmatter must match tcs-helper conventions (see existing memory-* skills)

**Dependencies**:
- Phase 1 must be complete — SKILL.md references the 3 reference docs by path

---

## Tasks

Delivers the complete SKILL.md with all 6 workflow phases and the example output document. This is the core deliverable of the specification.

- [x] **T2.1 SKILL.md — Frontmatter, Persona, Interface, Constraints** `[activity: skill-authoring]`

  1. Prime: Read existing skill patterns: `plugins/tcs-helper/skills/memory-cleanup/SKILL.md`, `plugins/tcs-helper/skills/memory-add/SKILL.md`, `plugins/tcs-helper/skills/setup/SKILL.md` `[ref: SDD/Building Block View/Directory Map]`. Read skill authoring reference at `~/.claude/includes/skills-reference.md`.
  2. Test: Verify frontmatter has: name (memory-claude-md-optimize), description (trigger keywords), user-invocable (true), argument-hint, allowed-tools. Verify Persona section identifies the active skill. Verify Interface section defines State and data types matching SDD entities. Verify Constraints section has Always/Never lists covering all SDD constraints (CON-1 through CON-6).
  3. Implement: Create `plugins/tcs-helper/skills/memory-claude-md-optimize/SKILL.md` with:
     - Frontmatter: name, description (include trigger words: optimize, migrate, audit, CLAUDE.md, memory bank, context), user-invocable: true, argument-hint: `[--dry-run] [--scope global|project|repo]`, allowed-tools: Read, Write, Edit, Bash, Glob, Grep, AskUserQuestion
     - Persona: "Act as a CLAUDE.md optimization specialist..."
     - Interface: State object, DiscoveredFile, QualityScore, CategorizedItem entities (from SDD data models)
     - Constraints: Always (non-destructive, backup before modify, user confirms every phase, load reference docs per-phase) / Never (modify without confirmation, hardcode project paths, overwrite existing memory content)
  4. Validate: Frontmatter fields match tcs-helper conventions. Interface types cover all SDD entities. Constraints include all CON-1 through CON-6.
  5. Success:
    - [ ] Skill file created with valid frontmatter `[ref: SDD/Building Block View/Directory Map]`
    - [ ] Interface matches SDD data models `[ref: SDD/Interface Specifications/Data Models]`
    - [ ] Constraints cover all SDD constraints CON-1 through CON-6 `[ref: SDD/Constraints]`

- [x] **T2.2 SKILL.md — Workflow Phases 1-3 (Discover, Score, Categorize)** `[activity: skill-authoring]`

  1. Prime: Read SDD runtime view `[ref: SDD/Runtime View/Primary Flow]`. Read SDD cascade discovery algorithm `[ref: SDD/Runtime View/Complex Logic]`. Read SDD scoring and categorization examples `[ref: SDD/Implementation Examples]`.
  2. Test: Verify workflow step 1 (Discover) handles: scope selection via AskUserQuestion, @-import chain following, project path discovery from imports, broken import warnings, file listing with scope/lines/tokens. Verify step 2 (Score) loads scoring-rubric.md, applies 6 criteria, produces grades. Verify step 3 (Categorize) loads categorization.md, classifies items, assesses scope fit.
  3. Implement: Add to SKILL.md:
     - **Step 1: Discover** — AskUserQuestion for scope, Glob for CLAUDE.md files, Read + scan for @-imports, recursive chain following, project dir discovery from imports, collect DiscoveredFile list, display summary table
     - **Step 2: Score** — Read reference/scoring-rubric.md, apply 6 criteria per file, compute total + grade, flag low scores and long files, display scores table
     - **Step 3: Categorize** — Read reference/categorization.md + reference/scope-rules.md, parse content into items, classify each by category + scope fit, flag cross-scope recommendations, detect credentials (ADR-4), display categorization summary
  4. Validate: Each step references the correct reference doc. Discovery handles all 3 starting scopes. Scoring covers all 6 criteria. Categorization covers all 6 categories. Error handling matches SDD error table.
  5. Success:
    - [ ] Discovery handles global, project, repo scopes with cascade `[ref: PRD/Feature 1]`
    - [ ] @-import chain following with cycle detection `[ref: PRD/Feature 1/AC-6]`
    - [ ] Quality scoring with 6 criteria and grade output `[ref: PRD/Feature 2]`
    - [ ] Content categorization into 6 Memory Bank categories `[ref: PRD/Feature 3]`
    - [ ] Credential detection with non-blocking warnings `[ref: SDD/Architecture Decisions/ADR-4]`

- [x] **T2.3 SKILL.md — Workflow Phases 4-6 (Propose, Apply, Verify)** `[activity: skill-authoring]`

  1. Prime: Read SDD proposal structure `[ref: SDD/Building Block View/Directory Map]` (Proposal Output component). Read SDD apply criteria `[ref: SDD/Acceptance Criteria]`. Read SDD OPTIMIZATION-REPORT example `[ref: SDD/Implementation Examples/OPTIMIZATION-REPORT]`. Read SDD before/after verification `[ref: PRD/Feature 8]`.
  2. Test: Verify step 4 (Propose) creates temp dir with g/p/r structure, generates OPTIMIZATION-REPORT.md, handles --dry-run exit. Verify step 5 (Apply) creates backups, places new files, creates Memory Bank if missing. Verify step 6 (Verify) computes before/after snapshots, generates verification prompt, offers temp dir cleanup.
  3. Implement: Add to SKILL.md:
     - **Step 4: Propose** — Check --dry-run (if set: print report, stop). Create claude-md-optimization/ dir. Write optimized CLAUDE.md files per scope. Write memory category files. Generate OPTIMIZATION-REPORT.md (scores, migrations, import replacements, secrets, before/after). AskUserQuestion: Apply / Edit first / Cancel.
     - **Step 5: Apply** — Create .backup-YYYYMMDD-HHMMSS for each original. Write new files to original locations. If docs/ai/memory/ missing: create from templates. Summary of backups created and files modified. Recommend /memory-sync --fix.
     - **Step 6: Verify** — Compute AFTER snapshot. Display before/after comparison table. Generate self-contained verification prompt (why new session needed, run /context + /memory, what to look for). AskUserQuestion: delete temp dir / archive / keep.
  4. Validate: Proposal structure matches SDD directory map. Backup naming matches ADR-3 convention. Verification prompt matches PRD Feature 8 acceptance criteria. Temp dir cleanup offers all 3 options.
  5. Success:
    - [ ] Proposal directory created with g/p/r structure `[ref: PRD/Feature 5]`
    - [ ] OPTIMIZATION-REPORT.md generated with all sections `[ref: PRD/Feature 5/AC-3]`
    - [ ] --dry-run stops after report, no files created `[ref: PRD/Feature 9]`
    - [ ] In-place backups with timestamp suffix `[ref: PRD/Feature 6/AC-1]`
    - [ ] Memory Bank structure created from templates if missing `[ref: PRD/Feature 6/AC-3]`
    - [ ] Before/After comparison with token savings `[ref: PRD/Feature 8/AC-1, AC-2]`
    - [ ] Verification prompt for new session `[ref: PRD/Feature 8/AC-4, AC-5, AC-6]`
    - [ ] Temp dir cleanup options (delete/archive/keep) `[ref: PRD/Feature 7]`

- [x] **T2.4 Output Example** `[activity: skill-authoring]` `[parallel: true]`

  1. Prime: Read SDD OPTIMIZATION-REPORT example `[ref: SDD/Implementation Examples/OPTIMIZATION-REPORT]`. Read existing skill examples in `plugins/tcs-helper/skills/*/examples/`.
  2. Test: Verify the example shows a complete run: discovery summary, quality scores table, categorization results, @-import replacements, secret warnings, before/after comparison, verification prompt.
  3. Implement: Create `plugins/tcs-helper/skills/memory-claude-md-optimize/examples/output-example.md` with a realistic sample showing all sections of the OPTIMIZATION-REPORT.
  4. Validate: Example covers all OPTIMIZATION-REPORT sections from SDD. Numbers are realistic and internally consistent.
  5. Success: Complete example that a user could reference to understand expected output `[ref: SDD/Implementation Examples/OPTIMIZATION-REPORT]`

- [x] **T2.5 Phase Validation** `[activity: validate]`

  - Read the complete SKILL.md. Verify all 6 workflow phases are present and complete. Verify reference doc paths are correct. Verify AskUserQuestion prompts match SDD interface spec. Verify error handling covers all cases from SDD error table. Run `/skill-author audit` to validate structure and quality.
