---
title: "Phase 3: Registration and install"
status: completed
version: "1.0"
phase: 3
---

# Phase 3: Registration and install

## Phase Context

**GATE**: Read all referenced files before starting this phase.

**Specification References**:
- `[ref: SDD/Interface Specifications/Internal API Changes]` — the two settings entries
- `[ref: SDD/Architecture Decisions; ADR-1, ADR-4, ADR-5]`
- `[ref: SDD/Deployment View/Multi-Component Coordination]` — order, rollback
- `[ref: SDD/Risks and Technical Debt/Implementation Gotchas]` — h1 pins, cross-file subset assertion
- `plugins/tcs-helper/skills/observability-setup/lib/{registration.py,detect.sh,setup.sh,bundle_install.sh}`

**Key Decisions**:
- ADR-1: `REGISTRATION['PreToolUse'] = ('Skill|Agent|Bash', 'log_tool.sh')`; add `'UserPromptExpansion': ('', 'log_expansion.sh')`; `log_skill.sh` stays in the bundle.
- ADR-5: `OURS-INCOMPLETE|<event> (missing|outdated), …`, exit 4; `setup.sh` accepts it as ours. OURS is still decided before the CONFLICT scan.
- ADR-4: setup tightens existing record dirs to 0700 and `events.jsonl*` to 0600.

**Dependencies**: Phase 2 (the new scripts must exist for the bundle to install them).

---

## Tasks

Makes the new recording installable and makes a repository's own registration, not the global bundle, decide whether it is current.

- [x] **T3.1 Registration, detection and status** `[activity: backend]`

  1. Prime: `registration.py` REGISTRATION (:101-105), `add_registration` (:294-319), LEGACY_SCRIPTS (:406-410); `detect.sh` OUR_EVENTS (:222), LEGACY_SCRIPTS (:236), classification and OURS/drift (:439-488); `setup.sh` label list (:601), `IS_OURS` (:617-618), `_REGISTERED_EVENTS` (:719) `[ref: SDD/ADR-1, ADR-5]`
  2. Test: an h1 registration (`Skill`/`log_skill.sh`) is updated in place to `Skill|Agent|Bash`/`log_tool.sh`, `UserPromptExpansion` added, the other two untouched; a second run changes nothing and leaves one entry of ours per event; foreign entries survive both runs; with the bundle marker current, an h1 registration reports `OURS-INCOMPLETE` naming `PreToolUse (outdated)` and `UserPromptExpansion (missing)`, exit 4; `setup status` shows it as ours and outdated, never "not configured"; a foreign `UserPromptExpansion` hook in a CLEAN repo is a CONFLICT; in an OURS repo it is named in the OURS-INCOMPLETE message; `remove` deletes every entry of ours across all events and keeps records; cross-file tests: `OUR_EVENTS == set(REGISTRATION)`, the new EXPECTED copy equals REGISTRATION, `set(LEGACY_SCRIPTS) ⊆ set(REGISTRATION)`
  3. Implement: REGISTRATION change; `detect.sh` OUR_EVENTS, EXPECTED, OURS-INCOMPLETE; `setup.sh` label parsing, status text, `_REGISTERED_EVENTS`; add an OURS-INCOMPLETE row (exit 4, proceed) to the state tables in the headers of `detect.sh` (:19-29) and `setup.sh` (:47-57); extend `_detect_constant` in `test_observability_cross_file_agreement.py` if it cannot parse a dict of tuples for EXPECTED; update `tests/tcs-helper/test_observability_registration.py`, `test_observability_cross_file_agreement.py`, `observability-registration-matrix.bats`, `observability-detect.bats`, `observability-setup.bats`, settings fixtures (`plugins/tcs-helper/tests/fixtures/observability-settings/build.sh`: matcher at :145, :201, :352)
  4. Validate: pytest and observability bats green; mutate `setup.sh`'s label list (drop OURS-INCOMPLETE) and the status test fails
  5. Success: `[ref: PRD/F5 AC1, AC2, AC3, AC4, AC5]`; `[ref: SDD/Acceptance Criteria/F5]`

- [x] **T3.2 Bundle h2, install list and mode tightening** `[activity: backend]`

  1. Prime: `bundle_install.sh` `_BUNDLE_INSTALL_SCRIPTS` (:118); marker `plugins/tcs-helper/templates/observability/tcs-helper-observability-version`; CI gate row in `check-hook-bundle-version.sh`; h1 pins listed in research.md § Technical/Tests `[ref: SDD/ADR-4]` `[ref: SDD/Deployment View]`
  2. Test: install copies `log_tool.sh`, `git_ops.sh`, `log_expansion.sh` and still `log_skill.sh`; the marker reads `h2` and every former `h1` pin is updated — `observability-bundle-version.bats` (:82, :120, :126), `observability-bundle-install.bats` (:35, and the exact script list at :83 and :144), `observability-drift-check.bats`, `observability-set-u-safety.bats`, `plugins/tcs-helper/tests/fixtures/observability-settings/build.sh:92`; `setup install` on a repo with a 0644 `events.jsonl` and 0755 dirs leaves 0600/0700; a file not owned by the user produces a warning, not an abort; an h1 registration keeps recording against the h2 bundle (old `log_skill.sh` path) until setup re-runs
  3. Implement: install list, marker bump, mode tightening in `setup.sh install` for the target repo's resolved data dir (same resolution as `logwrite.sh` `_observability_data_dir`)
  4. Validate: observability bats and pytest green; the hook-bundle-version gate passes on the branch; shellcheck clean
  5. Success: `[ref: PRD/F6 AC2]`; `[ref: PRD/F5 AC1]` end to end; `[ref: SDD/Acceptance Criteria/F5, F6]`

- [x] **T3.3 Phase Validation** `[activity: validate]`

  - Full pytest and observability bats; hook-bundle-version gate; run `setup status` against a scratch repo registered with the h1 shape and confirm OURS-INCOMPLETE, then `install`, then OURS-CURRENT.
