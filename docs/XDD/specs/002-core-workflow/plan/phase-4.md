---
title: "Phase 4: Core Orchestration"
status: completed
version: "1.0"
phase: 4
---

# Phase 4: Core Orchestration

## Phase Context

**GATE**: Read all referenced files before starting this phase. Phase 3 must be complete.

**Specification References**:
- `[ref: SDD/Interface Specifications/tcs-workflow:implement Enhanced Flow; lines: 468-520]` — implement enhancement steps a-h
- `[ref: SDD/Interface Specifications/tcs-workflow:guide; lines: 289-310]` — guide frontmatter and recovery algorithm
- `[ref: SDD/Interface Specifications/tcs-workflow:guide Decision Tree; lines: 437-466]` — intent → skill routing
- `[ref: SDD/Building Block View/Directory Map; lines: 190-196]` — guide/ and implement/ paths
- `[ref: SDD/Constraints/CON-4, CON-5]` — skill-author, YOLO pattern
- `[ref: SDD/ADR-4]` — guide reads live git + plan files (bash-first) + memory hint
- `[ref: PRD/Feature 7]` — guide skill (orientation + session recovery)
- `[ref: PRD/Feature 9]` — implement enhancement (tdd-guardian dispatch, fresh subagents, two-stage review)

**Key Decisions**:
- ADR-4: guide is bash-first — reads live git state with bash commands, not session memory. Memory hint from `docs/ai/memory/context.md` is supplementary only.
- Phase 4 requires Phase 3: implement dispatch of tdd-guardian depends on tdd-guardian existing.
- Phase 5 (parallel-agents, receive-review, etc.) requires Phase 4 complete (guide references those skills; implement calls parallel-agents).

---

## Tasks

Creates the `guide` skill (universal session entry/re-entry point) and enhances `implement` with fresh-subagent dispatch, tdd-guardian integration, model selection, and two-stage review. These are the two central orchestration skills that wire together all other components.

- [x] **T4.1 Create guide skill** `[activity: backend-api]`

  1. Prime: Read `[ref: SDD/Interface Specifications/tcs-workflow:guide; lines: 289-310]` for frontmatter contract and recovery algorithm. Read `[ref: SDD/Interface Specifications/tcs-workflow:guide Decision Tree; lines: 437-466]` for intent → skill routing. Read `plugins/tcs-workflow/skills/brainstorm/SKILL.md` for PICS reference format. `[ref: PRD/Feature 7, SDD/ADR-4]`
  2. Test: `plugins/tcs-workflow/skills/guide/SKILL.md` exists. Frontmatter: `name: guide`, `user-invocable: true`, `argument-hint` includes intent options. Recovery algorithm: step 1 runs `git branch --show-current`, step 2 uses `fd -t f "phase-*.md"`, step 3 uses `grep -c "^- \[ \]"`, step 4 reads `docs/ai/memory/context.md`. Decision tree covers all 8 intent cases from SDD. Every intent path ends with an explicit "next skill" announcement. YOLO=true: runs algorithm automatically without prompting for intent. `[ref: PRD/Feature 7/AC-7.1, AC-7.2, AC-7.3, AC-7.4]`
  3. Implement: Invoke `/tcs-helper:skill-author` to create `plugins/tcs-workflow/skills/guide/SKILL.md`. Content: PICS structure; Step 1 bash block (git branch, fd, grep); Step 2 context.md read; Step 3 intent resolution; Step 4 decision tree; Step 5 announcement of next skill. Bash commands use `fd`/`rg` with graceful fallback if absent. `[ref: SDD/CON-3, CON-4, ADR-4]`
  4. Validate: `guide/SKILL.md` exists. Recovery algorithm has all 5 steps. Decision tree has all 8 intent branches. Each branch ends with explicit skill announcement. `fd` and `rg` used (not `find`/`grep`). Graceful error if `fd` absent. YOLO branch present. Size ≤ 25 KB. `[ref: SDD/CON-2, CON-3]`
  5. Success: `guide` created with bash-first recovery algorithm `[ref: SDD/ADR-4]`; all 8 intent routes covered `[ref: PRD/Feature 7/AC-7.1]`; every route ends with next-skill announcement `[ref: PRD/Feature 7/AC-7.4]`; YOLO-aware `[ref: PRD/Feature 7/AC-7.3]`; authored via skill-author `[ref: SDD/CON-4]`

