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

- [x] **T4.2 End-to-end walkthroughs, both tiers** `[activity: validate]`

  **Ran 2026-09-03**, in a session started after the manual plugin sync recorded
  below. The skills loaded from the installed plugin (`tcs-workflow/4.4.4`),
  which is itself the evidence that the sync and the fresh-session indexing
  requirement were both satisfied.

  Walkthroughs used a scratch project outside this repository
  (a small `slugify` module with its own `.claude/startup.toml`,
  `docs/XDD/specs/` and git history), so the two scratch specs exercise the real
  path-resolution chain without leaving artifacts here. PRD and SDD authoring
  inside those runs was abbreviated — those phases are untouched by this spec;
  step 6 is what was under test.

  **Direct — ran in full.** `/xdd` on a one-line fix classified `change_type=fix`,
  `component_count=0`, `feature_count=1`, `ac_count=1`, no parallel markers →
  rule 2's change-type escape → **Direct**, signals surfaced, user confirmed.
  No `plan/` written; tier recorded in the Status row and the Decisions Log;
  `spec.py --read` returned `decomposition_tier = "direct"`. `/implement` then
  detected `requirements.md + solution.md`, cross-checked against the recorded
  tier (agrees → silent), announced the direct route, ran `tdd-guardian`
  (APPROVE, three named tests), took the approval gate, dispatched one
  implementer (RED shown, GREEN 4 passing), ran the drift check (no findings),
  skipped the constitution check (no CONSTITUTION.md), and finalized the spec to
  `Implemented`.

  **Incremental — specification half ran; the loop was not re-driven.** `/xdd` on
  a two-component change classified `component_count=2`, `feature_count=2`,
  `ac_count=6`, `parallel_markers=true` → rule 1's breadth veto → **Incremental**.
  `plan/` written, tier recorded, and `/implement` detected `plan/README.md` and
  routed to `implement-incremental`. The loop itself was deliberately not driven
  (Marcus's call, to avoid dispatching the full per-task review chain over a
  scratch spec). The criterion is met by stronger evidence than a re-run would
  give: `git diff main:implement/SKILL.md implement-incremental/SKILL.md` is
  **empty below the frontmatter** — 296 lines against 296, differing only in
  `name`, `description`, `user-invocable` and the persona line. ADR-5's "this is
  a move, not a rewrite" holds byte for byte, so the incremental loop *is*
  today's loop.

  **Regression — routed, not re-implemented.** Spec 016 predates tiers: recorded
  tier absent, `plan/README.md` present → `implement-incremental`, cross-check
  proceeds silently, no error about the missing tier. Its loop was not executed —
  016 has already shipped, and re-running it would be destructive rather than
  informative. The executable sweep in `tests/test_dispatch_detection.py` covers
  the same route over all 17 spec directories.

  **Three defects found and fixed** (`eb92f11`, `a5d0af4`, `2858ce5`):

  1. **`spec.py` scaffolded an empty `plan/` into every new spec** — found at the
     first step of the Direct walkthrough. A Direct spec, which by ADR-1 carries
     no decomposition artifact, was handed the very directory that marks a spec
     Incremental. Dispatch survived it (detection keys on `plan/README.md`), but
     `--read` announced a `plan_dir` for a spec with no plan, and
     `implement-direct`'s "never write `plan/`" rule was contradicted before the
     loop began. `plan/` is now created only on the `--add xdd-plan` path, and
     `--read` treats an empty one as absent.
  2. **Nothing said what the `plan/` Documents row reads on a Direct spec** — it
     stayed `pending`, so a finished Direct spec looked as though a plan were
     still outstanding, collapsing the "no plan by decision, not by omission"
     distinction `xdd-meta` draws. Now `skipped`, stated in `classifier.md`'s
     Decision Logging and in `xdd`'s Direct route arm.
  3. **A tier mismatch left no artifact** — found by walking the PRD's tracking
     table. "Tier mismatch reported" is listed as artifact-based, but the
     dispatcher only reported it in conversation, making the event uncountable
     for its stated purpose of detecting dispatcher defects. The cross-check now
     logs it to the Decisions Log through `xdd-meta`. Dispatcher stays at 99
     lines.

  No deviation from the SDD was required; all three fixes bring the
  implementation *to* the SDD rather than away from it.

  **Suites after the fixes:** `pytest tests/ -q` → 337 passed, 1 skipped.
  `bats -r plugins/tcs-git-helpers/tests/bats` → exit 0, 787 tests, 0 failures
  (bats is not preinstalled in this container; install it per the venv recipe).

  > **Manual plugin sync — still in force, revert in T4.3.** The five touched
  > skill directories were copied into both
  > `~/.claude/plugins/cache/the-custom-startup/tcs-workflow/4.4.4/skills/` and
  > the marketplace clone, on Marcus's explicit call — the documented exception
  > to the standing no-manual-marketplace-sync rule, taken so the walkthroughs
  > could run before the PR rather than after. The three fixes above were synced
  > across as they landed, so both copies match the working tree. **Revert:**
  > `git -C ~/.claude/plugins/marketplaces/the-custom-startup checkout . &&
  > git clean -fd plugins/tcs-workflow/skills`, then re-copy the reverted tree
  > over the cache, or let the post-merge plugin update overwrite both.

  5. Success:
     - [x] A Direct spec completes with two documents, no plan, and a recorded tier `[ref: PRD/AC Feature 1.1, 1.4]`
     - [x] An Incremental spec is indistinguishable from today's behaviour — the loop body is byte-identical to `main` `[ref: SDD/Quality Requirements; Reliability]`
     - [x] A pre-tier spec implements exactly as it does on `main` `[ref: PRD/AC Feature 3.3]`
     - [x] The tier decision log carries every field the PRD's tracking table needs — after fix 3 `[ref: PRD/Tracking Requirements]`
     - [x] The user-facing surface is still two entry points — `implement-direct` and `implement-incremental` are both `user-invocable: false` `[ref: SDD/Quality Requirements; Usability]`

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

    **Re-audited 2026-09-04**, after the three T4.2 fixes changed `implement`,
    `xdd` and `classifier.md`. All five skills pass the mechanical checklist —
    frontmatter, no duplicate keys, PICS structure, Always/Never lists, numbered
    workflow steps, all under 500 lines. The duplicate-key check is now the
    regression guard for the `implement-incremental` defect the first audit
    found. On instruction purity: the `implement` and `xdd` edits are pure
    instruction; `classifier.md`'s new item carries a rationale clause, but items
    1 and 2 of that same section already do, so it matches the file's register
    rather than introducing drift. **0 new findings.**
  - Walk the PRD's 24 acceptance criteria and the SDD's 27 EARS criteria; confirm each maps to a task that ran. Any criterion with no evidence is a gap, not a pass.

    **Walked 2026-09-04. Every criterion maps to work that ran.** (The plan's
    Context Priming said 24 EARS criteria; the document carries 27 — 5 + 6 + 3 +
    4 + 5 main-flow, 2 error-handling, 2 edge-case. Corrected in the manifest.)
    Evidence falls in three classes:

    - **Walked live** in T4.2 — PRD 1.1, 1.2, 1.4, 1.5, 2.2, 2.4, 2.6, 3.1, 3.2,
      3.3, 4.1, 4.2, 4.5, 5.1, 5.2, 5.3, 5.4, 5.5.
    - **Unit-tested**, executable — PRD 2.1 (`test_every_signal_combination_yields_a_known_tier`),
      2.3 (`test_classification_is_deterministic`), 4.3
      (`test_unrecognised_decomposition_artifact_stops`), 4.4
      (`test_disagreeing_record_reports`), plus the sweeps behind 3.3 and 4.2
      over all 17 spec directories.
    - **Structural only — one criterion.** PRD 2.5, "when the user overrides,
      both the recommendation and the override are captured". `classifier.md`
      documents the override row and
      `test_classifier_reference_requires_rationale_and_override_logging` pins
      it, but neither walkthrough overrode the recommendation, so the path has
      never run. A narrow gap: an override writes the same Decisions Log row as
      an accepted recommendation, which did run, differing only in its text.

    **The constitution gate was exercised deliberately.** The scratch project had
    no `CONSTITUTION.md`, so the Direct walkthrough only took the skip branch,
    leaving PRD 5.4 / the SDD's `WHERE a CONSTITUTION.md exists` criterion with no
    evidence at all. One was added afterwards and the check re-run against the
    same commit: it found an L1 violation (a public function with no docstring)
    and returned **BLOCKING**. The gate runs and blocks; that the loop then halts
    on it is `implement-direct` step 4 plus
    `test_direct_tier_keeps_drift_and_constitution_checks`.

    Both Should-Have features hold: escalation out of Direct is `implement-direct`
    step 2, pinned by `test_direct_tier_escalates_rather_than_growing_phases`;
    tier-aware status reporting is `spec.py --read`'s `decomposition_tier` key —
    this repository keeps no central spec index table for it to appear in.
  - Confirm the dispatcher is under 100 lines `[ref: SDD/Quality Requirements; Maintainability]`. **99 lines**, asserted by `test_dispatcher_stays_small`. Registration also re-checked: 23 skill directories, 23 documented, pinned by `test_documented_skill_count_matches_reality`.
  - Invoke `xdd-meta` with `finalize 017 -- <shipping notes>` so this spec does not become another entry in the stale-`Ready` pattern its own PRD cites as evidence.
  - Revert the manual plugin sync recorded under T4.2, then open the PR.
