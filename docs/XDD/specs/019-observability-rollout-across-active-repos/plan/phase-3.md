---
title: "Phase 3: Reading several records"
status: pending
version: "1.0"
phase: 3
---

# Phase 3: Reading several records

**Independent of phases 1 and 2.** This phase touches `scripts/observability/*.py` and `tests/*.py`
only; phases 1 and 2 touch `plugins/tcs-helper/skills/observability-setup/` and its bats suite. No
file is written by both, so the two sides can proceed concurrently.

---

## Phase Context

**GATE**: Read all referenced files before starting this phase.

**Specification References**:
- `[ref: SDD/ADR-6]` — the locations config: TOML, `repo_root` plus optional `home`
- `[ref: SDD/ADR-7]` — split by `repo`; union only coverage
- `[ref: SDD/ADR-8]` — the denominator stays one repository's shipped inventory
- `[ref: SDD/Runtime View — Complex Logic]` — how the report splits without lying
- `[ref: PRD/F3]`, `[ref: PRD/F4]`, `[ref: PRD/F5]`

**Key Decisions**:
- **The config stores `repo_root` and optional `home`, never a derived record path.** Those are
  exactly the two values `report.py` already accepts, and `_resolve_events_path` already derives
  both location shapes from them — so the config cannot drift from the resolver that consumes it.
- **`repo` is the dimension the reader is missing.** Every record carries it, frozen in the writer
  and not caller-settable; `report.py` reads it nowhere today. Adding it is what makes reading
  several records safe rather than merely possible.
- **Merging is not uniformly safe**, and this is the phase where that gets built rather than
  discussed. Recording status and the hook `installed` flag collapse to a single winner across a
  merged stream, so one live source would report the whole set as fresh and hide a source that
  stopped months ago — the exact inversion of spec-018's SDD-AC-15.

**Dependencies**: none from this spec. Depends on spec-018's `report.py` existing, which it does.

---

## Tasks

Delivers a reader that answers the cross-repository question without pretending four repositories
are one.

- [ ] **T3.1 `repo` as a first-class dimension in the existing analyses** `[activity: backend-api]`

  1. Prime: read `scripts/observability/report.py` — `instruction_stats:151`, `_redact_path:453`,
     `recording_status:412`, `hook_duration_stats:1183` `[ref: SDD/Runtime View — Complex Logic]`.
  2. Test: over a fixture holding records from two repositories, instruction statistics key on
     `(repo, path)` so a file of the same name in both is counted twice, not once — **this is the
     defect the naive merge produces, so it is the first test written**; per-repository counts sum
     to the per-file totals; a record with an empty `repo` is attributed to an "unknown" bucket
     rather than silently joining another repository's.
  3. Implement: thread `repo` through the analyses that need it. No rendering yet.
  4. Validate: `pytest -q` green; existing single-record tests unchanged and still passing.
  5. Success: `[ref: SDD/SDD-AC-19]`; `[ref: SDD/ADR-7]`

- [ ] **T3.2 The locations config and its reader** `[activity: backend-api]`

  1. Prime: read ADR-6 and `_resolve_events_path:1561-1573`, which the reader must feed rather than
     duplicate `[ref: SDD/ADR-6]` `[ref: PRD/F3]`.
  2. Test: a config with a container source (a `home` given) and a host source (none) resolves both
     record paths correctly; a source whose record does not exist yet is reported as *not yet
     recording*, distinct from a source whose path is gone entirely, which is reported as *missing*;
     an absent config file is not an error — the report falls back to single-record behaviour; a
     malformed config is an error naming the line; duplicate labels are rejected, since a label is
     how a human tells two sources apart; the config is confirmed gitignored by a test, because that
     property is a requirement rather than a convenience.
  3. Implement: `scripts/observability/sources.py`, and the example config documented in the SDD.
  4. Validate: `pytest -q` green.
  5. Success: `[ref: SDD/SDD-AC-16, SDD-AC-17, SDD-AC-18]`; `[ref: PRD/F3]`

- [ ] **T3.3 Per-source rendering, and the honesty rules** `[activity: backend-api]`

  1. Prime: re-read why merging is misleading for two specific analyses `[ref: SDD/ADR-7]`
     `[ref: SDD/Runtime View — Complex Logic]`.
  2. Test: with one source recording now and one whose newest record is months old, each source's
     recording state is reported separately and the stale one is named — **the merged form of this
     test must fail before the split is implemented**, so write it against the merged behaviour
     first and watch it report everything as fresh; the never-loaded list is a per-source difference
     against that source's own inventory walk, never against a pooled set; byte accounting is
     reported per source.
  3. Implement: per-source sections in the renderer.
  4. Validate: `pytest -q` green.
  5. Success: `[ref: SDD/SDD-AC-20]`; `[ref: SDD/ADR-7]`

- [ ] **T3.4 The one union: firing coverage across sources** `[activity: backend-api]`

  1. Prime: read `walk_skill_agent_inventory:857-922` and `fired_names:927`, and ADR-8 on why the
     denominator must not be globbed across sources `[ref: SDD/ADR-8]` `[ref: PRD/F4]`.
  2. Test: numerators union across sources while the denominator stays this repository's shipped
     inventory; a skill that fired in one source and not another appears in both the union figure
     *and* the per-source detail, because "fired somewhere" and "fired in both places it should" are
     different questions and the PRD asks the second; a target's own local agents do **not** enter
     the denominator; a record naming something outside the inventory is reported as unrecognised
     rather than dropped; hook timing's `installed` is per source, so a wrapper installed in one
     source does not present timing as available for the others.
  3. Implement: the union figure and the per-source coverage detail beside it.
  4. Validate: `pytest -q` green.
  5. Success: `[ref: SDD/SDD-AC-21, SDD-AC-22, SDD-AC-23]`; `[ref: PRD/F4]`

- [ ] **T3.5 Backwards compatibility and phase validation** `[activity: validate]`

  1. Test: `--events <path>` behaves exactly as it did in spec-018 — same output for the same input,
     asserted against a recorded fixture of the old output rather than by inspection; no argument
     reads the config; `--data-dir` still means what it meant.
  2. Validate: run `pytest -q` in full. Every spec-018 report test must still pass unmodified; if one
     needs changing, that is a deviation and is recorded rather than absorbed.
  3. **Optional scope, PRD F6 (Could-have)**: assisted discovery. If implemented, a discovered
     location is *proposed* and never added silently. The three test-fixture record directories on
     this machine are the standing argument for that rule — a discovery pass would have offered them
     as repositories, and they look entirely plausible.
  4. Success: `[ref: SDD/SDD-AC-24]`

---

## Phase Acceptance Criteria

- The report reads several records, splits every per-repository analysis by `repo`, and unions
  exactly one figure.
- Every spec-018 report test passes unmodified.
- No analysis presents a merged value where the SDD says merging is misleading.
