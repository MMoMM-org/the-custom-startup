---
title: "Phase 3: Integration & Validation"
status: pending
version: "1.0"
phase: 3
---

# Phase 3: Integration & Validation

## Phase Context

**GATE**: Read all referenced files before starting this phase.

**Specification References**:
- `[ref: SDD/Quality Requirements]` — measurable quality targets
- `[ref: SDD/Acceptance Criteria]` — all EARS criteria
- `[ref: PRD/Success Metrics]` — KPIs and tracking requirements
- `[ref: PRD/Features 10-11]` — re-optimization and AGENTS.md handling
- Complete Phase 2 deliverables: SKILL.md, output-example.md

**Key Decisions**:
- Skill-author audit is mandatory before any skill commit (project feedback memory)
- Manual testing via actual invocation — no automated test framework for skills
- Documentation update required per global CLAUDE.md rules

**Dependencies**:
- Phase 2 must be complete — SKILL.md must be finalized before validation

---

## Tasks

Validates the complete skill against specifications, tests it with real CLAUDE.md files, and integrates it into the tcs-helper plugin.

- [ ] **T3.1 Skill-Author Audit** `[activity: validate]`

  1. Prime: Read skill authoring reference at `~/.claude/includes/skills-reference.md` `[ref: SDD/Cross-Cutting Concepts/Pattern Documentation]`. Read the complete SKILL.md and all reference docs.
  2. Test: Run `/skill-author audit` on the new skill. Verify: frontmatter is valid, description triggers on expected keywords, allowed-tools list is complete, workflow steps are numbered, constraints are actionable.
  3. Implement: Fix any issues flagged by skill-author audit. Iterate until audit passes clean.
  4. Validate: Skill-author audit passes with no errors or warnings.
  5. Success: `/skill-author audit` passes clean `[ref: SDD/Project Commands]`

- [ ] **T3.2 Dry Run Validation** `[activity: validate]`

  1. Prime: Read the SKILL.md workflow, focusing on phases 1-3 (Discover, Score, Categorize) `[ref: SDD/Runtime View/Primary Flow]`.
  2. Test: Invoke `/memory-claude-md-optimize --dry-run` on the current repo. Verify: scope selection prompt appears, discovery finds CLAUDE.md and memory files, quality scores are generated for each file, content is categorized into Memory Bank categories, no files are created (dry-run mode).
  3. Implement: Fix any workflow issues discovered during dry-run testing. Adjust reference docs if categorization or scoring produces unexpected results.
  4. Validate: Dry-run completes without errors. Output matches expected format from output-example.md. No files were created or modified.
  5. Success:
    - [ ] Scope selection works via AskUserQuestion `[ref: PRD/Feature 1/AC-1]`
    - [ ] Discovery finds all CLAUDE.md and memory files `[ref: PRD/Feature 1/AC-7]`
    - [ ] Quality scores are computed and displayed `[ref: PRD/Feature 2]`
    - [ ] Content is categorized correctly `[ref: PRD/Feature 3]`
    - [ ] No files created in dry-run mode `[ref: PRD/Feature 9]`

- [ ] **T3.3 Full Run Validation** `[activity: validate]`

  1. Prime: Read SDD apply and verify phases `[ref: SDD/Runtime View/Primary Flow]`. Read SDD backup convention `[ref: SDD/Architecture Decisions/ADR-3]`.
  2. Test: Invoke `/memory-claude-md-optimize` (full run, repo scope) on the current repo. Verify: proposal directory is created with correct structure, OPTIMIZATION-REPORT.md contains all sections, apply creates backups with correct naming, new files are placed in correct locations, before/after comparison shows token savings, verification prompt is generated, temp dir cleanup works.
  3. Implement: Fix any issues discovered during full validation. Verify backups can be used for manual rollback.
  4. Validate: Full run completes end-to-end. Backups exist for all modified files. Memory Bank structure is valid (run `/memory-sync` to verify). Before/after metrics are realistic.
  5. Success:
    - [ ] Proposal directory matches SDD structure `[ref: PRD/Feature 5/AC-1, AC-2]`
    - [ ] OPTIMIZATION-REPORT has all sections `[ref: PRD/Feature 5/AC-3]`
    - [ ] Backups created with .backup-YYYYMMDD-HHMMSS suffix `[ref: PRD/Feature 6/AC-1]`
    - [ ] Before/After snapshot with token savings `[ref: PRD/Feature 8/AC-1, AC-2]`
    - [ ] Verification prompt generated `[ref: PRD/Feature 8/AC-4]`
    - [ ] Temp dir cleanup options work `[ref: PRD/Feature 7]`

- [ ] **T3.4 Re-Optimization Validation** `[activity: validate]`

  1. Prime: Read PRD Feature 10 (incremental re-optimization) `[ref: PRD/Feature 10]`. Read SDD alternative flow for existing Memory Bank `[ref: SDD/Runtime View/Primary Flow]`.
  2. Test: After T3.3 (Memory Bank now exists), invoke `/memory-claude-md-optimize --dry-run` again. Verify: existing memory content is recognized as already-categorized, new CLAUDE.md content is proposed as additions (not overwrites), stale/duplicate detection recommends /memory-cleanup.
  3. Implement: Fix any issues with re-optimization flow.
  4. Validate: Re-run produces additive proposals. Existing memory entries are preserved. /memory-cleanup recommendation appears when appropriate.
  5. Success:
    - [ ] Existing memory content treated as already-categorized `[ref: PRD/Feature 10/AC-1]`
    - [ ] New content proposed as additions, not overwrites `[ref: PRD/Feature 10/AC-1]`
    - [ ] Recommends /memory-cleanup for maintenance `[ref: PRD/Feature 10/AC-2]`

- [ ] **T3.5 Documentation & Commit** `[activity: documentation]`

  1. Prime: Read global CLAUDE.md rules (update README and docs when shipping). Read spec README for decision log updates.
  2. Test: Verify README mentions the new skill. Verify spec README has all decisions logged. Verify any relevant documentation is updated.
  3. Implement: Update tcs-helper README (if it exists) to list the new skill. Update spec 008 README to mark plan as completed. Ensure CLAUDE.md routing rules mention the new skill where appropriate.
  4. Validate: All documentation references are accurate. Commit includes all new files.
  5. Success:
    - [ ] Documentation updated with new skill reference
    - [ ] Spec 008 README reflects completed status
    - [ ] All files committed to feat/memory-claude-md-optimize branch

- [ ] **T3.6 Phase Validation** `[activity: validate]`

  - Run `/memory-sync` to verify Memory Bank integrity after full validation. Verify all PRD acceptance criteria are satisfied (cross-reference PRD Features 1-11 against test results). Verify all SDD quality requirements are met (context savings 30%+, quality score improvement 20+, zero data loss). Final skill-author audit passes clean.
