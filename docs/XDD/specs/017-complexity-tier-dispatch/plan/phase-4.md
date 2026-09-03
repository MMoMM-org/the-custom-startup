---
title: "Phase 4: Registration and end-to-end validation"
status: in_progress
version: "1.0"
phase: 4
---

# Phase 4: Registration and end-to-end validation

## Phase Context

**GATE**: Read all referenced files before starting this phase.

**Specification References**:
- `[ref: SDD/Directory Map]` — the repository-level registration list
- `[ref: SDD/Deployment View]` — the rollout claim this phase has to actually verify
- `[ref: SDD/Quality Requirements]` — the measurable bars: reliability over 16 specs, dispatcher under 100 lines, no growth in user-facing surface
- `[ref: SDD/Implementation Gotchas]` — `plugin.json` is CI's, and skills need a fresh session to be indexed
- `[ref: PRD/Success Metrics; Tracking Requirements]` — the five artifact-based events the decision log has to be able to carry

**Key Decisions**:
- **CON-6** — one plugin, one version bump, and the bump belongs to CI. A hand-edited `plugin.json` version is read by the auto-bump script as "already bumped" and the release is skipped.
- **ADR-3** — registration must not advertise a Factory tier. It does not exist.

**Dependencies**:
- Phases 1, 2 and 3 complete. This phase validates the assembled whole and cannot start earlier.

---

## Tasks

Registers the two new skills everywhere the repo tracks skills, and proves end to end that the tiers behave as specified and that nothing existing regressed.

- [x] **T4.1 Register the new skills** `[activity: docs]`

  1. Prime: Read the repository-level list `[ref: SDD/Directory Map]`. Note the count discrepancy found during design: the skill directories under `plugins/tcs-workflow/skills/` number 21 while `docs/reference/plugins.md` and `AGENTS.md` both say 20 — **count the directories, do not add two to the documented figure**.
  2. Test: Assert every registration surface names both `implement-direct` and `implement-incremental`, that the stated count equals the actual directory count, and that no surface mentions a Factory tier `[ref: SDD/ADR-3]`. Assert `plugins/tcs-workflow/.claude-plugin/plugin.json` has an unchanged `version` field `[ref: SDD/Constraints; CON-6]`.
  3. Implement: Update `README.md`, `AGENTS.md`, `docs/reference/plugins.md`, `docs/reference/skills.md`, and add the `tcs-workflow` CHANGELOG entry for the next patch version. Add tier-related keywords to `plugin.json` — keywords only.
  4. Validate: `bash scripts/ci/check-changelog-version-sync.sh --allow-ahead 1` exits 0. Confirm by `git diff` that the `version` field is untouched.
  5. Success:
     - [x] Both sub-skills are registered wherever skills are listed `[ref: SDD/Directory Map]`
     - [x] The documented skill count matches reality, and the pre-existing off-by-one is corrected `[ref: SDD/Known Technical Issues]`
     - [x] The CHANGELOG names the version CI is about to produce, and `plugin.json` is untouched `[ref: SDD/Constraints; CON-6]`

