---
title: "Phase 4: Plan and Write Modes"
status: pending
version: "1.0"
phase: 4
---

# Phase 4: Plan and Write Modes

## Phase Context

**GATE**: Read all referenced files before starting this phase.

**Specification References**:
- `[ref: SDD/Building Block View — Directory Map]` — templates/skeleton-* location
- `[ref: SDD/Acceptance Criteria — Plan mode]` — EARS for plan
- `[ref: SDD/Acceptance Criteria — Write mode]` — EARS for write
- `[ref: PRD/Feature 1 — plan mode]` — PRD ACs for plan
- `[ref: PRD/Feature 2 — write mode]` — PRD ACs for write
- `[ref: SDD/Quality Requirements — Usability]` — no surprise file writes principle

**Key Decisions**:
- Plan mode: propose-then-confirm; never overwrite silently. Diff against existing `docs/` and offer Keep / Replace / Merge per page.
- Plan mode never fabricates content — placeholder files only with TODO headers.
- Write mode: section structure first, then iterative section drafting. After 3 iterations on the same section without change, ask "can anything be removed?".
- Write mode preserves prior approved sections during iteration.
- Repo-type detection drives skeleton selection: Obsidian (manifest.json), Python (pyproject.toml), TCS plugin (plugin.json), generic fallback.

**Dependencies**:
- Phase 1 (skeleton exists; `modes/plan.md` and `modes/write.md` stubs will be replaced).
- Independent of Phases 2 and 3.

---

## Tasks

This phase delivers working `plan` and `write` modes. Verifiable outcome: `/doc-product plan` against an Obsidian plugin produces a docs/ skeleton proposal; `/doc-product write installation` drafts a clean installation page through guided dialogue.

- [ ] **T4.1 Skeleton Templates (4 repo types)** `[activity: template-design]` `[parallel: true]`

  1. **Prime**: Inspect `miyo-kado/docs/` (the reference for "good") and `miyo-tomo/README.md` (the anti-pattern). Read SDD `[ref: SDD/Directory Map — templates/]`.
  2. **Test**: Each skeleton template specifies the same minimum page set (installation, configuration, usage, troubleshooting) plus type-specific additions (e.g. TCS plugin gets per-component reference; Python gets a "first command" page). Each template includes a top-level `docs/README.md` index that links to all topic pages. By inspection: minimum pages present in every template; type-specific extras documented.
  3. **Implement**: Author `templates/skeleton-obsidian.md`, `skeleton-python.md`, `skeleton-tcs-plugin.md`, `skeleton-generic.md`. Each is a Markdown file describing the proposed `docs/` tree with one section per page (page name + one-sentence purpose + suggested section structure for that page).
  4. **Validate**: Inspection check against PRD F1 ACs (every PRD-required minimum page is in every skeleton).
  5. **Success**:
     - [ ] Four skeletons cover Obsidian, Python, TCS plugin, generic `[ref: PRD/F1 AC1-AC4]`
     - [ ] Each includes a `docs/README.md` index `[ref: PRD/Should-Have plan mode index README]`

- [ ] **T4.2 modes/plan.md — Repo Detection, Skeleton Proposal, Diff** `[activity: build-feature]` `[parallel: true]`

  1. **Prime**: Read SDD §Acceptance Criteria — Plan mode + PRD F1.
  2. **Test**: Pressure scenarios:
     - Obsidian repo (manifest.json): mode detects, picks `skeleton-obsidian.md`, proposes the tree, asks confirmation before writing.
     - Python repo (pyproject.toml only): picks `skeleton-python.md`.
     - TCS plugin (plugin.json): picks `skeleton-tcs-plugin.md`.
     - Unknown manifest: mode AskUserQuestion for repo type before proposing.
     - Existing `docs/` present: mode shows the diff (per-page Keep / Replace / Merge) and respects the author's choices.
     - Approval to write: only empty placeholders with TODO headers are created — no fabricated content (verify by reading the resulting files).
  3. **Implement**: Author `modes/plan.md` per SDD. Detection uses Glob. Proposal renders the chosen skeleton template. Diff via `git diff --no-index` or directory comparison. Writing uses the Write tool with placeholder bodies.
  4. **Validate**: All pressure scenarios pass.
  5. **Success**:
     - [ ] All 6 PRD F1 acceptance criteria pass `[ref: PRD/F1 ACs]`
     - [ ] No fabricated content; placeholders only `[ref: SDD/Acceptance Criteria — plan mode last]`

- [ ] **T4.3 modes/write.md — Section-by-Section Drafting Workflow** `[activity: build-feature]` `[parallel: true]`

  1. **Prime**: Read SDD §Acceptance Criteria — Write mode + PRD F2 + reference Anthropic's `doc-coauthoring` skill (the inspiration for this workflow shape).
  2. **Test**: Pressure scenarios:
     - Author invokes `/doc-product write installation` on an empty placeholder: mode proposes a section structure (Prerequisites → Install → Verify) and asks confirmation.
     - Confirmed structure: mode drafts section 1, asks targeted questions where source-of-truth is missing rather than fabricating.
     - Author iterates on section 1: prior approved sections are preserved.
     - Author iterates 3+ times on the same section without substantive change: mode asks "can anything be removed?" before continuing (per PRD F2 AC4).
     - Author tries to use `write` on a non-existent page: mode either creates the placeholder first (via plan-mode logic) or refuses with a clear error.
  3. **Implement**: Author `modes/write.md` per SDD + Anthropic doc-coauthoring's discover→document→review pattern, adapted for user-facing docs. The mode body is Markdown instructions to Claude that orchestrate the conversation; section structures per page type live in `reference/conventions.md` (a small lookup table).
  4. **Validate**: All pressure scenarios pass.
  5. **Success**:
     - [ ] All 4 PRD F2 acceptance criteria pass `[ref: PRD/F2 ACs]`
     - [ ] Iterative structure preserves prior sections `[ref: SDD/Acceptance Criteria — write mode]`

- [ ] **T4.4 reference/conventions.md — Page Type → Section Structure Map** `[activity: template-design]`

  1. **Prime**: Inspect what `miyo-kado/docs/installation.md`, `miyo-kado/docs/configuration.md`, `miyo-kado/docs/troubleshooting.md` contain — those are the reference good states.
  2. **Test**: For each of the 4 minimum page types (installation, configuration, usage, troubleshooting), the conventions document specifies a section structure that, when followed, would let a first-time-installer / config-explorer / troubleshooter persona answer their required questions. Tested indirectly via Phase 5 dogfood reader-test passes.
  3. **Implement**: Author `reference/conventions.md`. Per page type: a recommended section list, a one-sentence purpose for each section, and a "must include" checklist (e.g. installation must include "How do I verify it works?").
  4. **Validate**: Inspection cross-referenced with Phase 5 dogfood outcomes.
  5. **Success**:
     - [ ] Page type → section map covers all 4 minimum page types
     - [ ] Used by `modes/write.md` to drive section proposals

- [ ] **T4.5 Phase 4 Validation** `[activity: validate]`

  - Run `/skill-author audit`.
  - Run plan against three repo types (Obsidian, Python, TCS plugin) using fixture or real targets.
  - Run write on at least one page through full iterate cycle.
  - Verify against SDD §Acceptance Criteria — Plan mode (6 EARS) and Write mode (4 EARS).
  - If any deviation from SDD, log in Deviations.

---

## Deviations

(None yet.)
