---
title: "Phase 2: Triage Skill + Hand-offs"
status: pending
version: "1.0"
phase: 2
---

# Phase 2: Triage Skill + Hand-offs

## Phase Context

**GATE**: Read all referenced files before starting this phase.

**Specification References**:
- `[ref: PRD/M2 — /enforce-rule slash command]`
- `[ref: PRD/M3 — 4-question triage logic]`
- `[ref: PRD/M4 — Mechanism matrix routing]`
- `[ref: PRD/M5 — Hand-off to existing author skills]`
- `[ref: PRD/S2 — Worked examples reference]`
- `[ref: SDD/ADR-1 Matrix in reference/ lazy-load]`
- `[ref: SDD/ADR-3 No persistence v1]`
- `[ref: SDD/Building Block View — Skill Layer]`
- `[ref: SDD/Interface Specifications — Skill Contract]`
- `[ref: SDD/Runtime View — Primary Flow]`

**Key Decisions**:
- Skill is a router, not a duplicator — hand off to existing author skills via `Skill()` tool
- Mechanism matrix loaded lazily (`Read reference/mechanism-matrix.md`) at workflow step 6 (ADR-1)
- Sequential AskUserQuestion for Q1→Q4 (PRD-decided; allows short-circuit at Q1 and Q2)
- Override choices live only in conversation context (ADR-3)
- SKILL.md ≤ 500 lines per `tcs-helper:skill-author` conventions (CON-6)

**Dependencies**: Phase 1 complete (intercept hook + trigger-phrases must exist for the skill to be triggered organically; manual `/enforce-rule` works without Phase 1 but the integration story requires it).

---

## Tasks

This phase delivers the **`/enforce-rule` triage skill** — the user-invocable entry point that walks the 4-question triage and routes to the right author skill via `Skill()` hand-offs. PRD Features M2–M5 + S2.

- [ ] **T2.1 Skill scaffold (SKILL.md + frontmatter)** `[activity: skill-authoring]` `[parallel: true]`

  1. **Prime**: Read `plugins/tcs-helper/skills/skill-author/SKILL.md` and `reference/conventions.md` — adopt PICS structure (Persona, Interface, Constraints, Workflow). Read `plugins/tcs-helper/skills/memory-add/SKILL.md` for hand-off-target convention reference.
  2. **Test (RED)**: Write a structural assertion script (bash): SKILL.md exists, has YAML frontmatter with required fields (`name: rule-enforcer`, `description: ...`, `user-invocable: true`, `argument-hint: "[rule description]"`), contains `## Persona`, `## Interface`, `## Constraints`, `## Workflow` sections.
  3. **Implement (GREEN)**:
     - Create `plugins/tcs-helper/skills/rule-enforcer/SKILL.md` skeleton (~80 lines): frontmatter + Persona + Interface (TriageState type + 4 question enums) + Constraints (Always/Never lists) + Workflow placeholders for steps 1–8 (filled out in T2.3)
     - Active-skill announcement: `**Active skill: tcs-helper:rule-enforcer**`
     - Description per CSO rules: triggering conditions only, not workflow summary
  4. **Validate**: Run structural assertion. Run `tcs-helper:skill-author` in **audit mode** against the scaffold — expect "structure OK, workflow body pending" verdict.
  5. **Success**:
     - [ ] SKILL.md passes skill-author structural audit `[ref: PRD/M2 AC-1, AC-3]`
     - [ ] Active-skill announcement present and matches `tcs-helper:rule-enforcer` `[ref: SDD/Skill Contract]`

