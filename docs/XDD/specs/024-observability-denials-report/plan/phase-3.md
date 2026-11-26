---
title: "Phase 3: Report integration, docs and validation"
status: pending
version: "1.0"
phase: 3
---

# Phase 3: Report integration, docs and validation

## Phase Context

**GATE**: Read all referenced files before starting this phase.

**Specification References**:
- `[ref: SDD/Runtime View; lines: 429-474]` primary flow and error handling
- `[ref: SDD/Implementation Boundaries; lines: 150-155]` `--events` path unchanged
- `[ref: SDD/Acceptance Criteria; lines: 598-642]`
- `[ref: PRD/F7]`

**Key Decisions**:
- ADR-1: `report.py` only calls `denials`; distinct homes via `report._home_identity` before the call.
- ADR-7: period parsed once in `main()`.
- Perf rule: the 60 s measurement on real data runs only after the owner's go; never a CI gate.

**Dependencies**:
- Phase 2 (`build_section`, `render_not_enabled`, `period_from_args`).

---

## Tasks

Wires the denials section into the per-source report and the CLI, documents it, and validates it end to end and against this machine's real transcripts.

- [ ] **T3.1 Report and CLI integration** `[activity: backend-integration]`

  1. Prime: `report._build_source_report`, `build_multi_source_report`, `main()`, `_home_identity` `[ref: SDD/Primary Flow]`
  2. Test: an enabled source's section ends with the denials lines and a disabled source's with the not-enabled lines; with two sources, each section carries only its own counts and no total appears; a disabled source's transcript dir is never opened (fixture dir that raises on read); `--denials-weeks 2` and `--denials-since 2026-11-01` change the printed period; invalid or combined options exit via argparse before any source is read; the `--events` path and the T30 golden fixture stay byte-identical; end-to-end sentinel test over `main()` output
  3. Implement: `period` parameter on `_build_source_report` and `build_multi_source_report`; denials call with distinct homes; `--denials-weeks` / `--denials-since` (mutually exclusive) in `main()`
  4. Validate: `pytest -q tests/test_observability_report.py tests/test_observability_report_t30_golden.py tests/test_observability_denials.py`
  5. Success: per-source placement, no pooled totals `[ref: PRD/F3 AC4]`; opt-in respected `[ref: PRD/F1 AC1-AC2]`; CLI period `[ref: PRD/F8]`

- [ ] **T3.2 Documentation** `[activity: docs]` `[parallel: true]` `[model: routine]`

  1. Prime: observability README "Watching several repositories at once" section and `observability-sources.toml.example` `[ref: PRD/F7]`
  2. Test: a doc test (pytest) asserts the README "Denials" part names every category from `denials.TABLE` plus "unattributed", the not-observable list, the `denials = true` line and the local-only statement; the example config carries a commented `denials = true`
  3. Implement: README "Denials" part (enable, what each category means and its confidence, not observable, privacy, period options); example config line; CHANGELOG entry (root `[Unreleased]`, tcs-helper not affected since the code lives in repo `scripts/`)
  4. Validate: `pytest -q`; docs-sync check
  5. Success: limits documented `[ref: PRD/F7 AC1-AC2]`

- [ ] **T3.3 Real-data validation** `[activity: validate]`

  1. Prime: PRD Quality KPIs `[ref: PRD/Success Metrics]` `[ref: SDD/Quality Requirements]`
  2. Test: with `denials = true` for this repository in a local, untracked config, run the report over this machine's transcripts; check unattributed share ≤ 5 % of hook denies and that the counts are consistent with research.md for the same window; ask the owner before the one timing run (perf rule) and record the result
  3. Implement: adjust table rows only if a real message family is misclassified (deviation logged in this plan)
  4. Validate: full `pytest -q`; no transcript text in the captured output (grep for a few known command strings from this session)
  5. Success: Quality KPIs met or the gap stated `[ref: PRD/Success Metrics]`

- [ ] **T3.4 Phase Validation** `[activity: validate]`

  - Run the full test suite. Walk every SDD acceptance criterion F1–F8 against a passing test. Update the spec README phase to Ready.
