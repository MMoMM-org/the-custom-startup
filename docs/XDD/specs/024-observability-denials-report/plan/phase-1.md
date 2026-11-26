---
title: "Phase 1: Reading and classifying transcripts"
status: pending
version: "1.0"
phase: 1
---

# Phase 1: Reading and classifying transcripts

## Phase Context

**GATE**: Read all referenced files before starting this phase.

**Specification References**:
- `[ref: SDD/Building Block View; lines: 223-345]` components and internal API
- `[ref: SDD/Implementation Examples; lines: 349-428]` classification table, traced walkthrough, locating transcripts
- `[ref: SDD/Implementation Gotchas; lines: 653-661]`
- `[ref: research.md]` families, field shapes, traps

**Key Decisions**:
- ADR-2: invalid `denials` value is a `ConfigSchemaError`.
- ADR-3: project dirs by encoded-repo prefix, case-insensitive; main and `*/subagents/` files.
- ADR-4/8: ordered table, first match wins; owners as listed in the SDD.
- ADR-5: `type == "user"` and `is_error: true` only; dedupe by `(file, tool_use_id)`.

**Dependencies**:
- None. T1.1 and T1.2 are independent; T1.3 uses T1.2's `classify` only through the test fixtures of later phases, not at import time.

---

## Tasks

Establishes reading Claude Code transcripts for one repository and turning error tool results into classified denials, without rendering anything.

- [ ] **T1.1 `denials` config key** `[activity: backend-config]` `[parallel: true]` `[model: routine]`

  1. Prime: `sources._parse_source_table`, `_ALLOWED_SOURCE_KEYS`, `Source` `[ref: SDD/Internal API Changes; lines: 286-309]`
  2. Test: absent key → `Source.denials is False`; `true`/`false` accepted; `"true"` (string), `1`, `"yes"` → `ConfigSchemaError` naming the source label and value; existing configs and error messages unchanged
  3. Implement: extend `_ALLOWED_SOURCE_KEYS`, `_parse_source_table`'s return, `_parse_document`, `load_sources` and `Source` with `denials: bool = False`
  4. Validate: `pytest -q tests/test_observability_sources.py tests/test_observability_report.py`
  5. Success: invalid value stops with a schema error `[ref: PRD/F1 AC3]`; absent key behaves as today `[ref: SDD/Implementation Boundaries]`

- [ ] **T1.2 Classification table** `[activity: domain-modeling]` `[parallel: true]`

  1. Prime: SDD classification table and order rationale `[ref: SDD/Implementation Examples; lines: 351-382]`
  2. Test: one case per row (TCS block-bad-git-ops with 1 and 3 rules; pre-edit-branch-check; protect-git-internals; worktree-exit-guard; tcs-patterns eslint; tcs-issues comments; both external rows; both classifier wordings with category; safety check; permission denied; worktree isolation; prompt rejected for Bash; sandbox filesystem and network with confidence); prefixed unknown → hook deny, unattributed; unprefixed unknown → `None`; prompt rejected on AskUserQuestion and ExitPlanMode → `None`; rule text after the bracket is not in the returned `Denial`; a cross-check test reads each TCS hook source file named in the SDD Code Context and asserts its message line still matches its table row
  3. Implement: `denials.py` with `Denial`, `TABLE`, `classify(text, tool)` (prefix strip, first match, rule extraction)
  4. Validate: `pytest -q tests/test_observability_denials.py -k classify`; no local imports in `denials.py`
  5. Success: every PRD F2 category classifies `[ref: PRD/F2 AC1-AC6]`; owners per ADR-8 `[ref: SDD/ADR-8]`

- [ ] **T1.3 Locating and scanning transcripts** `[activity: backend-io]`

  1. Prime: SDD locating example, walkthrough steps 1–4, gotchas `[ref: SDD/Implementation Examples; lines: 383-428]` `[ref: SDD/Error Handling; lines: 465-474]`
  2. Test: `locate_transcripts` finds main and subagent files under prefix-matching dirs, case-insensitive, across several homes, and reports searched dirs when none exist; `scan_file` keeps only `type == "user"` with `is_error: true`, drops an `api-request-blob` copy, dedupes by `tool_use_id`, ignores non-error results with denial-like text, joins list-form content, maps tool name from the assistant `tool_use` in the same file, reads `cwd`, `sessionId`, `version`, `isSidechain`/subagent location, filters by period, counts malformed and partial lines as skipped, survives an unreadable file
  3. Implement: `_encode`, `LocateResult`, `locate_transcripts`, `ErrorResult`, `ScanResult`, `scan_file` with the `'"is_error":true'` substring prefilter before `json.loads`
  4. Validate: `pytest -q tests/test_observability_denials.py`; fixtures use `tmp_path` homes only, never the real `$HOME`
  5. Success: duplicates count once and non-errors never count `[ref: PRD/F2 AC7-AC8]`; skipped lines and versions available for rendering `[ref: PRD/F5 AC2-AC3]`

- [ ] **T1.4 Phase Validation** `[activity: validate]`

  - Run all Phase 1 tests and the existing observability tests. Verify `denials.py` imports nothing local (CON-4) and that no function reads `datetime.now()` or `Path.home()` (CON-5).
