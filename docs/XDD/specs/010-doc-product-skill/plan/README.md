---
title: "doc-product Skill — Implementation Plan"
status: draft
version: "1.0"
---

# Implementation Plan

## Validation Checklist

### CRITICAL GATES (Must Pass)

- [ ] All `[NEEDS CLARIFICATION: ...]` markers have been addressed
- [ ] All specification file paths are correct and exist
- [ ] Each phase follows TDD: Prime → Test → Implement → Validate
- [ ] Every task has verifiable success criteria
- [ ] A developer could follow this plan independently

### QUALITY CHECKS (Should Pass)

- [ ] Context priming section is complete
- [ ] All implementation phases are defined with linked phase files
- [ ] Dependencies between phases are clear (no circular dependencies)
- [ ] Parallel work is properly tagged with `[parallel: true]`
- [ ] Activity hints provided for specialist selection `[activity: type]`
- [ ] Every phase references relevant SDD sections
- [ ] Every test references PRD acceptance criteria
- [ ] Integration & E2E tests defined in final phase
- [ ] Project commands match actual project setup

---

## Output Schema

(Same as template — omitted for brevity.)

---

## Specification Compliance Guidelines

### How to Ensure Specification Adherence

1. **Before Each Phase**: Complete the Pre-Implementation Specification Gate
2. **During Implementation**: Reference specific SDD sections in each task
3. **After Each Task**: Run Specification Compliance checks (`/spec-compliance-reviewer`)
4. **Phase Completion**: Verify all specification requirements are met

### Deviation Protocol

When implementation requires changes from the specification:
1. Document the deviation with clear rationale in the phase file's Deviations section
2. Surface the deviation to Marcus before proceeding
3. Update SDD when the deviation improves the design
4. Record all deviations in this plan for traceability

## Metadata Reference

- `[parallel: true]` — Tasks that can run concurrently
- `[component: name]` — For multi-component features (N/A here — single skill)
- `[ref: document/section]` — Links to specifications by section name (line ranges intentionally omitted — sections are stable, line numbers drift)
- `[activity: type]` — Activity hint for specialist selection

### Success Criteria

**Validate** = Process verification ("did we follow TDD?")
**Success** = Outcome verification ("does it work correctly?")

---

## Context Priming

*GATE: Read all files in this section before starting any implementation.*

**Specification:**
- `docs/XDD/specs/010-doc-product-skill/requirements.md` — Product Requirements (22 Gherkin ACs)
- `docs/XDD/specs/010-doc-product-skill/solution.md` — Solution Design (7 ADRs, ~25 EARS criteria)
- `docs/about/skill-and-agent-design.md` — TCS skill/agent design heuristics (governs this skill's architecture)
- `plugins/tcs-helper/skills/skill-author/reference/conventions.md` — TCS skill conventions
- `plugins/tcs-helper/skills/skill-author/reference/decision-tree.md` — Mechanism decision tree
- `~/.claude/rules/authoring.md` — User-global authoring rules (description quality, tool minimalism)

**Reference Implementations** (read before starting):
- `plugins/tcs-helper/skills/skill-author/SKILL.md` — Reference structure and PICS layout
- `plugins/tcs-helper/skills/finish-branch/SKILL.md` — Bash-orchestrated skill example
- `plugins/tcs-helper/skills/memory-add/SKILL.md` — Lightweight skill example

**Key Design Decisions** (from SDD ADRs, all confirmed 2026-05-06):
- **ADR-1**: Mode-router skill (one skill + four mode files via progressive disclosure)
- **ADR-2**: Reader-test via `claude -p` subprocess (not Agent tool dispatch)
- **ADR-3**: Stateless review (no persistence, no `.reader-test/` directory)
- **ADR-4**: Persona override = replace by default, opt-in `extends: defaults`
- **ADR-5**: Separate Bash parsers per source type, with explicit missing-dependency reporting
- **ADR-6**: Gap report Markdown rendered inline, never written to disk
- **ADR-7**: Single `/doc-product` slash command, modes as args (no per-mode shortcuts in v1)

**Implementation Context:**
```bash
# Skill-development workflow (from project CLAUDE.md)
# Skills are auto-discovered via plugin marketplace; never manually copy to cache.
# To make a new skill testable: bump plugin.json version, push, restart Claude Code.

# Manual skill smoke testing (during development, before plugin version bump):
bash plugins/tcs-helper/skills/doc-product/scripts/reader-test.sh \
  <persona-id> <question-id>

bash plugins/tcs-helper/skills/doc-product/scripts/parse-ts-settings.sh \
  <path-to-settings.ts>

# Quality (no project-wide linter, but skills must pass):
shellcheck plugins/tcs-helper/skills/doc-product/scripts/*.sh
markdownlint plugins/tcs-helper/skills/doc-product/**/*.md  # if installed

# Dependency check (per ADR-5):
command -v claude jq python3 node  # surfaces what's available

# Validation against TCS conventions:
# Invoke /skill-author audit on the new skill before committing
```

---

## Implementation Phases

Each phase is defined in a separate file. Tasks follow red-green-refactor: **Prime** (understand context), **Test** (red), **Implement** (green), **Validate** (refactor + verify).

> **Tracking Principle**: Track logical units that produce verifiable outcomes. The TDD cycle is the method, not separate tracked items.

- [x] [Phase 1: Skill Scaffold and Mode Router](phase-1.md)
- [x] [Phase 2: Review Mode and Reader-Test Engine](phase-2.md)
- [x] [Phase 3: Extract Mode and Settings Parsers](phase-3.md)
- [x] [Phase 4: Plan and Write Modes](phase-4.md)
- [ ] [Phase 5: Dogfood and Validation](phase-5.md)

**Sequencing rationale:**
- Phase 1 establishes the skill skeleton and mode-router contract; nothing else can be tested without it.
- Phase 2 (review) comes before extract/plan/write because it is the **killer feature** — earliest possible validation of the highest-risk component (`claude -p` subprocess orchestration). Failing here changes the v1 scope sooner.
- Phase 3 (extract) is the second-highest-value mode and shares no logic with review, making it cleanly parallelisable in calendar terms after Phase 2 lands.
- Phase 4 (plan + write) is mostly Markdown templates and conversational orchestration — least risky.
- Phase 5 (dogfood) only makes sense after all modes work, and it is the gate for declaring v1 done.

**Parallel opportunities within phases:**
- Phase 3 parsers (T3.1, T3.2, T3.3) can be built in parallel — three independent scripts with shared output format.
- Phase 4 plan mode (T4.2) and write mode (T4.3) can be built in parallel — different mode files, no shared state.
- Phase 5 dogfood tasks (T5.1, T5.2, T5.3) can run in parallel — independent target repos.

---

## Plan Verification

Before this plan is ready for implementation, verify:

| Criterion | Status |
|-----------|--------|
| A developer can follow this plan without additional clarification | ⬜ |
| Every task produces a verifiable deliverable | ⬜ |
| All PRD acceptance criteria map to specific tasks | ⬜ |
| All SDD components have implementation tasks | ⬜ |
| Dependencies are explicit with no circular references | ⬜ |
| Parallel opportunities are marked with `[parallel: true]` | ⬜ |
| Each task has specification references `[ref: ...]` | ⬜ |
| Project commands in Context Priming are accurate | ⬜ |
| All phase files exist and are linked from this manifest as `[Phase N: Title](phase-N.md)` | ⬜ |
