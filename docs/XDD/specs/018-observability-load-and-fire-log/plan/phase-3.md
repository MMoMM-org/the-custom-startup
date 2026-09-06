---
title: "Phase 3: Report, self-check and end-to-end validation"
status: pending
version: "1.0"
phase: 3
---

# Phase 3: Report, self-check and end-to-end validation

## Phase Context

**GATE**: Read all referenced files before starting this phase.

**Specification References**:
- `[ref: PRD/F4]` — the report that answers the question
- `[ref: PRD/F8]` — usage against the inventory
- `[ref: SDD/Integration Points]` — ingesting the harness's own hook records, and the `batch` label
- `[ref: SDD/Architecture Decisions — ADR-6]` — Python, pytest-covered, offline
- `[ref: SDD/Quality Requirements]` — the honesty requirement

**Key Decisions**:
- The report is offline, so the hook-path budget does not apply. Clarity and test coverage win over
  cleverness here `[ref: SDD/Solution Strategy]`.
- **Superseded 2026-09-06 (T1.4 finding, see README and ADR-7):** the bullet below described ingesting
  a **batch** figure from the harness's own telemetry. That route is dropped — it would require a
  locally running OTLP receiver, which collides with CON-6 and the Won't-Have "no server component".
  ~~A hook duration ingested from the harness is a batch figure and must be labelled as such. The
  report may never present it as per-hook attribution — that is the misreading the whole ADR-7
  question exists to prevent.~~ Hook durations now come only from `timed-wrapper.sh`, always
  `scope_note: single`; see `solution.md`'s Integration Points. **T3.4 below is written around the
  dropped route and needs the maintainer's decision on how to change it — not rewritten here.**
- An empty record is a statement about recording, not about loading.

**Dependencies**: Phase 2 (records must exist to report on). T1.4 has run (see `plan/phase-1.md`):
configuration-only attribution is impossible, so T3.5 is not skipped — it builds the wrapper as
designed. T3.4's dependence on the harness-ingest route is now the open question in this phase.

---

## Tasks

Turns the record into the answers #147 needs, and proves the whole path end to end.

- [ ] **T3.1 Load report — what loaded, how often, and what never did** `[activity: backend-api]`

  1. Prime: read the record schema and PRD Feature 4 `[ref: SDD/Application Data Models]`
  2. Test: over a fixture log, lists each instruction file with its load count and the reasons
     observed; names configured instruction files that never appear, enumerated from the instruction
     inventory `[ref: SDD/The two inventories]`; distinguishes always-loaded
     from conditionally loaded entries; handles a rotated chain (`.jsonl` plus `.1`–`.3`) as one
     logical record without double-counting
  3. Implement: `scripts/observability/report.py`
  4. Validate: `pytest -q` green; the module is importable and unit-testable without a live session
  5. Success: `[ref: SDD/SDD-AC-13]`; `[ref: PRD/F4]`

- [ ] **T3.2 Byte accounting and the honesty rule** `[activity: backend-api]`

  1. Prime: read the honesty requirement `[ref: SDD/Quality Requirements]`
  2. Test: reports the measured byte cost of the always-loaded layer separately from conditional
     loads; **given an empty record, reports the recording state rather than "nothing loaded"**;
     given a record whose newest entry is older than the current session, says so
  3. Implement: extend `report.py`; read the `kind: state` record written by `selfcheck`
  4. Validate: `pytest -q` green, including the empty-input and stale-input cases
  5. Success: `[ref: SDD/SDD-AC-14, SDD-AC-15]`; `[ref: PRD/F4]`

- [ ] **T3.3 Inventory join — what never fired** `[activity: backend-api]`

  1. Prime: read PRD F8, the note that a hook supplies only the numerator, and the two inventory
     definitions `[ref: PRD/F8]` `[ref: SDD/The two inventories]`
  2. Test: given the shipped skill and agent inventory and a record, reports coverage as a fraction
     and names the entries that never fired; a skill present in the inventory but absent from the
     record appears as **unused**, not as missing
  3. Implement: extend `report.py` with the inventory scan
  4. Validate: `pytest -q` green
  5. Success: `[ref: SDD/SDD-AC-18]`; `[ref: PRD/F8]`

- [ ] **T3.4 Ingest harness hook durations** `[activity: integration]`

  > **Flagged 2026-09-06, not rewritten here.** This task's entire premise — ingesting the harness's
  > own `hook_execution_complete` output from a redirected diagnostic run — is the route T1.4 found
  > requires a locally running OTLP receiver, and that route has been dropped (see `README.md`'s T1.4
  > section, `solution.md`'s Integration Points, and the superseded Key Decision above). F6 now gets
  > its durations from `timed-wrapper.sh` (T3.5) instead. This task as written should not be
  > implemented; it needs the maintainer's decision on whether to repurpose it (e.g. as the wrapper's
  > `report.py` ingest path) or drop it and fold its acceptance criteria into T3.5.

  1. Prime: read the integration point and the batch caveat `[ref: SDD/Integration Points]`
  2. Test: given captured `hook_execution_complete` output, produces `kind: hook` records carrying
     `scope_note: batch`; the report labels every such figure as covering a batch; a batch with
     `num_hooks > 1` is never rendered as a single hook's duration
  3. Implement: the ingest path in `report.py`, plus the documented recipe for the diagnostic run
     (enable variables, redirection to a file, and an explicit statement of what is and is not sent,
     and to whom) `[ref: PRD/F6]`
  4. Validate: `pytest -q` green
  5. Success: `[ref: SDD/SDD-AC-17]`; `[ref: PRD/F6]`

- [ ] **T3.5 Per-hook attribution — scope decided by T1.4** `[activity: infrastructure]`

  1. Prime: read T1.4's recorded finding and the updated ADR-7
  2. Test: **only if T1.4 found configuration insufficient** — a wrapped hook's exit status, stdout
     and stderr are byte-identical to the unwrapped hook's, including the exit-2 blocking case; the
     wrapper adds under 1 ms; timing is absent from the record when the wrapper is not installed
  3. Implement: `.claude/observability/timed-wrapper.sh`, built around the three protocol
     constraints — the benchmarked candidate from the research pass discards stdout and stderr and
     loses the exit code, so it is a cost measurement, **not** a template
  4. Validate: bats green; install, reproduce, read, uninstall — and confirm nothing remains in the
     hook path afterwards
  5. Success: `[ref: SDD/SDD-AC-20]`; `[ref: PRD/F7]`
  6. **Skip condition**: if T1.4 found that per-command matchers do produce separate measurement
     groups, this task is replaced by a configuration change and a note in the SDD. Record which
     path was taken.

- [ ] **T3.6 End-to-end validation and the privacy gate** `[activity: validate]`

  1. Run the full suites: `pytest -q` and `bats tests/bats/`, plus the `tcs-git-helpers` bats suite.
  2. Work a normal session with recording enabled, then run the report and check that it answers the
     four questions in PRD Feature 4 against real data rather than fixtures.
  3. **Privacy gate**: scan a record produced by a real session against the deny-list — no file
     contents, no Bash arguments, no hook command strings, no `transcript_path`, no absolute home
     paths `[ref: SDD/Quality Requirements — Privacy]` `[ref: PRD/F3]`.
  4. **Overhead gate**: measure per-hook overhead on macOS and confirm the CON-7 budget holds. The
     research figures came from a Linux container and were explicitly flagged as non-transferable.
  5. Success: every SDD acceptance criterion has passing evidence, and #147 can be answered from the
     report `[ref: PRD/Success Metrics]`.