- [ ] **T2.2 Mechanism matrix reference file** `[activity: data-architecture]` `[parallel: true]`

  1. **Prime**: Read SDD `Mechanism Matrix File Format` section. Re-read the table in PRD `Value Proposition` and `Detailed Feature Specifications/M3`.
  2. **Test (RED)**: Write a parser assertion (Python): given `reference/mechanism-matrix.md`, parser returns a dict `{(q3, q4): mechanism}` covering all 7 Q3 options × 3 Q4 options = 21 entries.
  3. **Implement (GREEN)**:
     - Create `plugins/tcs-helper/skills/rule-enforcer/reference/mechanism-matrix.md` (~80 lines): one `## Q3 = <intervention point>` section per Q3 option, each containing a `| Q4 | Mechanism |` table with 3 rows (Block, Auto-fix, Nudge)
     - 7 Q3 options (each labeled with a recognizable case so user can pick): Before tool call (e.g. block bad git ops), After tool call (e.g. nudge after editing skills/), User submits prompt (e.g. recurrence-signal injection), Session start (e.g. restore context), Local git push (e.g. block before pushing if docs missing), PR/merge (e.g. auto-bump versions on merge), In coding patterns (e.g. TDD discipline)
     - Plus 1 fallback note: Genuine judgment call → Memory rule
     - Map each (Q3, Q4) to one of: PreToolUse hook | PostToolUse hook | UserPromptSubmit hook | SessionStart/End hook | git pre-push hook (bundle-integrated per revised ADR-2) | CI workflow | Skill w/ discipline language | Memory rule
  4. **Validate**: Parser assertion passes; markdown renders correctly. Cross-check against PRD M4 AC examples — they must produce expected mechanisms.
  5. **Success**:
     - [ ] All 21 (Q3, Q4) combinations have a mechanism mapping `[ref: PRD/M4 AC-1..AC-8]`
     - [ ] PRD M4 example cases produce exactly the expected mechanism `[ref: PRD/M4 AC-1, AC-3, AC-5]`

