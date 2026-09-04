---
title: "Phase 3: Implementation split and dispatch"
status: completed
version: "1.0"
phase: 3
---

# Phase 3: Implementation split and dispatch

## Phase Context

**GATE**: Read all referenced files before starting this phase.

**Specification References**:
- `[ref: SDD/Architecture Decisions; ADR-5]` — `implement` keeps its name; its body **moves verbatim**
- `[ref: SDD/Architecture Decisions; ADR-2]` — the Direct tier's gate set, and what it drops
- `[ref: SDD/Architecture Decisions; ADR-4]` — detect from artifacts, cross-check the record
- `[ref: SDD/Implementation Examples; Example: Dispatcher detection]` — the detection table, verbatim
- `[ref: SDD/Directory Map]` — where each file lands, including the `reference/` and `examples/` moves
- `[ref: SDD/Implementation Gotchas]` — the five things that break this phase silently

**Key Decisions**:
- **ADR-5** — moving, not rewriting. The 296-line phase loop must arrive in `implement-incremental` unchanged, so today's behaviour is preserved by construction rather than by review.
- **ADR-2** — Direct keeps `tdd-guardian`, the approval gate, and the drift and constitution checks. It drops only the per-task `spec-compliance-reviewer` → `code-quality-reviewer` chain.
- **ADR-3** — do not build factory machinery. An unrecognised decomposition artifact stops the dispatcher; it does not get a route.

**Dependencies**:
- Phase 1 complete — the dispatcher's cross-check reads `decomposition_tier`, and T1.4 must have proven all 16 existing specs report it cleanly.
- Independent of Phase 2; disjoint files, may run concurrently.

---

## Tasks

Splits the implementation half into a dispatcher and two tier loops, and proves the split changes nothing for existing specs.

- [x] **T3.1 Dispatch detection, executable against every existing spec** `[activity: domain-modeling]`

  1. Prime: Read the detection table and its cross-check `[ref: SDD/Implementation Examples; Example: Dispatcher detection]` and the backwards-compatibility constraint `[ref: SDD/Constraints; CON-5]`.
  2. Test: Write `tests/test_dispatch_detection.py` encoding the detection table as a pure function over a spec directory's contents. Assert, **over all 16 real directories under `docs/XDD/specs/`**, that every spec carrying `plan/README.md` routes to `implement-incremental` and none errors — this is the regression guard for CON-5 and must fail before the function exists. Then the synthetic cases: no plan but requirements present → `implement-direct`; legacy `implementation-plan.md` → `implement-incremental`; a `manifest.md` or `units/` present → **Stop**, not a route; nothing at all → error naming `/xdd` as the remedy; recorded tier disagreeing with detected artifacts → report-before-dispatch; recorded tier absent → proceed silently.
  3. Implement: Write the detection rules into the new `implement/SKILL.md` (T3.4) as the single source the test mirrors. Keep the test and the skill text in lockstep.
  4. Validate: `.venv/bin/python -m pytest tests/test_dispatch_detection.py -q` passes, including the sweep over all 16 specs.
  5. Success:
     - [x] Every existing spec with a plan routes to the incremental loop `[ref: SDD/Quality Requirements; Reliability]`
     - [x] An unrecognised decomposition artifact stops rather than guessing `[ref: PRD/AC Feature 4.3]`
     - [x] A recorded-vs-detected mismatch reports before any work is dispatched `[ref: PRD/AC Error Handling 1]`
     - [x] An absent tier proceeds silently `[ref: PRD/AC Feature 3.3]`

- [x] **T3.2 `implement-incremental` carries today's loop, unchanged** `[activity: docs]` `[parallel: true]`

  1. Prime: Read `plugins/tcs-workflow/skills/implement/SKILL.md` in full — all 296 lines, steps 1 through 7 including 4a–4h — and the move instruction `[ref: SDD/Architecture Decisions; ADR-5]`.
  2. Test: Assert the moved file is byte-identical to the original **below the frontmatter and Persona announcement** — a diff of the Workflow sections must be empty. Assert frontmatter carries `user-invocable: false` and that the announcement reads `**Active skill: tcs-workflow:implement-incremental**` `[ref: SDD/Implementation Gotchas]`. Assert the phase-checklist parsing line `- [ ] [Phase N: Title](phase-N.md)` survives verbatim.
  3. Implement: Create `plugins/tcs-workflow/skills/implement-incremental/` and move `SKILL.md`, `reference/output-format.md`, `reference/perspectives.md`, `examples/output-example.md` into it `[ref: SDD/Directory Map]`. Change only the frontmatter `name`, add `user-invocable: false`, and update the active-skill line. Nothing else.
  4. Validate: `git diff --stat` shows a move plus a handful of changed lines, not a rewrite. Run the `tcs-helper:skill-author` audit `[ref: SDD/Constraints; CON-7]`.
  5. Success:
     - [x] The phase loop's Workflow text is unchanged `[ref: SDD/ADR-5]`
     - [x] The skill is hidden from the `/` menu `[ref: PRD/Won't Have]`
     - [x] The checklist format the loop parses is intact `[ref: SDD/Implementation Boundaries]`

