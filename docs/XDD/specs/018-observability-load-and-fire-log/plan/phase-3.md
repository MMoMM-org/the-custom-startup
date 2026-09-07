---
title: "Phase 3: Report, self-check and end-to-end validation"
status: in_progress
version: "1.0"
phase: 3
---

# Phase 3: Report, self-check and end-to-end validation

## Phase Context

**GATE**: Read all referenced files before starting this phase.

**Specification References**:
- `[ref: PRD/F4]` — the report that answers the question
- `[ref: PRD/F8]` — usage against the inventory
- `[ref: SDD/Integration Points]` — why the harness-ingest route is dropped, and what `batch`
  survives as
- `[ref: SDD/Architecture Decisions — ADR-6]` — Python, pytest-covered, offline
- `[ref: SDD/Quality Requirements]` — the honesty requirement

**Key Decisions**:
- The report is offline, so the hook-path budget does not apply. Clarity and test coverage win over
  cleverness here `[ref: SDD/Solution Strategy]`.
- **Superseded 2026-09-06 (T1.4 finding, see README and ADR-7), resolved 2026-09-07:** this bullet
  once described ingesting a **batch** figure from the harness's own telemetry. That route is
  dropped — it would require a locally running OTLP receiver, which collides with CON-6 and the
  Won't-Have "no server component". Hook durations now come only from `timed-wrapper.sh`, always
  `scope_note: single`; see `solution.md`'s Integration Points. The rule the dropped bullet carried
  still holds in its new form: **the report may never present a duration as per-hook attribution
  unless the record says `scope_note: single`** — that is the misreading the whole ADR-7 question
  exists to prevent. T3.4 has been repurposed as the report-side half of SDD-AC-17 and is no longer
  an open question.
- An empty record is a statement about recording, not about loading.
- **Added after phase 2 (T2.1, T2.2), three cases `report.py` did not previously have to handle**
  `[ref: solution.md/Application Data Models]`: (1) `reason` may be an empty string — T2.1 dropped
  a fabricated `session_start` default for a payload missing `load_reason`, so an empty `reason`
  must be counted as unknown, never folded into any named reason's count; (2) `bytes` may be
  absent — a file that could not be stat'ed is written with no `bytes` field at all, never `0`, so
  it must be excluded from a byte-cost total rather than counted as zero cost; (3) a payload with no
  usable `path` produces no `kind: instruction` record at all (T2.1's guard against a phantom entry
  inflating PRD F4's denominator) — `report.py` does not need to filter for this itself, but must
  not assume every record it reads once existed unfiltered upstream.

**Dependencies**: Phase 2 (records must exist to report on). T1.4 has run (see `plan/phase-1.md`):
configuration-only attribution is impossible, so T3.5 is not skipped — it builds the wrapper as
designed. T3.4 no longer depends on the harness-ingest route (repurposed 2026-09-07) and now
depends on T3.5 instead: the wrapper writes the `kind: hook` records the report reads, so **T3.5
runs before T3.4** even though it is numbered after it. T3.1–T3.3 all extend the same
`report.py` and are strictly sequential.

---

## Tasks

Turns the record into the answers #147 needs, and proves the whole path end to end.

- [x] **T3.1 Load report — what loaded, how often, and what never did** `[activity: backend-api]`

  1. Prime: read the record schema and PRD Feature 4 `[ref: SDD/Application Data Models]`
  2. Test: over a fixture log, lists each instruction file with its load count and the reasons
     observed; names configured instruction files that never appear, enumerated from the instruction
     inventory `[ref: SDD/The two inventories]`; distinguishes always-loaded
     from conditionally loaded entries; handles a rotated chain (`.jsonl` plus `.1`–`.3`) as one
     logical record without double-counting; **a record with an empty `reason` is counted as
     unknown, never folded into any named reason's count** (T2.1 dropped the fabricated
     `session_start` default — see this phase's Key Decisions)
  3. Implement: `scripts/observability/report.py`
  4. Validate: `pytest -q` green; the module is importable and unit-testable without a live session
  5. Success: `[ref: SDD/SDD-AC-13]`; `[ref: PRD/F4]`

- [x] **T3.2 Byte accounting and the honesty rule** `[activity: backend-api]`

  1. Prime: read the honesty requirement `[ref: SDD/Quality Requirements]`
  2. Test: reports the measured byte cost of the always-loaded layer separately from conditional
     loads; **given an empty record, reports the recording state rather than "nothing loaded"**;
     given a record whose newest entry is older than the current session, says so; **a record with
     no `bytes` field (T2.1: the file could not be stat'ed) is excluded from the byte-cost total,
     never counted as zero**, and the report states how many records had no measurable size
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

- [ ] **T3.4 Wrapper-sourced hook durations in the report** `[activity: backend-api]`

  > **Repurposed 2026-09-07**, maintainer decision (see the Decisions Log). This task previously
  > ingested the harness's own `hook_execution_complete` output. T1.4 found that route needs a
  > locally running OTLP receiver, which collides with CON-6 and the Won't-Have "no server
  > component", so it is dropped. `solution.md` has already moved on — SDD-AC-17 and the
  > `kind = hook` record shape both read against `timed-wrapper.sh` with `scope_note: single`.
  > This task is now the **report-side half** of SDD-AC-17; T3.5 remains the wrapper itself.

  **Order**: run this task *after* T3.5, so the report is written against records the wrapper
  actually produces rather than against a shape read only from the SDD.

  1. Prime: read the `kind = hook` record shape and the single-scope rule
     `[ref: SDD/Application Data Models]` `[ref: SDD/Integration Points]`
  2. Test: given `kind: hook` records written by `timed-wrapper.sh`, the report shows each duration
     against the one hook invocation that produced it, labelled `scope_note: single`; a record
     carrying `scope_note: batch` — or no `scope_note` at all — is **never** rendered as a single
     hook's duration, which is the misreading ADR-7 exists to prevent; a record with no `kind: hook`
     entries reports that hook timing is not installed, rather than reporting zero hooks
  3. Implement: the hook-duration section of `scripts/observability/report.py`
  4. Validate: `pytest -q` green
  5. Success: `[ref: SDD/SDD-AC-17]`; `[ref: PRD/F6]`

- [ ] **T3.5 Per-hook attribution — scope decided by T1.4** `[activity: infrastructure]`

  1. Prime: read T1.4's recorded finding and the updated ADR-7
  2. Test: **only if T1.4 found configuration insufficient** — a wrapped hook's exit status, stdout
     and stderr are byte-identical to the unwrapped hook's, including the exit-2 blocking case; the
     wrapper adds under 1 ms; timing is absent from the record when the wrapper is not installed
  3. Implement: `plugins/tcs-helper/scripts/observability/timed-wrapper.sh` (tracked, alongside
     `logwrite.sh` and the adapters — relocated 2026-09-06, see `solution.md`'s Directory Map and
     the README's Decisions Log; `.claude/observability/` no longer exists as a path), built around
     the three protocol
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