- [x] **T4.2 Enhance implement skill** `[activity: backend-api]`

  1. Prime: Read `plugins/tcs-workflow/skills/implement/SKILL.md` in full — understand current flow before modifying. Read `[ref: SDD/Interface Specifications/tcs-workflow:implement Enhanced Flow; lines: 468-520]` for all enhancement steps. Note steps a-h: plan read, task extract, TaskCreate, per-task validation, model selection, tdd-guardian dispatch, fresh implementer subagent, status handling, spec compliance review, code quality review. `[ref: PRD/Feature 9]`
  2. Test: Updated `implement/SKILL.md` includes: (a) task extraction using `grep "^- \[ \]"` from plan file; (b) `TaskCreate` call for all tasks upfront; (c) model selection logic (haiku/sonnet/opus criteria); (d) tdd-guardian dispatch per task (APPROVE → proceed, BLOCK → halt + prompt user); (e) fresh subagent dispatch with curated context (task text, SDD ref, scene-setting — NOT session history); (f) four status states (DONE, DONE_WITH_CONCERNS, NEEDS_CONTEXT, BLOCKED) with handling; (g) spec compliance review (sonnet) before code quality review; (h) code quality review (sonnet) after spec compliance ✅. YOLO=true: tdd-guardian violations logged to yolo-review.md, implement continues. `[ref: PRD/Feature 9/AC-9.1–9.6]`
  3. Implement: Invoke `/tcs-helper:skill-author` to update `plugins/tcs-workflow/skills/implement/SKILL.md`. Add each enhancement as a discrete section. Preserve existing flow structure — add new steps, don't replace working logic. Reference `tdd-guardian` by path `agents/tdd-guardian.md`. Scene-setting template: spec name, current phase, repo structure summary (3-5 lines, not session dump). `[ref: SDD/CON-4, CON-5]`
  4. Validate: `implement/SKILL.md` — tdd-guardian dispatch section present. Four status handlers present. Model selection criteria present. Two-stage review: spec compliance first, code quality second. Spec compliance review cannot be skipped even if DONE. YOLO branch: tdd-guardian BLOCK becomes warning flag in APPROVE. Size ≤ 25 KB (overflow to `reference/` if needed). `[ref: SDD/CON-2]`
  5. Success: `implement` dispatches tdd-guardian before every implementer `[ref: PRD/Feature 9/AC-9.2]`; fresh subagents with curated context (no session history) `[ref: PRD/Feature 9/AC-9.3]`; two-stage review in correct order `[ref: PRD/Feature 9/AC-9.4]`; YOLO logs guardian violations `[ref: PRD/Feature 9/AC-9.6]`; authored via skill-author `[ref: SDD/CON-4]`

- [x] **T4.3 Phase 4 Validation** `[activity: validate]`

  - `ls plugins/tcs-workflow/skills/guide/` — `SKILL.md` present.
  - `guide/SKILL.md`: frontmatter name=guide, user-invocable=true. Recovery algorithm steps 1-5 present. Decision tree 8 branches present. `fd` and `rg` used in bash blocks.
  - `implement/SKILL.md`: tdd-guardian dispatch block present. Model selection block present. Four status states documented. Two-stage review: spec compliance before code quality.
  - YOLO pattern `[ "${YOLO:-false}" = "true" ]` in both skills.
  - `wc -c plugins/tcs-workflow/skills/guide/SKILL.md` — ≤ 25600 bytes.
  - `wc -c plugins/tcs-workflow/skills/implement/SKILL.md` — ≤ 25600 bytes (or overflow in `reference/`).
  - All Phase 4 PRD acceptance criteria: Feature 7 (AC-7.1–7.4) and Feature 9 (AC-9.1–9.6) verifiably met.
