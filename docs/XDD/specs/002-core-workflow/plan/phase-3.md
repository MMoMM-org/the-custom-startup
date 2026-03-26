---
title: "Phase 3: TDD Enforcement Core"
status: pending
version: "1.0"
phase: 3
---

# Phase 3: TDD Enforcement Core

## Phase Context

**GATE**: Read all referenced files before starting this phase. Phase 1 must be complete.

**Specification References**:
- `[ref: SDD/Interface Specifications/tcs-workflow:xdd-tdd; lines: 312-336]` — xdd-tdd enforcement contract
- `[ref: SDD/Interface Specifications/tdd-guardian agent; lines: 338-359]` — guardian contract (APPROVE/BLOCK)
- `[ref: SDD/Interface Specifications/tcs-workflow:verify; lines: 361-387]` — evidence contract
- `[ref: SDD/Building Block View/Directory Map; lines: 190-204]` — new skill/agent paths
- `[ref: SDD/Constraints/CON-4]` — skill-author for skills, agent-creator for agents
- `[ref: SDD/ADR-3]` — tdd-guardian lives in tcs-workflow/agents/ (self-contained)
- `[ref: PRD/Feature 2]` — tdd-guardian (dispatched by implement, dispatches per subagent)
- `[ref: PRD/Feature 3]` — xdd-tdd skill (user-facing TDD workflow)
- `[ref: PRD/Feature 4]` — verify skill (evidence gate)

**Key Decisions**:
- ADR-3: `tdd-guardian.md` lives in `plugins/tcs-workflow/agents/` — self-contained in the workflow plugin.
- CON-4: `xdd-tdd` and `verify` created via `/tcs-helper:skill-author`; `tdd-guardian` created via `/plugin-dev:agent-creator`.
- `tdd-guardian` is haiku model — lightweight, cheap enforcement only.
- YOLO=true: tdd-guardian logs violation to `docs/ai/memory/yolo-review.md` and returns APPROVE with warning flag.

**Dependencies**:
- Phase 1 complete (tcs-workflow directory exists, docs/XDD/ exists)
- Phase 2 not required (TDD enforcement is independent of skill renames)
- Phase 4 requires Phase 3 (implement enhancement depends on tdd-guardian)

---

## Tasks

Creates the three new TDD enforcement components: `xdd-tdd` (user-facing RED-GREEN-REFACTOR guide), `tdd-guardian` (lightweight enforcement agent dispatched by implement), and `verify` (evidence gate preventing false success claims). Together they close the test-discipline gap identified in the PRD.

- [ ] **T3.1 Create xdd-tdd skill** `[activity: backend-api]`

  1. Prime: Read `[ref: SDD/Interface Specifications/tcs-workflow:xdd-tdd; lines: 312-336]` for enforcement contract and steps. Read `plugins/tcs-workflow/skills/brainstorm/SKILL.md` as reference for PICS format and frontmatter pattern. `[ref: PRD/Feature 3]`
  2. Test: `plugins/tcs-workflow/skills/xdd-tdd/SKILL.md` exists. Frontmatter matches contract: `name: xdd-tdd`, `user-invocable: true`, `argument-hint` includes `--sdd-ref`. Skill body includes all 7 enforcement steps: (1) read SDD section, (2) generate test list, (3) confirm test file path, (4) wait for RED confirmation, (5) approve GREEN, (6) confirm PASS, (7) REFACTOR checkpoint. Output states: `APPROVED` or `BLOCKED`. Reference file `reference/iron-law.md` exists with RED-GREEN-REFACTOR iron law. `[ref: PRD/Feature 3/AC-3.1, AC-3.2, AC-3.3]`
  3. Implement: Invoke `/tcs-helper:skill-author` to create `plugins/tcs-workflow/skills/xdd-tdd/SKILL.md` and `plugins/tcs-workflow/skills/xdd-tdd/reference/iron-law.md`. Skill content follows the 7-step contract from SDD. Iron law reference: "No production code without a failing test. This is the law." `[ref: SDD/CON-4]`
  4. Validate: `ls plugins/tcs-workflow/skills/xdd-tdd/` — `SKILL.md` and `reference/iron-law.md` present. Frontmatter `name: xdd-tdd`. SKILL.md contains APPROVED/BLOCKED output states. YOLO mode: `[ "${YOLO:-false}" = "true" ]` check present. Skill size ≤ 25 KB (`wc -c SKILL.md`). `[ref: SDD/CON-2, CON-5]`
  5. Success: `xdd-tdd` skill created with full 7-step RED-GREEN-REFACTOR contract `[ref: PRD/Feature 3/AC-3.1]`; YOLO-aware `[ref: PRD/Feature 3/AC-3.3]`; authored via skill-author `[ref: SDD/CON-4]`; ≤ 25 KB `[ref: SDD/CON-2]`

