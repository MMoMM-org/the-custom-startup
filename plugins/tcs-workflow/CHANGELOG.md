# Changelog

All notable changes to `tcs-workflow` are documented here.

Patch versions are bumped automatically when a merge touches this plugin
(`.github/workflows/auto-bump-versions.yml`), so not every version has an entry.
Add one when a change is worth a reader's attention. The top entry must never
name a version `plugin.json` does not carry — `scripts/ci/check-changelog-version-sync.sh`
enforces that on every merge.

## [4.4.8] - 2026-09-03

### Added

- **Complexity-tier dispatch (spec 017, #83)** — `/xdd` now classifies a specification into a decomposition tier and `/implement` routes to the matching execution loop. A one-line fix gets a real artifact for roughly the cost of skipping the workflow, which is the pressure that produced the repo's own `feedback_spec_first` correction.
  - **`implement-direct`** (new, hidden) — phase-less loop: one to three delivery units, no plan artifact, no phase boundaries. Keeps `tdd-guardian`, the approval gate, and the drift and constitution checks; drops only the per-task spec-compliance and code-quality review chain. Escalates to Incremental rather than growing an unstructured loop.
  - **`implement-incremental`** (new, hidden) — today's phase loop, moved verbatim. A diff of its Workflow section against the pre-split `implement` is empty.
  - **`xdd/reference/classifier.md`** (new) — five signals read from the two documents already written, ordered rules, first match wins. Breadth is checked before change type, so a refactor spanning three components is not Direct just because it is a refactor.
  - **`decomposition_tier`** — a first-class lifecycle field, recorded in the spec README Status table (machine-readable), the Decisions Log (audit), and `spec.py --read`.

### Changed

- **`implement` is now a dispatcher**, not an orchestrator. It keeps its name and its `/implement` invocation; it detects which decomposition artifact a spec carries and hands off. 296 lines became 99. Routing reads artifacts rather than the recorded tier, because artifacts are ground truth while a record goes stale when a specification run is interrupted — the recorded tier cross-checks and reports the disagreement.
- **`xdd` step 6 is now Decompose**, not Write PLAN. It classifies, shows the signals that produced the recommendation, lets the user confirm or override, records the choice, and only then routes to `xdd-plan` or to nothing.
- **Skill count corrected from 20 to 23.** The documented figure was already wrong before this change — 21 directories described as 20 — and nothing checked it. A test now derives the number from the filesystem.

### Fixed

- **A new spec no longer scaffolds an empty `plan/`.** `spec.py` created one for every spec, so a Direct spec — which carries no decomposition artifact by design — was handed the directory that marks a spec Incremental. Dispatch survived it, but `--read` reported a `plan_dir` for a spec with no plan. The directory is now created only when the plan template is added, and an empty one reads as absent.
- **A Direct spec's `plan/` documents row now reads `skipped`.** It stayed `pending`, so a finished Direct spec looked as though a plan were still outstanding.
- **A tier mismatch is now logged, not only reported.** The PRD counts "tier mismatch reported" as an artifact-based event; the dispatcher reported it in conversation and wrote nothing, leaving the event uncountable for the purpose it exists to serve. The cross-check now writes a Decisions Log row through `xdd-meta` before asking.

All three were found by the spec's own end-to-end walkthroughs rather than by its tests.

### Note on scope

`Factory` is a reserved tier name with **no implementation**. TCS has no units, holdout scenarios, information barriers or retry loop, and every piece of evidence behind this change is about work too *small* for the current ceremony. The classifier never recommends it, the dispatcher stops rather than guessing a route for it, and no surface advertises it. Adding it later changes neither the classify nor the dispatch contract.

## [4.4.6] - 2026-09-03

Changelog started at the version the plugin already carried. Nothing is
reconstructed here — earlier history is in the repository's git log and in the
root `CHANGELOG.md`.