- [ ] **T4.2 End-to-end walkthroughs, both tiers** `[activity: validate]`

  > **Blocked on a session restart — after a manual plugin sync.** A session
  > restart alone is not enough, and the earlier note here was wrong about the
  > cause. Skills are loaded from the *installed* plugin
  > (`~/.claude/plugins/cache/the-custom-startup/tcs-workflow/<version>/`) and
  > validated against the marketplace clone, neither of which is this working
  > tree. On this branch both carried only the pre-split `implement`, so no
  > fresh session could invoke the new sub-skills until the branch merged and
  > CI released.
  >
  > Unblocked by copying the five touched skill directories into both
  > locations per the project instructions file (§ Testing Skills During
  > Development), on Marcus's explicit call — this is the documented
  > exception to the standing no-manual-marketplace-sync rule, taken so the
  > walkthroughs could run before the PR rather than after. **Revert after the
  > walkthroughs**: `git -C ~/.claude/plugins/marketplaces/the-custom-startup
  > checkout . && git clean -fd plugins/tcs-workflow/skills`, then re-copy the
  > reverted tree over the cache, or let the post-merge plugin update
  > overwrite both.
  >
  > The executable half of this task already runs green — the detection sweep
  > in `tests/test_dispatch_detection.py` covers the regression walkthrough
  > over all 17 real spec directories. What remains is driving `/xdd` and
  > `/implement` by hand at both tiers, in a session started after the sync.

  1. Prime: Read the primary sequence `[ref: SDD/Runtime View; Primary Flow]` and the rollout claim `[ref: SDD/Deployment View]`. Start a **fresh session** so the new skills are indexed `[ref: SDD/Implementation Gotchas]`.
  2. Test: Two scripted walkthroughs against a scratch spec, plus one regression walkthrough.
     - **Direct:** run `/xdd` on a one-line fix. Expect the classifier to recommend Direct with its signals shown, no `plan/` written, the tier recorded in both the Status row and the decision log, then `/implement` detecting no plan, announcing the direct route, running `tdd-guardian`, asking for approval, running drift and constitution checks, and calling `finalize`.
     - **Incremental:** run `/xdd` on a multi-component change. Expect Incremental, a `plan/` written, and `/implement` running the phase loop with both reviewers, exactly as it does on `main` today.
     - **Regression:** run `/implement` against an existing spec that predates tiers (spec 016). Expect the incremental route, no error about the absent tier, and no behavioural difference from `main`.
  3. Implement: Fix whatever the walkthroughs surface. Record any deviation from the SDD per the plan's Deviation Protocol.
  4. Validate: All three walkthroughs complete. `.venv/bin/python -m pytest tests/ -q` and `bats plugins/*/tests/bats` both green.
  5. Success:
     - [ ] A Direct spec completes with two documents, no plan, and a recorded tier `[ref: PRD/AC Feature 1.1, 1.4]`
     - [ ] An Incremental spec is indistinguishable from today's behaviour `[ref: SDD/Quality Requirements; Reliability]`
     - [ ] A pre-tier spec implements exactly as it does on `main` `[ref: PRD/AC Feature 3.3]`
     - [ ] The tier decision log carries every field the PRD's tracking table needs `[ref: PRD/Tracking Requirements]`
     - [ ] The user-facing surface is still two entry points `[ref: SDD/Quality Requirements; Usability]`

- [ ] **T4.3 Phase Validation and spec closeout** `[activity: validate]`

  - Run the full suite: `.venv/bin/python -m pytest tests/ -q`, `bats plugins/*/tests/bats`, `bash scripts/ci/check-changelog-version-sync.sh --allow-ahead 1`.
  - Run the `tcs-helper:skill-author` audit over all four touched skills — `xdd`, `xdd-meta`, `implement`, and both new sub-skills — and confirm 0 findings `[ref: SDD/Constraints; CON-7]`.

    **Ran 2026-09-03. Four defects found, all fixed in `09001f5`:** a duplicate
    `user-invocable` key in `implement-incremental` (`true` then `false`, leaving
    the hidden-skill intent to the parser), and workflow-summarising descriptions
    on all three `implement*` skills — the CSO anti-pattern the audit reference
    documents, where a description listing steps gets followed as a shortcut and
    the body goes unread. Descriptions rewritten to triggering conditions.

    **Three notes accepted rather than changed**, recorded so a re-audit does not
    re-raise them: the rationale clauses in `implement-direct`'s Never list are
    doing rationalization-counter work and stay; `xdd-meta`'s Factory rule keeps
    its negative-existence phrasing because ADR-3 wants Factory named as reserved;
    `xdd` and `xdd-meta` carry mildly workflow-summarising descriptions that
    predate this spec and are out of its scope.
  - Walk the PRD's 24 acceptance criteria and the SDD's 24 EARS criteria; confirm each maps to a task that ran. Any criterion with no evidence is a gap, not a pass.
  - Confirm the dispatcher is under 100 lines `[ref: SDD/Quality Requirements; Maintainability]`.
  - Invoke `xdd-meta` with `finalize 017 -- <shipping notes>` so this spec does not become another entry in the stale-`Ready` pattern its own PRD cites as evidence.
  - Revert the manual plugin sync recorded under T4.2, then open the PR.
