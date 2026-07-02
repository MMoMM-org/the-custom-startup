---
title: "Phase 3: Optimizer integration, dogfood E2E, audit & release"
status: completed
version: "1.0"
phase: 3
---

# Phase 3: Optimizer integration, dogfood E2E, audit & release

## Phase Context

**GATE**: Read all referenced files before starting this phase.

**Specification References**:
- `[ref: SDD/Integration Points]` — optimizer→batch one-directional pointer
- `[ref: SDD/Runtime View/Primary Flow]` — end-to-end dogfood
- `[ref: SDD/Architecture Decisions ADR-6]`
- `[ref: PRD/Secondary User Journeys; PRD/Success Metrics]`

**Key Decisions**:
- ADR-6: pointer is one-directional text (optimizer → `/rule-enforcer --scan`), no
  back-call; sequencing = relocate first, then scan canonical files.
- Project rules: run skill-author audit before commit
  (`feedback_skill-author-on-creation`); release via plugin.json version bump, no manual
  marketplace/cache sync (`feedback_no-manual-marketplace-sync`).

**Dependencies**: Phase 2 complete (batch mode functional + tests green).

---

## Tasks

This phase connects the neighbor skill, proves the feature end-to-end against this
repo's real rule corpus (where dedup must fire on ≥3 already-enforced rules), then
audits and ships.

- [x] **T3.1 `memory-claude-md-optimize` pointer insertions (one-directional)** `[activity: skill-authoring]`

  1. Prime: Read `[ref: memory-claude-md-optimize/SKILL.md Constraints, Step 3, Step 4]`,
     `[ref: reference/categorization.md always/never/prefer]`, `[ref: SDD/ADR-6]`.
  2. Test (RED): (a) new `Never` bullet forbids the optimizer from mechanizing
     directives; (b) a detection subsection in Step 3 **"Categorize"** counts
     always/never/must candidates without classifying; (c) the Step 4 **"Propose"**
     report (writes `OPTIMIZATION-REPORT.md`) emits the "run `/rule-enforcer --scan` after
     this applies" pointer; (d) no `Skill(rule-enforcer)` back-call exists.
  3. Implement: Insert the three edits into `memory-claude-md-optimize/SKILL.md`.
  4. Validate: `grep` confirms pointer text + Never bullet; no back-call; optimizer's
     own line budget respected.
  5. Success: One-directional pointer wired `[ref: PRD/Secondary Journeys; SDD/ADR-6]`.

- [x] **T3.2 Dogfood E2E: `--scan` against this repo** `[activity: integration-test]`

  1. Prime: Read `[ref: SDD/Runtime View/Primary Flow]`, `[ref: PRD/Feature 3; EC-2]`;
     the real corpus is root `CLAUDE.md` + `docs/ai/memory/*` + `@`-imported `general.md`.
  2. Test: A live `--scan` run (a) discovers the sources, (b) proposes the venv /
     `--break-system-packages` and `fd`/`rg` rules as `new`, (c) marks no-edit-on-main
     and git bad-ops as hook-`already-enforced` (**≥2 hook dedup hits**; per alignment
     finding 4c skill-author-on-creation is memory-enforced, surfaced separately — not a
     hook dedup hit), (d) lists judgment-only rules ("English for all code", "DRY/YAGNI")
     under guidance, (e) writes nothing until the single confirm.
  3. Implement: Execute the scan; capture the consolidated table as evidence in the
     phase file (do not accept/apply during the test — read-only verification).
  4. Validate: Dedup hits ≥3; zero false-positive block hooks proposed; every row cites
     `file:line`.
  5. Success: E2E behavior matches spec on real data `[ref: PRD/SM-2, SM-3, SM-6; EC-1,EC-3]`.

- [x] **T3.3 skill-author audit of modified rule-enforcer** `[activity: validate]`

  1. Prime: `[ref: CLAUDE.md Testing Skills During Development; feedback_skill-author-on-creation]`.
  2. Test: Audit reports no blocking issues (description/trigger quality, PICS structure,
     line budget, lazy-load discipline).
  3. Implement: Run `Skill(tcs-helper:skill-author)` audit on the modified
     `rule-enforcer` skill; address any findings.
  4. Validate: Audit passes; all self-tests still green afterward.
  5. Success: Skill passes authoring audit `[ref: project rule]`.

- [x] **T3.4 Release: tcs-helper version bump** `[activity: release]`

  1. Prime: `[ref: feedback_no-manual-marketplace-sync; reference_tcs-bundle-versioning-pattern]`.
  2. Test: `plugins/tcs-helper/plugin.json` version bumped per semver (minor — new
     feature); CHANGELOG/README updated if the repo convention requires.
  3. Implement: Bump the version; do NOT `cp` into cache/marketplace dirs.
  4. Validate: Version bump committed; CI auto-bump (if any) not conflicting.
  5. Success: Release-ready via version bump `[ref: PRD/Deployment View]`.

## Deviations & Findings (recorded per deviation protocol)

- **Dogfood finding (T3.2), signal (b) PARTIAL — not a bug:** `fd`/`rg` surfaces as `new`,
  but the venv / `--break-system-packages` rule is **out of default scope** — its
  actionable form lives in `~/Kouzou/standards/guardrails.md` (reached only via a "see X"
  prose pointer, not an `@`-import) and in global auto-memory (excluded unless
  `--scope global`). The sweep behaves correctly for its documented scope; the PRD's
  example assumption (venv in `general.md`) was slightly off. Remediation for users:
  `@`-import `guardrails.md` into `general.md`, or run `--scope global`. No code change.
  Dedup (≥2 hook hits), judgment-only filtering, high-FP demotion, and read-only-ness
  all PASS against live data.

- **skill-author audit (T3.3): NEEDS FIXES (no hard FAIL). Applied:** #1 description now
  advertises batch mode (auto-discoverable); #2 `allowed-tools` corrected (dropped unused
  `Task`, added `Skill`/`Write`/`Bash`); #9 stale flag `--from-claude-md` → `--scan` in
  `scan-sources.md`; #6 added `## Reference Materials` section. **Deferred (Low/Optional,
  non-blocking):** #4/#11 normalize `examples.md` Q3 lines to bare labels (canonical bare
  labels already live in `extraction-heuristics.md`; label-drift + parity tests enforce
  correctness); #5 externalize Step 8 to shrink toward the &lt;200-line soft target (332/500,
  touching the interactive path is higher risk than value now); #7 batch `**B1**` vs `### `
  formatting (audit: acceptable as-is); #8 instruction-purity ADR/CON parenthetical strip.
  #13 (batch trigger discoverability) addressed via #1 — `trigger-phrases.md` deliberately
  left alone (it feeds the recurrence-nudge hook; batch phrases are not recurrence signals).

- [x] **T3.5 Phase 3 Validation & full suite** `[activity: validate]`

  - Run the full self-test suite (`test_examples_md.sh`, `test_batch_q3_labels.sh`,
    `test_batch_parity.sh`, `test_batch_security.sh`) + any bats suites (sandbox
    disabled). Confirm interactive-mode regressions are zero, the optimizer pointer is
    present, the dogfood evidence is captured, the skill-author audit passed, and the
    plugin version is bumped. Verify all PRD acceptance criteria (AC-1..AC-12) trace to
    a completed task.
