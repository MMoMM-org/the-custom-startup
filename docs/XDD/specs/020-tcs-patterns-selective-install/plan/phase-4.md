---
title: "Phase 4: Drift and the advisory"
status: in_progress
version: "1.0"
phase: 4
---

# Phase 4: Drift and the advisory

## Phase Context

**GATE**: Read all referenced files before starting this phase.

**Specification References**:
- `[ref: SDD/Interface Specifications/Process contract: drift reporter]` — the stdout contract and
  why `MISSING` is reported but not surfaced
- `[ref: SDD/Interface Specifications/Process contract: the generalized drift check]` — the added
  directory parameter and the kept wrapper
- `[ref: SDD/Cross-Cutting Concepts/Pattern Documentation]` — the four parts of the spec-012
  pattern and the one deviation, which is the grain
- `[ref: SDD/Deployment View/Multi-Component Coordination]` — the one-way dependency and the
  tolerance requirement
- `[ref: PRD/F7]` — four acceptance criteria

**Key Decisions**:
- **Per-pattern grain is the deviation from spec-012 and it is forced.** A per-bundle marker would
  raise an advisory in every repository for a change to one pattern, which F7's second criterion
  forbids.
- **`MISSING` is reported by the contract and suppressed by the advisory.** F7's fourth criterion
  requires that a repository with no patterns is not nagged; only the `status` verb surfaces it.
- **`tcs-git-helpers` must tolerate `tcs-patterns` being absent or at `1.x`.** The advisory segment
  stays silent when the drift script cannot be found. The dependency runs one way, through a
  documented file format, not through code.

**Dependencies**:
- Phase 1 — the `VERSION` files are one half of every comparison.
- Phase 3 — the manifest is the other half.

---

## Tasks

Delivers the property that makes distributed copies acceptable: a stale copy is detectable, and
only where it exists.