- [ ] **T3.2 Create tdd-guardian agent** `[activity: backend-api]`

  1. Prime: Read `[ref: SDD/Interface Specifications/tdd-guardian agent; lines: 338-359]` for full contract. Read `plugins/tcs-team/agents/the-architect/design-system.md` as reference agent format. Read `plugins/tcs-workflow/.claude-plugin/plugin.json` to understand current agent registration. `[ref: PRD/Feature 2, SDD/ADR-3]`
  2. Test: `plugins/tcs-workflow/agents/tdd-guardian.md` exists. Agent frontmatter: `name: tdd-guardian`, `user-invocable: false`, model hint: haiku. Contract input fields present: `task_description`, `sdd_ref` (optional), `proposed_approach`. Output states defined: `APPROVE` (with `test_file`, `test_names`, `reason`) and `BLOCK` (with `reason`). YOLO=true branch: logs to `docs/ai/memory/yolo-review.md` as checkbox item, returns APPROVE with warning flag. `plugin.json` `agents` key includes `agents/tdd-guardian.md`. `[ref: PRD/Feature 2/AC-2.1, AC-2.2, AC-2.3]`
  3. Implement: Invoke `/plugin-dev:agent-creator` to create `plugins/tcs-workflow/agents/tdd-guardian.md`. Agent spec: haiku model, non-user-invocable, implements APPROVE/BLOCK contract from SDD. Update `plugins/tcs-workflow/.claude-plugin/plugin.json` to register the agent. `[ref: SDD/CON-4, ADR-3]`
  4. Validate: `plugins/tcs-workflow/agents/` directory exists. `tdd-guardian.md` present. `plugin.json` agents array includes `agents/tdd-guardian.md`. YOLO branch present in agent instructions. `[ref: PRD/Feature 2/AC-2.3]`
  5. Success: `tdd-guardian.md` created with APPROVE/BLOCK contract `[ref: PRD/Feature 2/AC-2.1]`; registered in plugin.json `[ref: SDD/ADR-3]`; YOLO logs to yolo-review.md `[ref: PRD/Feature 2/AC-2.3]`; created via agent-creator `[ref: SDD/CON-4]`

- [ ] **T3.3 Create verify skill** `[activity: backend-api]`

  1. Prime: Read `[ref: SDD/Interface Specifications/tcs-workflow:verify; lines: 361-387]` for evidence contract. Read `[ref: PRD/Feature 4]` for acceptance criteria. `[ref: PRD/Feature 4]`
  2. Test: `plugins/tcs-workflow/skills/verify/SKILL.md` exists. Frontmatter: `name: verify`, `user-invocable: true`, `argument-hint: "[task name or description]"`. Evidence types documented: `test_output`, `build_output`, `lint_output`, `manual_record`. Output states: evidence_summary block or BLOCKED. YOLO=true: auto-executes test/lint/build commands, writes summary to `docs/ai/memory/context.md`. `[ref: PRD/Feature 4/AC-4.1, AC-4.2, AC-4.3]`
  3. Implement: Invoke `/tcs-helper:skill-author` to create `plugins/tcs-workflow/skills/verify/SKILL.md`. Content implements: evidence collection step, BLOCKED check (evidence missing or failing), evidence_summary output format, YOLO auto-execute branch. `[ref: SDD/CON-4, CON-5]`
  4. Validate: `plugins/tcs-workflow/skills/verify/SKILL.md` exists. Frontmatter correct. Evidence type definitions present. BLOCKED path present. YOLO branch present with `docs/ai/memory/context.md` write. Size ≤ 25 KB. `[ref: SDD/CON-2, CON-5]`
  5. Success: `verify` skill gates completion on actual evidence `[ref: PRD/Feature 4/AC-4.1]`; YOLO auto-executes without prompting `[ref: PRD/Feature 4/AC-4.3]`; authored via skill-author `[ref: SDD/CON-4]`

- [ ] **T3.4 Phase 3 Validation** `[activity: validate]`

  - `ls plugins/tcs-workflow/skills/xdd-tdd/` — `SKILL.md` and `reference/iron-law.md` present.
  - `ls plugins/tcs-workflow/agents/` — `tdd-guardian.md` present.
  - `ls plugins/tcs-workflow/skills/verify/` — `SKILL.md` present.
  - Frontmatter check: `xdd-tdd` name=xdd-tdd, user-invocable=true; `tdd-guardian` user-invocable=false; `verify` name=verify, user-invocable=true.
  - `plugin.json` agents key includes `tdd-guardian.md`.
  - `wc -c plugins/tcs-workflow/skills/xdd-tdd/SKILL.md` — ≤ 25600 bytes.
  - `wc -c plugins/tcs-workflow/skills/verify/SKILL.md` — ≤ 25600 bytes.
  - YOLO pattern present in all three: `[ "${YOLO:-false}" = "true" ]`.
  - All Phase 3 PRD acceptance criteria: Feature 2 (AC-2.1–2.3), Feature 3 (AC-3.1–3.3), Feature 4 (AC-4.1–4.3) verifiably met.