- [x] **T3.3 `implement-direct` — the phase-less loop** `[activity: docs]` `[parallel: true]`

  1. Prime: Read the Direct gate set `[ref: SDD/Architecture Decisions; ADR-2]`, the escalation rule `[ref: SDD/Error Handling]`, and the `DeliveryUnit` model `[ref: SDD/Application Data Models]`.
  2. Test: Structural assertions — the skill dispatches `tdd-guardian` before every implementer; it has an explicit approval point before delegating; it invokes `validate` in drift mode and in constitution mode; it calls `xdd-meta finalize` on completion; it **never** references `spec-compliance-reviewer` or `code-quality-reviewer`; it never writes `plan/`, `manifest.md` or `units/`; it stops and recommends re-specifying when decomposition exceeds three delivery units. Frontmatter is `user-invocable: false` with the correct announcement.
  3. Implement: Write `plugins/tcs-workflow/skills/implement-direct/SKILL.md` (PICS + Workflow) and `reference/output-format.md`. Workflow: Initialize → Decompose into 1–3 delivery units → approval → per-unit gate and delegate → validate → finalize.
  4. Validate: Run the `tcs-helper:skill-author` audit. Confirm the absence assertions by grep, not by reading.
  5. Success:
     - [x] `tdd-guardian` runs before every implementer `[ref: PRD/AC Feature 5.1]`
     - [x] An explicit approval point exists before work is dispatched `[ref: PRD/AC Feature 5.2]`
     - [x] The drift check runs on completion `[ref: PRD/AC Feature 5.3]`
     - [x] The constitution check runs where a CONSTITUTION.md exists, and an L1/L2 violation blocks completion `[ref: PRD/AC Feature 5.4]`
     - [x] Neither reviewer agent is dispatched `[ref: PRD/AC Feature 5.5]`
     - [x] Exceeding three delivery units recommends escalation `[ref: PRD/AC Edge Case 1]`
     - [x] `finalize` is called, so Direct specs do not rot on `Ready` `[ref: SDD/Implementation Gotchas]`

- [x] **T3.4 `implement` becomes the dispatcher** `[activity: docs]`

  1. Prime: Read the dispatch contract `[ref: SDD/Internal API Changes; Contract: Dispatch]` and the size bar — under 100 lines, or logic has leaked out of a sub-skill `[ref: SDD/Quality Requirements; Maintainability]`.
  2. Test: Assert the rewritten skill resolves the spec via `xdd-meta`, applies the T3.1 detection table, prints a one-line dispatch summary naming the route and the artifact that triggered it, passes `$ARGUMENTS` through unchanged, and invokes exactly one sub-skill. Assert it contains **no** implementation orchestration — no phase loop, no task dispatch, no reviewer chain. Assert `user-invocable: true` and the name `implement` are retained.
  3. Implement: Rewrite `plugins/tcs-workflow/skills/implement/SKILL.md` as the dispatcher.
  4. Validate: Line count under 100. Run the `tcs-helper:skill-author` audit. Re-run `tests/test_dispatch_detection.py` against the skill's stated rules.
  5. Success:
     - [x] No plan present routes to `implement-direct` `[ref: PRD/AC Feature 4.1]`
     - [x] `plan/README.md` present routes to `implement-incremental` `[ref: PRD/AC Feature 4.2]`
     - [x] The selected route and its trigger are displayed `[ref: PRD/AC Feature 4.4]`
     - [x] `$ARGUMENTS` reaches the sub-skill unchanged `[ref: PRD/AC Feature 4.5]`
     - [x] The user-facing entry-point name is unchanged `[ref: SDD/Implementation Boundaries]`

- [x] **T3.5 Phase Validation** `[activity: validate]`

  - Run `.venv/bin/python -m pytest tests/ -q` — all green.
  - Re-run the 16-spec sweep from T3.1 and confirm every route is `implement-incremental`.
  - Grep the three new/rewritten skills for the gate assertions rather than trusting a read: `tdd-guardian` present in both loops; the two reviewers present only in `implement-incremental`; `user-invocable: false` on both sub-skills.
  - Verify against SDD `Runtime View` and PRD Features 4 and 5.