- [x] **T4.1 The generalized drift check** `[activity: refactor]`

  1. Prime: Read both existing implementations — `plugins/tcs-git-helpers/scripts/lib/drift_check.sh`
     and its `.py` sibling — and the new contract
     `[ref: SDD/Interface Specifications/Process contract: the generalized drift check]`. The marker
     filename is already a parameter; only the `.githooks/` directory is hardcoded.
  2. Test: The existing `drift_check_hook_bundle` name and behaviour are unchanged for every
     current caller (this is a refactor and must prove itself invisible); the new
     `drift_check_bundle` accepts a directory and returns `OK` / `MISSING` / `DRIFT:<installed>`
     for each; exit status stays 0 in all cases, because the caller decides what to do. Both the
     `.sh` and the `.py` implementation are tested — they are two implementations of one contract
     and may not diverge.
  3. Implement: add the directory parameter to both, keep `drift_check_hook_bundle` as a thin
     wrapper defaulting to `.githooks`. bash 3.2, shellcheck-clean. Remember that a bare `[[ ]]`
     only fails a bats test as the body's last statement.
  4. Validate: the bats leg for `tcs-git-helpers`; `python3 -m pytest -q`; `shellcheck` on the
     changed script. The two existing bundle-table rows must behave exactly as before — three
     markers exist, but the rule-enforcer bundle is ungated (#174), so there is no third row
     to leave alone.
  5. Success:
     - [x] Existing callers unchanged in behaviour `[ref: SDD/Interface Specifications]`
     - [x] Both implementations return the same verdicts for the same inputs `[ref: SDD/Interface Specifications]`

- [x] **T4.2 The patterns drift reporter** `[activity: backend-api]`

  1. Prime: Read the stdout contract
     `[ref: SDD/Interface Specifications/Process contract: drift reporter]`. One line per drifted
     pattern, carrying the pattern, the installed version and the catalogue version.
  2. Test: Every installed pattern current → `OK`; two behind → exactly two `DRIFT:` lines naming
     both versions each; no manifest → `MISSING`; a catalogue pattern changed that this manifest
     does not list → **nothing** said about it (F7's second criterion); a pattern whose catalogue
     `VERSION` is absent or non-numeric → reported as unknown rather than drifted; exit 0 in every
     case.
  2b. **Compute drift from the per-pattern `version` lines only — never from the manifest's
     top-level `bundle`.** Carried from Phase 3, measured 2026-10-06:
     `[ref: SDD/Interface Specifications/Data model: the update path (C5's second verb),
     decision 9]` settles that `bundle` records the plugin version that last **wrote** to the
     manifest, not the version every pattern came from. Refreshing one pattern advances it while
     other patterns keep older content — measured as `bundle = "2.0.0"` with a second pattern still
     at its version `1`. So a reporter keying on `bundle` would answer `OK` for a repository that is
     a version behind on a pattern it installed, which is the exact failure F7 exists to prevent.
     **Add a test for it**: two patterns installed, only one refreshed, then assert the reporter
     emits a `DRIFT:` line for the stale one rather than `OK`.
  3. Implement: `plugins/tcs-patterns/scripts/patterns_drift.py`, reading the manifest and the
     catalogue `VERSION` files.
  4. Validate: `python3 -m pytest tests/test_patterns_drift.py -q`; run it against a fixture
     repository holding a deliberate subset.
  5. Success:
     - [x] One `DRIFT:` line per behind pattern, with both versions `[ref: PRD/F7 1st; SDD/AC-11]`
     - [x] Silence about patterns this repository did not install `[ref: PRD/F7 2nd]`
     - [x] `OK` when all current, `MISSING` without a manifest `[ref: SDD/AC-11]`

- [x] **T4.3 The session-start advisory segment** `[activity: platform-operations]`

  1. Prime: Read how segments are composed —
     `plugins/tcs-git-helpers/scripts/session-start-brief.sh` lines 145-185, where `drift_seg` is
     built and then joined with the others — and the coordination requirement
     `[ref: SDD/Deployment View/Multi-Component Coordination]`.
  2. Test: A drifted pattern produces a segment naming the pattern, both versions and the command;
     all current produces **no** segment at all; no manifest produces no segment (F7's fourth
     criterion — `MISSING` is suppressed here even though the contract reports it); `tcs-patterns`
     absent or at `1.x`, so the drift script does not exist, produces no segment and no error; the
     existing hooks segment is unaffected when both fire. Assert substrings through a `grep -qF`
     helper, not a bare `[[ ]]`.
  3. Implement: one new segment in the existing composition, mirroring the wording of the hooks
     advisory (`hooks v2.2.21 → v2.2.22; run /tcs-git-helpers:git-setup --update`).
  4. Validate: the bats leg; run a real session in a fixture repository and read the advisory —
     and remember the plugin cache is stale inside the session that updated it, so a live check
     needs a new session.
  5. Success:
     - [x] Drift named with both versions and the command `[ref: PRD/F7 1st]`
     - [x] Silent when current, silent without a manifest `[ref: PRD/F7 3rd, 4th]`
     - [x] Silent and error-free when `tcs-patterns` is absent `[ref: SDD/Deployment View]`

  **Validate step 4's live-session read is still pending, and carried to T5.5.** As of
  2026-10-06 the installed cache holds only `tcs-patterns` 1.4.4, which has no
  `patterns_drift.py`, so a new session today correctly shows nothing and proves nothing about
  drift. The stand-in is bats test 13, which runs the real hook against the real reporter in the
  repository layout. The live read needs a `tcs-patterns` 2.x build installed and a fresh session,
  because the cache is stale in the session that updated it. It also needs T5.1: the advisory
  names `/tcs-patterns:patterns-setup update`, which does not exist until that skill ships.
  Landed as 9edcc66. The review follow-ups are ce88cb5, which enforces line 204's
  `systemMessage` assertion (a non-final `!` that bats ignored; the three remaining sites are
  recorded on #173), and 41425e1 (repo layout wins over a cached copy).

- [ ] **T4.4 Phase validation** `[activity: validate]`

  Both legs, per leg. Confirm the two-way property that makes the grain worth its cost: a change to
  one pattern raises an advisory in a repository that installed it **and** stays silent in one that
  did not. Both halves in the same test run, because each alone is satisfiable by a broken
  implementation.

  - Success: drift suites green; the two-way property asserted; the advisory degrades silently when
    the plugin is absent `[ref: SDD/AC-11; PRD/F7]`
