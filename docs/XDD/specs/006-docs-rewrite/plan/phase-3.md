---
title: "Phase 3: Workflow and Patterns"
status: pending
version: "1.0"
phase: 3
---

# Phase 3: Workflow and Patterns

## Phase Context

**GATE**: Read all referenced files before starting this phase.

**Specification References**:
- `[ref: SDD/Directory Map — getting-started/workflow.md; guides/]` — 4 files: workflow.md, quick-start.md, tcs-patterns.md, multi-ai-workflow.md, statusline.md
- `[ref: SDD/ADR-4]` — SKILL.md as source of truth for tcs-patterns skill descriptions
- `[ref: SDD/Implementation Gotchas]` — statusline.md merge: read all 3 source files; tcs-patterns: glob actual SKILL.md files

**Key Decisions**:
- ADR-4: Glob `plugins/tcs-patterns/skills/*/SKILL.md` before writing `guides/tcs-patterns.md` — never paraphrase from memory
- T3.2 (quick-start.md) depends on T3.1 (workflow.md) — write workflow.md first

**Dependencies**:
- Phase 1 complete (directory scaffold exists)
- T3.1 must complete before T3.2 (quick-start links to and builds on workflow.md)
- T3.3, T3.4, T3.5 are independent and can run in parallel with each other (and with T3.1)

---

## Tasks

Builds the workflow guidance (how to use TCS) and the patterns guide (which optional skills to add).

- [ ] **T3.1 Write getting-started/workflow.md** `[activity: documentation]`

  1. Prime: Read `docs/workflow.md` (current BUILD loop diagram and steps); read `docs/XDD/specs/006-docs-rewrite/solution.md` for XDD-first framing `[ref: PRD/Primary User Journey step 3]`
  2. Test: List what must change: (a) all `tcs-start` references removed, (b) XDD workflow presented as the primary specify path, (c) link to `../reference/xdd.md` for deep dive, (d) MAINTAIN loop commands verified accurate
  3. Implement: Rewrite `docs/getting-started/workflow.md` — keep the ASCII/Mermaid BUILD loop diagram (updated for v2); expand SPECIFY step to show XDD path; add link to `../reference/xdd.md`; update all slash command namespaces to `tcs-workflow:`
  4. Validate: `grep "tcs-start" docs/getting-started/workflow.md` → 0 results; XDD section links to `../reference/xdd.md`
  5. Success: Workflow accurately describes v2 BUILD loop including XDD entry point `[ref: PRD/AC Feature 1; PRD/Primary User Journey step 3]`

- [ ] **T3.2 Write getting-started/quick-start.md** `[activity: documentation]`

  1. Prime: Read `docs/getting-started/workflow.md` (just written in T3.1) and `docs/getting-started/installation.md` (T1.3) — quick-start builds on both `[ref: PRD/Should Have — Quick-start walkthrough]`
  2. Test: Outline the walkthrough: install → set output style → optional constitution → run /specify on a generic task → run /validate → run /implement → celebrate; confirm all commands use `tcs-workflow:` namespace
  3. Implement: Write `docs/getting-started/quick-start.md` — use generic placeholder project (not a real example); step-by-step with exact commands; expected output for each step; troubleshooting note for common errors
  4. Validate: All commands use correct v2 namespaces; no real-project content that could become stale; links back to `workflow.md` and `../reference/skills.md`
  5. Success: A new user can follow this guide and complete their first TCS workflow `[ref: PRD/Should Have; PRD/Primary User Journey steps 3-4]`

- [ ] **T3.3 Write guides/tcs-patterns.md** `[activity: documentation]` `[parallel: true]`

  1. Prime: Glob `plugins/tcs-patterns/skills/*/SKILL.md`; read each file's frontmatter `name` and `description` (first 10 lines); group into categories: Architecture, API & Types, Testing, Platforms, DevOps, Integrations `[ref: PRD/Feature 2; SDD/ADR-4]`
  2. Test: Confirm exactly 17 skills across the 6 categories; note which have `user-invocable: true`; record the `argument-hint` for each to show users how to invoke
  3. Implement: Write `docs/guides/tcs-patterns.md` — intro explaining the plugin is selective-install (install only what you need); 6 category sections each with a table (skill name, what it does, when to use, invocation example); install command at top
  4. Validate: Exactly 17 skills listed; `grep "tcs-start" docs/guides/tcs-patterns.md` → 0 results; install command uses correct namespace
  5. Success:
    - [ ] All 17 tcs-patterns skills documented with when/why guidance `[ref: PRD/AC Feature 2]`
    - [ ] Install command accurate `[ref: PRD/AC Feature 1]`

- [ ] **T3.4 Move guides/multi-ai-workflow.md** `[activity: documentation]` `[parallel: true]`

  1. Prime: Read `docs/multi-ai-workflow.md` (current) — assess if any `tcs-start` references exist `[ref: SDD/Directory Map]`
  2. Test: Identify any stale plugin name references; verify all export/import script paths are still accurate
  3. Implement: Copy `docs/multi-ai-workflow.md` to `docs/guides/multi-ai-workflow.md`; fix any `tcs-start` references; verify script paths (`scripts/export-spec.sh`, `scripts/import-spec.sh`) still exist
  4. Validate: `grep "tcs-start" docs/guides/multi-ai-workflow.md` → 0 results; script paths verified
  5. Success: multi-ai-workflow.md in correct location with accurate content `[ref: SDD/Directory Map]`

- [ ] **T3.5 Merge guides/statusline.md** `[activity: documentation]` `[parallel: true]`

  1. Prime: Read all 3 source files: `docs/statusline.md`, `docs/statusline-starship.md`, `docs/statusline-starship-reddit.md` — note unique content in each (starship-reddit has specific setup notes not in the main file) `[ref: SDD/Implementation Gotchas]`
  2. Test: Identify content in `statusline-starship-reddit.md` that exists nowhere else; plan merge structure: Standard → Enhanced → Starship → Starship Reddit variant
  3. Implement: Write `docs/guides/statusline.md` — merged single doc with 4 sections (standard, enhanced with budget bar, Starship, Starship Reddit); include all unique content from each source; reference `statusline.toml` config format
  4. Validate: All unique content from all 3 source files is present in the merged file; no duplicate sections
  5. Success: Single comprehensive statusline guide with no content loss `[ref: PRD/Should Have — merged statusline]`

- [ ] **T3.6 Phase 3 Validation** `[activity: validate]`

  - `ls docs/getting-started/` → 4 files: `index.md`, `installation.md`, `quick-start.md`, `workflow.md`
  - `ls docs/guides/` → 3 files: `multi-ai-workflow.md`, `statusline.md`, `tcs-patterns.md`
  - `grep -r "tcs-start" docs/getting-started/ docs/guides/ --include="*.md"` → 0 results
  - Confirm `guides/tcs-patterns.md` mentions all 17 skills (count entries)
