---
title: "Phase 1: Reference Documents"
status: pending
version: "1.0"
phase: 1
---

# Phase 1: Reference Documents

## Phase Context

**GATE**: Read all referenced files before starting this phase.

**Specification References**:
- `[ref: SDD/Building Block View/Directory Map]` — skill directory structure
- `[ref: SDD/Implementation Examples/Content Categorization]` — categorization algorithm and traced walkthrough
- `[ref: SDD/Implementation Examples/Quality Scoring]` — scoring algorithm
- `[ref: SDD/Runtime View/Complex Logic]` — scope cascade discovery algorithm
- `[ref: PRD/Feature 2]` — quality scoring criteria (6 criteria, 0-100 scale)
- `[ref: PRD/Feature 3]` — content categorization (Memory Bank categories)
- `[ref: PRD/Detailed Feature Specifications]` — categorization business rules (Rules 1-8)

**Key Decisions**:
- ADR-2: Rubric-guided LLM categorization — reference docs provide definitions + signals + examples; Claude applies judgment
- Categories are the 6 Memory Bank types: general, tools, domain, decisions, context, troubleshooting

**Dependencies**:
- None — this is the first phase. Reference docs must be complete before Phase 2 starts.

---

## Tasks

Establishes the knowledge base that guides Claude's analysis during skill execution. Each reference doc is a standalone rubric loaded on-demand by the SKILL.md workflow.

- [ ] **T1.1 Categorization Reference** `[activity: domain-modeling]` `[parallel: true]`

  1. Prime: Read existing categorization signals in `plugins/tcs-helper/skills/memory-add/SKILL.md` `[ref: SDD/Implementation Examples/Content Categorization]`. Read Memory Bank templates in `plugins/tcs-helper/templates/memory-*.md` for category definitions. Read `plugins/tcs-helper/templates/routing-reference.md` for routing rules.
  2. Test: Verify the reference doc covers all 6 categories with: definition, signal keywords, 3+ examples per category, edge case guidance (multi-category items), scope-fit signals (generic vs specific)
  3. Implement: Create `plugins/tcs-helper/skills/memory-claude-md-optimize/reference/categorization.md` with category definitions, keyword signals (from PRD Rules 1-8), example items for each category, edge case resolution rules, and scope-fit assessment criteria
  4. Validate: Every PRD categorization rule (Rules 1-8) maps to a category entry. Every Memory Bank category has a section. Examples cover happy path and ambiguous cases.
  5. Success:
    - [ ] All 6 Memory Bank categories defined with signals and examples `[ref: PRD/Feature 3]`
    - [ ] PRD business rules 1-8 all represented `[ref: PRD/Detailed Feature Specifications]`
    - [ ] Scope-fit criteria (generic vs specific) defined with examples `[ref: PRD/Feature 3/AC-3, AC-4]`

- [ ] **T1.2 Quality Scoring Rubric** `[activity: domain-modeling]` `[parallel: true]`

  1. Prime: Read PRD Feature 2 scoring criteria `[ref: PRD/Feature 2]`. Read SDD scoring algorithm `[ref: SDD/Implementation Examples/Quality Scoring]`. Research Anthropic's claude-md-management plugin for scoring patterns (noted in PRD Supporting Research).
  2. Test: Verify the rubric covers all 6 criteria with: definition, point allocation, scoring guidance (what earns 0 / mid / full marks), grade boundaries, warning thresholds
  3. Implement: Create `plugins/tcs-helper/skills/memory-claude-md-optimize/reference/scoring-rubric.md` with 6 criteria definitions (commands/workflows 20pts, architecture clarity 20pts, non-obvious patterns 15pts, conciseness 15pts, currency 15pts, actionability 15pts), scoring levels for each, grade scale (A-F), line count warnings (150+, 200+)
  4. Validate: Point allocations sum to 100. Grade boundaries are consistent with PRD. Each criterion has clear differentiators between score levels.
  5. Success:
    - [ ] 6 criteria defined with point allocations summing to 100 `[ref: PRD/Feature 2/AC-1]`
    - [ ] Grade scale (A-F) with boundaries matches PRD `[ref: PRD/Feature 2/AC-2]`
    - [ ] Low-score guidance (below 50) with improvement suggestions `[ref: PRD/Feature 2/AC-3]`
    - [ ] Line count warning thresholds defined `[ref: PRD/Feature 2/AC-4]`

- [ ] **T1.3 Scope Rules Reference** `[activity: domain-modeling]` `[parallel: true]`

  1. Prime: Read SDD scope cascade algorithm `[ref: SDD/Runtime View/Complex Logic]`. Read SDD system context diagram `[ref: SDD/External Interfaces]`. Read existing scope patterns in `plugins/tcs-helper/skills/memory-add/SKILL.md` (scope determination section).
  2. Test: Verify the reference doc covers: 3 scope definitions (global/project/repo), cascade behavior for each starting scope, project directory discovery via @-imports (NOT hardcoded paths), file types per scope, scope-fit assessment (when to recommend moving content between scopes)
  3. Implement: Create `plugins/tcs-helper/skills/memory-claude-md-optimize/reference/scope-rules.md` with scope definitions, cascade rules, @-import following algorithm, project directory discovery (dynamic, from @-import chain), file type classification per scope, scope-fit decision tree
  4. Validate: All 3 scopes defined. Cascade logic matches SDD algorithm. Project path is discovered dynamically (never hardcoded). Global→project→repo cascade is clear.
  5. Success:
    - [ ] 3 scopes defined with file locations and discovery methods `[ref: PRD/Feature 1/AC-1 through AC-6]`
    - [ ] Cascade behavior documented for each starting scope `[ref: PRD/Feature 1/AC-2, AC-3, AC-4]`
    - [ ] Project directory discovered via @-imports, not hardcoded `[ref: SDD/Runtime View/Complex Logic]`
    - [ ] @-import resolution rules (relative, absolute, ~-prefixed) `[ref: PRD/Feature 1/AC-6]`

- [ ] **T1.4 Phase Validation** `[activity: validate]`

  - Read all 3 reference docs. Verify internal consistency (no contradictions between categorization signals and scope rules). Verify all PRD features 1-3 are addressable from the reference docs. Verify a developer implementing the SKILL.md could use these docs without further clarification.