- [ ] **T2.5 Worked examples reference file** `[activity: documentation]` `[parallel: true]`

  1. **Prime**: Re-read the 3 session violation patterns from PRD M7. Identify 2 more cases from the memory bank survey.
  2. **Test (RED)**: Bash assertion — `reference/examples.md` exists and contains at least 5 H3 sections each named like `### Example: <rule>` with the 4-question answers and final mechanism documented.
  3. **Implement (GREEN)**: Create `plugins/tcs-helper/skills/rule-enforcer/reference/examples.md` with 5 worked cases:
     - Example 1: "I keep forgetting to bump marketplace.json" → CI workflow (PR #29 case)
     - Example 2: "I keep forgetting to update CHANGELOG after shipping" → git pre-push hook (this-session case)
     - Example 3: "I keep forgetting to run skill-author after editing skills" → PostToolUse hook (existing `authoring.md` pattern)
     - Example 4: "I always use --break-system-packages on macOS" → PreToolUse hook (per `feedback_python_venv` memory)
     - Example 5: "I forget the syntax for X" → NOT a recurrence (Q1 short-circuit; demonstrates false-positive case)
     - Each example: rule description, Q1–Q4 answers with rationale, final mechanism, hand-off / scaffolding outcome
  4. **Validate**: Bash assertion passes; each example has all 4 questions answered with rationale.
  5. **Success**:
     - [ ] At least 5 worked examples documented `[ref: PRD/S2 AC-1]`
     - [ ] PRD M7 self-test cases match Example 1–3 mechanisms `[ref: PRD/M7 AC-1, AC-2, AC-3]`

- [ ] **T2.3 4-question triage workflow (Steps 1–7 in SKILL.md)** `[activity: skill-authoring]` `[parallel: false]`

  1. **Prime**: Reload T2.1 SKILL.md skeleton. Read T2.2 matrix file format. Read PRD M3 short-circuit logic carefully (Q1=1× and Q2=judgment short-circuit to Memory).
  2. **Test (RED)**: Manual scenario test plan (recorded in `examples/output-example.md`): 4 scenarios exercising different paths through the revised memory-first workflow:
     - Scenario A: Q1=`First time` → defer to `/memory-add`, exit (Q2-Q4 skipped)
     - Scenario B: Q1=`Recurring`, Q2=`No-judgment` → short-circuit to Memory with strong-language
     - Scenario C: Q1=`Recurring`, Q2=`Yes`, Q3=`PR/merge`, Q4=`Auto-fix` → CI workflow
     - Scenario D: Q1=`Recurring`, Q2=`Yes`, Q3=`Local git push`, Q4=`Block` → git pre-push hook (per revised ADR-2: bundle-integrated)
  3. **Implement (GREEN)**: Expand SKILL.md Workflow section with 7 numbered steps (per revised PRD M3 — memory-first + example-guided):
     - Step 1: Echo rule description + confirm with user
     - Step 2: Q1 AskUserQuestion `{First time — no memory yet, Recurring — memory exists but was ignored, Cross-cutting}` → if `First time`: defer to `Skill(tcs-helper:memory-add)` (skip Q2-Q4); if `Cross-cutting`: proceed regardless of frequency
     - Step 3: Q2 AskUserQuestion `{Yes, No — judgment only}` with **concrete example per option** (per PRD M3 design constraint — option description includes "like 'missing CHANGELOG detectable by grep'" vs "like 'is this code too verbose'") → if `No`: short-circuit to Memory with strong-language template
     - Step 4: Q3 AskUserQuestion {7 intervention options} with **concrete example per option** (e.g., `Local git push (e.g. block before pushing if CHANGELOG missing)` instead of bare `Local git operation`)
     - Step 5: Q4 AskUserQuestion {Block, Auto-fix, Nudge} with behavior preview per option
     - Step 6: Read reference/mechanism-matrix.md, look up (Q3, Q4), compute mechanism
     - Step 7: Present recommendation with rationale via AskUserQuestion {Accept, Override, Explain}
  4. **Validate**: Manual scenario test (4 paths) in a Claude Code session after restart — each scenario produces the expected mechanism recommendation.
  5. **Success**:
     - [ ] 4-scenario triage path test all produce expected mechanisms `[ref: PRD/M3 AC-1..AC-5]` `[ref: PRD/M4 AC-1..AC-8]`
     - [ ] Q1 and Q2 short-circuits work correctly `[ref: PRD/M3 AC-2, AC-4]`

- [ ] **T2.4 Hand-off paths (Skill invocations for skill-author / hook-development / memory-add)** `[activity: integration]` `[parallel: false]`

  1. **Prime**: Read `plugins/tcs-helper/skills/skill-author/SKILL.md` $ARGUMENTS conventions. Read `plugins/tcs-helper/skills/memory-add/SKILL.md` template hints. Check whether `plugin-dev:hook-development` is installed (note as fallback path if not).
  2. **Test (RED)**: Manual scenario test plan (3 hand-off paths):
     - Hand-off A: mechanism = "Skill with discipline-enforcing language" → invokes `Skill(tcs-helper:skill-author)` with rule description
     - Hand-off B: mechanism = "Claude * hook" → invokes `Skill(plugin-dev:hook-development)` with hook event type pre-selected (with fallback if not installed)
     - Hand-off C: mechanism = "Memory rule" → invokes `Skill(tcs-helper:memory-add)` with strong-language template hint
  3. **Implement (GREEN)**: Extend SKILL.md Workflow with Step 8: Hand-off match block. Match on mechanism:
     - Skill mechanisms → `Skill(tcs-helper:skill-author)` with $ARGUMENTS = formatted rule context
     - Hook mechanisms → `Skill(plugin-dev:hook-development)` with hook event type extracted from mechanism
     - Memory mechanism → `Skill(tcs-helper:memory-add)` with type=feedback + strong-language hint
     - CI / pre-push → defer to Phase 3 T3.1/T3.2 (placeholder match arm)
     - Hand-off failure (e.g., plugin not installed) → AskUserQuestion {Install plugin, Use Memory instead, Cancel}
  4. **Validate**: Run 3 hand-off scenarios manually; verify each invokes the right skill OR offers fallback when target skill missing.
  5. **Success**:
     - [ ] All 3 hand-off paths invoke the correct target skill `[ref: PRD/M5 AC-1, AC-2, AC-3]`
     - [ ] Missing-target-skill fallback presents user options instead of crashing `[ref: SDD/Error Handling]`

- [ ] **T2.6 Phase 2 Validation** `[activity: validate]`

  - Re-run all Phase 2 test scenarios (4 triage paths from T2.3 + 3 hand-off paths from T2.4)
  - Run `tcs-helper:skill-author` audit in full mode — verify SKILL.md size budget (≤ 500 lines), description quality (CSO compliant), no mirrored constraints
  - Verify all 5 reference files exist and are valid markdown: `trigger-phrases.md`, `mechanism-matrix.md`, `examples.md` (also Phase-1 trigger-phrases ref already created)
  - Restart Claude Code session and confirm `/enforce-rule` appears in slash menu
  - **Phase complete when**: all 5 task Success criteria checked off + this Validation step green
