---
title: "Phase 1: Tier metadata foundation"
status: completed
version: "1.0"
phase: 1
---

# Phase 1: Tier metadata foundation

## Phase Context

**GATE**: Read all referenced files before starting this phase.

**Specification References**:
- `[ref: SDD/Architecture Decisions; ADR-6]` — tier recorded in three places, and why `--read` derives from the Status row rather than the log
- `[ref: SDD/Interface Specifications; Data Storage Changes]` — the exact Status row and TOML key
- `[ref: SDD/Implementation Examples; Test Examples as Interface Documentation]` — the three `spec.py` tests, near-verbatim
- `[ref: SDD/Constraints; CON-5]` — backwards compatibility with 16 pre-tier specs
- `[ref: SDD/Cross-Cutting Concepts; System-Wide Patterns]` — the fail-open rule for metadata

**Key Decisions**:
- **ADR-6** — the Status table row is the machine-readable source; the decision log is audit only. `--read` must never parse the log.
- **Fail open** — an absent, empty, or unrecognised tier reads as `""`. It is never an error, because 16 existing specs have no tier at all.

**Dependencies**:
- None. This is the foundation phase; Phases 2 and 3 both depend on it.

---

## Tasks

Establishes the tier as a first-class lifecycle field, readable by machine and by human, without breaking any spec written before it existed.

- [x] **T1.1 `spec.py` reports the decomposition tier** `[activity: backend-api]`

  1. Prime: Read `plugins/tcs-workflow/skills/xdd-meta/spec.py` — specifically the `--read` path and how it currently derives TOML keys from the README `[ref: SDD/Code Context]`. Read the fail-open rule `[ref: SDD/Cross-Cutting Concepts; System-Wide Patterns]`.
  2. Test: Write `tests/test_spec_tier.py` covering — a README with `Decomposition tier | Incremental` emits `decomposition_tier = "incremental"`; a README with `Direct` emits `"direct"`; **a README with no tier row at all emits `decomposition_tier = ""` and exits 0** (this is the CON-5 test and the one that must fail first); an unparseable value (`Bananas`) emits `""` rather than raising; a README missing entirely still behaves as it does today.
  3. Implement: Extend the `--read` path in `spec.py` to locate the Status table row and emit the key, lower-cased. Match the file's existing string-matching approach — do not introduce a Markdown parser `[ref: SDD/Technical Debt]`.
  4. Validate: `.venv/bin/python -m pytest tests/test_spec_tier.py -q` passes; the rest of `tests/` still passes.
  5. Success:
     - [x] Reading a pre-tier spec reports an absent tier rather than failing `[ref: PRD/AC Feature 3.3]`
     - [x] The emitted key name is exactly `decomposition_tier` `[ref: SDD/Data Storage Changes]`
     - [x] No existing `spec.py` behaviour changed — verified by the pre-existing tests still passing `[ref: SDD/Quality Requirements; Reliability]`

- [x] **T1.2 Spec README template carries the tier row** `[activity: docs]` `[parallel: true]`

  1. Prime: Read `plugins/tcs-workflow/skills/xdd-meta/template.md` and one real spec README (`docs/XDD/specs/016-rule-enforcer-claude-md-sweep/README.md`) to match the Status table's exact shape.
  2. Test: Assert in `tests/test_spec_tier.py` that a freshly scaffolded spec's README contains a `Decomposition tier` row in the Status table, and that its placeholder is a value `spec.py` reads back as `""` — a scaffolded spec has no tier yet, and must not appear to have one.
  3. Implement: Add the row to `template.md` in the Status table, after `Current Phase`.
  4. Validate: Scaffold a throwaway spec in a temp directory, run `--read` on it, confirm `decomposition_tier = ""`.
  5. Success:
     - [x] A new spec starts with a tier row present and empty `[ref: SDD/Data Storage Changes]`
     - [x] The row placeholder never reads back as a real tier `[ref: PRD/AC Feature 3.3]`

- [x] **T1.3 `xdd-meta` exposes tier in its interface and phase transitions** `[activity: docs]`

  1. Prime: Read `plugins/tcs-workflow/skills/xdd-meta/SKILL.md` — the `SpecStatus` interface, Workflow step 2 (Read Status) and step 3 (Transition Phase) `[ref: SDD/Code Context]`.
  2. Test: Structural assertions — `SpecStatus` declares `decomposition_tier`; step 2's continuation match accounts for a spec that has requirements and solution but is recorded Direct (so it suggests implementation, not "continue to PLAN"); step 3's phase match routes Direct to *no* skill invocation and Incremental to `xdd-plan`.
  3. Implement: Update `SpecStatus`, step 2's match, and step 3's match. Add a `Log Decision` note that a tier decision writes both the Status row and a log row `[ref: SDD/Architecture Decisions; ADR-6]`.
  4. Validate: Run the `tcs-helper:skill-author` audit on `xdd-meta`; PICS structure and size limits still pass `[ref: SDD/Constraints; CON-7]`.
  5. Success:
     - [x] The lifecycle interface carries the tier as a first-class field `[ref: PRD/AC Feature 3.1]`
     - [x] A Direct spec is never told to "continue to PLAN" `[ref: SDD/Runtime View]`
     - [x] Recording a tier writes both the Status row and a decision-log row `[ref: PRD/AC Feature 3.2]`
     - [x] A recorded tier is what explains a missing `plan/` to a later reader `[ref: PRD/AC Feature 1.5]`

- [x] **T1.4 Phase Validation** `[activity: validate]`

  - Run `.venv/bin/python -m pytest tests/ -q` — all green, including the pre-existing 198.
  - Run `--read` against **all 16 existing spec directories**; every one must exit 0 and report `decomposition_tier = ""`. This is the executable form of CON-5 and must be run before Phase 3 depends on it.
  - Verify against SDD `Data Storage Changes` and PRD Feature 3 acceptance criteria.
  - Confirm `plugin.json` was **not** touched `[ref: SDD/Constraints; CON-6]`.
