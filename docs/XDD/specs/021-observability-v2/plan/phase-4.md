---
title: "Phase 4: Report"
status: completed
version: "1.0"
phase: 4
---

# Phase 4: Report

## Phase Context

**GATE**: Read all referenced files before starting this phase.

**Specification References**:
- `[ref: SDD/Runtime View/Complex Logic]` — report shape (`firing_events`), dedupe, built-ins, traced session
- `[ref: SDD/Architecture Decisions; ADR-7, ADR-8]`
- `[ref: SDD/Acceptance Criteria/F4]`, `[ref: SDD/Acceptance Criteria/F1]` (AC 1.5)
- `scripts/observability/report.py`: `fired_names` (:1006), `firing_coverage` (:1074), `union_fired_names` (:1848), `build_load_report` (:1561), `build_multi_source_report`, `_render_per_source_firing_detail`
- `plugins/tcs-helper/scripts/observability/README.md:211-218` — quotable coverage wording

**Key Decisions**:
- `fired_names` keeps its signature and becomes a projection of the new `firing_events`.
- Typed records count only on an exact qualified inventory name; the bare-name fallback does not apply to `route: typed`.
- `BUILTIN_AGENT_TYPES` = `general-purpose`, `Explore`, `Plan`, `statusline-setup`, `claude-code-guide`, `fork`.
- Absence of records is reported as absence of records, never as absence of activity (018 F4 AC4).

**Dependencies**: Phase 2 (record shapes). Independent of Phase 3.

---

## Tasks

Makes the report credit every route and dispatch correctly and show git activity by caller.

- [x] **T4.1 Firings: routes, dispatches, dedupe, legacy caveat** `[activity: backend]`

  1. Prime: report shape and dedupe trace `[ref: SDD/Runtime View/Complex Logic]`; current `fired_names` and its callers
  2. Test: `firing_events` on the SDD's traced session yields exactly the table's outcomes; tool and typed records for one skill both count and the route counts render; a pre-h2 `skill` record without `route` counts as `tool`; a typed `test` (bare) is not a skill firing while a typed `tcs-issues:issue` is; a dispatch with empty `subagent_type` yields nothing; a named dispatch credits its `subagent_type` and its SubagentStart record adds nothing; an agent record with a spawn-shaped name and no dispatch is listed as uncreditable and not counted; built-ins are not called uncreditable; single- and multi-source coverage figures for a fixture equal hand-derived values; `union_fired_names` unchanged for records without new kinds (existing tests stay green)
  3. Implement: `firing_events`, `BUILTIN_AGENT_TYPES`, the projection in `fired_names`, the typed exact-match rule in `firing_coverage`, route counts and the uncreditable list in rendering, both single- and multi-source paths
  4. Validate: `pytest tests/test_observability_report.py tests/test_observability_sources.py tests/test_observability_report_t30_golden.py` green; T30 golden regenerated via `tests/fixtures/observability/t30_golden/regenerate.py` only if rendering changed, and the diff reviewed line by line
  5. Success: `[ref: PRD/F4 AC1, AC2, AC4]`; `[ref: PRD/F1 AC5]`; `[ref: PRD/F2 AC3]`; `[ref: SDD/Acceptance Criteria/F4]`

- [x] **T4.2 Git section and wording** `[activity: backend]` `[parallel: true]`

  1. Prime: `build_load_report` (:1561-1712); README coverage wording (:211-218) `[ref: SDD/Acceptance Criteria/F4]`
  2. Test: git records render grouped by session, then caller (`main` or `<caller_agent_type> <caller_agent_id>`), each with subcommand, flags and overrides; a source with none says no git activity was recorded and that this is not proof none happened; multi-source keeps the per-repo split (019 ADR-7)
  3. Implement: the section in `report.py`; update `plugins/tcs-helper/scripts/observability/README.md` (new kinds, routes, dispatch, git, the uncreditable caveat, wording, and the stale registration example at :282-309 showing matcher `Skill`/`log_skill.sh`) and `plugins/tcs-helper/skills/observability-setup/SKILL.md` (registered events, OURS-INCOMPLETE, re-run setup after the update); also from Phase 3 review: add `WARN` to SKILL.md's label list and tell the reader to relay a WARN (a record stayed readable), and note that setup restricts a `CLAUDE_OBSERVABILITY_DATA` override directory to 0700
  4. Validate: report tests green (`.github/docs-map` has no observability rule, so docs-sync proves nothing here; the README/SKILL.md changes are reviewed by hand)
  5. Success: `[ref: PRD/F4 AC3, AC5]`; `[ref: SDD/Acceptance Criteria/F4]`

- [x] **T4.3 Phase Validation** `[activity: validate]`

  - Full pytest. Manual: render a report over a fixture holding every record kind and read it as the maintainer persona would.
