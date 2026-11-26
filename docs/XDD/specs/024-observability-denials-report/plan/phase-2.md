---
title: "Phase 2: Aggregation, overrides and rendering"
status: pending
version: "1.0"
phase: 2
---

# Phase 2: Aggregation, overrides and rendering

## Phase Context

**GATE**: Read all referenced files before starting this phase.

**Specification References**:
- `[ref: SDD/Application Data Models; lines: 310-335]` `DenialsSummary`, `TopRow`, `OverrideCounts`
- `[ref: SDD/Complex Logic; lines: 475-485]` week rows
- `[ref: SDD/User Interface & UX; lines: 510-539]` section layout, empty and not-enabled lines
- `[ref: SDD/ADR-6, ADR-7; lines: 549-590]`

**Key Decisions**:
- ADR-6: override counts from `overrides.jsonl`, `ts` and `env_var` only; master separately; ask-guard rows excluded.
- ADR-7: default 28 days ending now; `--denials-weeks N` / `--denials-since D`; Monday weeks, UTC.
- CON-2/CON-3: render sees only `DenialsSummary`; no pooled totals.

**Dependencies**:
- Phase 1 (T1.2 `classify`, T1.3 `ScanResult`).

---

## Tasks

Turns classified denials of one repository into the counts, weekly rows, top list and override figures the section shows, and renders them, including every empty and partial state.

- [ ] **T2.1 Override counts** `[activity: backend-io]` `[parallel: true]`

  1. Prime: overrides.jsonl fields and path `[ref: SDD/ADR-6]` `[ref: research.md/Constraints]`
  2. Test: rows with `CLAUDE_ALLOW_<RULE>` in period counted per rule; `CLAUDE_ALLOW_GIT_BAD_OPS` counted as master; rows outside the period, ask-guard rows and malformed rows ignored; missing file → "no override log" state; two homes that are one directory are read once (caller passes distinct homes); the `command` field is never read into the result
  3. Implement: `OverrideCounts`, `read_overrides(repo_root, homes, period)`
  4. Validate: `pytest -q tests/test_observability_denials.py -k overrides`
  5. Success: listed rules can show override counts `[ref: PRD/F4 AC2]`; no `command` value reachable `[ref: PRD/F6 AC2]`

- [ ] **T2.2 Period and aggregation** `[activity: domain-modeling]`

  1. Prime: data models, week algorithm, walkthrough steps 4–7 `[ref: SDD/Application Data Models]` `[ref: SDD/Complex Logic]`
  2. Test: `period_from_args` default 28 days, N weeks from Monday, since-date, invalid values and both options raise `ValueError`; `aggregate` keeps lines whose cwd (casefolded, worktree suffix stripped) is the repo or under it and drops a sibling repo matched by prefix; counts per category and per (hook, rule) split main/subagent; a multi-rule deny counts once in its category and once per rule; one week row per Monday week including zero weeks, partial first and last weeks flagged; top list of at most 10 by count, ties by last time, with last session id and time; unattributed and hook-deny totals; versions outside 2.1.71–2.1.332 collected
  3. Implement: `Period`, `period_from_args`, `TopRow`, `DenialsSummary`, `aggregate`
  4. Validate: `pytest -q tests/test_observability_denials.py -k "period or aggregate"`
  5. Success: default period and week rows `[ref: PRD/F3 AC1, AC3]`; worktrees counted for their repo `[ref: PRD/F3 AC5]`; top list `[ref: PRD/F4 AC1, AC3]`; period options validated `[ref: PRD/F8]`

- [ ] **T2.3 Section rendering** `[activity: frontend-text]`

  1. Prime: section layout and empty-state wording `[ref: SDD/User Interface & UX]`; existing honesty wording in `report._render_git_operations`
  2. Test: rendered lines show period start and end, files read and oldest transcript, categories with main/subagent split, rules under their hook with override counts, classifier categories, low-confidence marks, week table, top list, not-observable line, skipped lines and unchecked versions; empty summary → no-denials line with "not proof" and the not-observable list; no files → "no transcripts found" with the searched dirs; `render_not_enabled(label)` names the `denials = true` line; sentinel test: marker strings planted in tool inputs, error texts after the rule bracket, classifier reasons after the category and override `command` fields never appear in `build_section` output
  3. Implement: `render(summary)`, `render_not_enabled(label)`, `build_section(repo_root, homes, period)` composing locate → scan → classify → overrides → aggregate → render
  4. Validate: `pytest -q tests/test_observability_denials.py`
  5. Success: empty and partial states explicit `[ref: PRD/F5]`; no transcript content `[ref: PRD/F6]`; per-category and per-rule view `[ref: PRD/F3 AC2]`

- [ ] **T2.4 Phase Validation** `[activity: validate]`

  - Run all Phase 2 tests. Check every PRD F3–F6 criterion has a passing test; `render` takes only `DenialsSummary` (CON-2).
