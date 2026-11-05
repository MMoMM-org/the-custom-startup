---
title: "Phase 1: Catalog, Lint and Single-Source Test"
status: in_progress
version: "1.0"
phase: 1
---

# Phase 1: Catalog, Lint and Single-Source Test

## Phase Context

**GATE**: Read all referenced files before starting this phase.

**Specification References**:
- `[ref: SDD/Application Data Models]` — CatalogEntry, the initial entries PA-01–PA-52, CatalogIndex, PortProfile
- `[ref: SDD/Implementation Examples]` — entry format, fingerprint test trace, W1 trace, lint test examples
- `[ref: SDD/Internal API Changes]` — prompt_lint.py CLI contract and exit codes
- `[ref: SDD/Architecture Decisions]` — SDD-ADR-1, SDD-ADR-2, SDD-ADR-5, SDD-ADR-6
- `[ref: research-internal.md (A)]` — sources of each migrating rule; `[ref: research-external.md §1-§5]` — evidence for entries and profiles
- `[ref: research-technical.md §2]` — measured false-alarm rates

**Key Decisions**:
- The catalog is the only place a rule is stated. Phase 1 writes it; Phase 3 makes the consumers cite it.
- Fingerprints must be sentences only the rule would contain (SDD Implementation Gotchas).
- The lint registers only E1–E4 and W1–W3. Checks with a high false-alarm rate are not registered.
- `MUST BE USED` in frontmatter is never flagged (repo ADR-4).

**Dependencies**:
- None. The spec is approved. Work happens on a feature branch off main (not on `feat/prompt-author-spec` unless the user says so).

---

## Tasks

Establishes the shared, evidence-graded rule source and the mechanical checks that later phases and the skill build on.

- [x] **T1.1 Failure catalog and index** `[activity: technical-writing]` `[component: C1]`

  1. Prime: Read the entry format and the initial entry list `[ref: SDD/Application Data Models]`, then the rule inventory and its contradictions `[ref: research-internal.md (A), (F)]`. Read the vendor quotes for the corrected rules `[ref: research-external.md §1-§2]`, the measured modes `[ref: experiment/results.md]` and the corpus modes `[ref: research-corpus.md NEW failure modes]`.
  2. Test: T1.4 is the executable check of this task (format fields, unique IDs, index ↔ sections agree). Write the parts of T1.4 that check format, IDs and the index *first*. They assert the exact INITIAL ENTRIES ID set from solution.md, so they are red on an empty catalog rather than passing vacuously.
  3. Implement:
     - Create `catalog/index.md`, `core.md`, `agentic.md`, `instruction-files.md`, `porting.md` and `harness.md` under `plugins/tcs-helper/skills/prompt-author/reference/catalog/`, with entries PA-01–PA-52 as listed.
     - Each entry stays at or under 12 lines.
     - The corrected entries carry their vendor sources:
       - PA-01: reason clause, history stripped.
       - PA-03: no authority language; one restated terminal constraint is allowed.
       - PA-11: 3–5 diverse examples, each behaviour also a rule.
     - PA-50 is `contested`, citing repo ADR-4 and docs/ai/memory/decisions.md.
     - Lint-backed entries name their check (E1–E4, W1–W3).
  4. Validate: T1.4 format checks pass. Read every entry once for "one tell, one clause, one fix" and for fingerprints that are distinctive.
  5. Success:
     - [ ] Every mode the PRD lists has an entry, with tell, failure, fix, scope and evidence grade `[ref: PRD/F1 "at least these entries"]`
     - [ ] The three contradicted rules appear only in corrected form with sources `[ref: PRD/F1 "stated in corrected form"]`
     - [ ] PA-50 is contested, pointing to repo ADR-4, wording of the rule unchanged `[ref: PRD/F1 "marked contested"]`

- [x] **T1.2 Port profiles** `[activity: technical-writing]` `[component: C1]` `[parallel: true]` — after T1.1 (profiles cite its IDs, and its checks extend the T1.4 test file); parallel with T1.3 only

  1. Prime: Read the PortProfile model and SDD-ADR-6 `[ref: SDD/Application Data Models; SDD/Architecture Decisions SDD-ADR-6]`, the vendor guidance and divergences `[ref: research-external.md §1]`, and the T5 findings `[ref: experiment/results.md T5 rows, Observations 3]`.
  2. Test: Add to T1.4: every profile file has the topics placement, delimiters, examples, negatives, emphasis, literalness and turn shape, and every topic has source, date and evidence. Run it and see it fail before the profiles exist.
  3. Implement: Create `reference/profiles/{anthropic,openai,google,small-local}.md`.
     - small-local grades turn shape and gate exits as `measured` (T5). Everything else in small-local is `unverified`.
     - Source dates are the fetch dates in research-external.md (2026-11-04).
  4. Validate: The profile checks in T1.4 pass. No profile restates a catalog entry; profiles cite PA IDs instead.
  5. Success: Four profiles exist, each topic sourced and dated, with unverified entries labelled `[ref: PRD/F4 "applies that target's profile"; PRD/F4 "labelled unverified"]`

- [x] **T1.3 Prompt lint** `[activity: backend-tooling]` `[component: C3]` `[parallel: true]`

  1. Prime: Read the CLI contract `[ref: SDD/Internal API Changes]`, SDD-ADR-5, the W1 trace `[ref: SDD/Implementation Examples]` and the lint-as-test precedent `tests/test_shell_portability_lints.py`. Read the measured false-alarm table `[ref: research-technical.md §2]` and `plugins/tcs-helper/scripts/lib/semantic_detector.py:128-135`.
  2. Test: Write `tests/tcs-helper/test_prompt_lint.py` with fixtures under `tests/tcs-helper/fixtures/prompt_lint/`:
     - one positive and one negative fixture per check E1–E4 and W1–W3;
     - E4 flags semantic_detector.py at the first line of both prompt literals: 128–136 (#253) and 94–98 (`_claude_contradiction`);
     - E4 does not treat quotes as a delimiter, and does treat a `<tag>…</tag>` pair or a fence as one;
     - E3: fixtures for `~`/URL/absolute targets (skipped) and for anchors with a dash, slash, backtick and a duplicate heading (GitHub slug rule);
     - W1 does not count `CRITICAL`, inline code or enum listings;
     - frontmatter `MUST BE USED` is not flagged;
     - `lint-ok: <check> <reason>` suppresses on the same line and on the line above, and a suppression without a reason does not count;
     - fenced blocks are skipped except for E1;
     - a secret's value never appears in the output;
     - exit codes 0, 1 and 2 (forced internal error);
     - linting a Python fixture whose import would create a file leaves no file;
     - the registry contains exactly the seven checks;
     - `--json` shape.

     Add `tests/tcs-helper/test_prompt_lint_repo.py`: `--repo` over `git ls-files` produces 0 unsuppressed errors. All of these tests fail before the script exists.
  3. Implement: Create `plugins/tcs-helper/skills/prompt-author/scripts/prompt_lint.py`.
     - stdlib only, Python ≥ 3.8, `ast.parse` for `.py`;
     - a check registry with levels;
     - kind inference from path patterns;
     - text and `--json` output;
     - the W1/W2/W3 thresholds from SDD-ADR-5.

     Run `--repo` over the prompt-file set defined in the SDD CLI contract (with its exclusions), and resolve every error, either by a fix that is in scope or by a `lint-ok` with a reason. semantic_detector.py is Must Not Touch: its two E4 findings go into a `KNOWN_OPEN` allow-list in test_prompt_lint_repo.py, keyed by path, check and issue number (#253 for 128–136; #253 also for 94–98 — the user chose to extend #253, comment posted 2026-11-05). Re-run the W1/W2 calibration on this set and record the numbers.
  4. Validate: Both test files pass on ubuntu and macOS (CI). `--repo` takes < 10 s. Error-level false alarms on the repo are ≤ 1, each one listed in the commit message.
  5. Success:
     - [ ] E1–E4 are errors and W1–W3 are warnings, with thresholds as in SDD-ADR-5 `[ref: PRD/F5 AC1, AC2]`
     - [ ] High false-alarm checks are absent from the registry `[ref: PRD/F5 "routed to review or the judge"]`
     - [ ] The repo run has ≤ 1 false alarm and every suppression is visible with its reason `[ref: PRD/F5 "no more than one false alarm"]`
     - [ ] repo ADR-4 descriptions are not flagged, an internal failure exits 2 (the skill continues), and the lint never executes code `[ref: PRD/F5 AC5-AC7 (AC6 amended)]`

- [x] **T1.4 Catalog consistency test** `[activity: testing]` `[component: C5]`

  1. Prime: Read the fingerprint trace `[ref: SDD/Implementation Examples]`, SDD-ADR-2, and the precedent `tests/test_model_ladder.py` (slicing by heading).
  2. Test: Create `tests/tcs-helper/test_prompt_catalog.py` with these checks:
     - every `## PA-NN` section has all CatalogEntry fields;
     - IDs are unique and every index row matches a section, and vice versa;
     - no fingerprint occurs in any git-tracked `.md` under `plugins/` or `docs/about/` outside `catalog/`;
     - every `PA-NN` token outside the catalog resolves to an active entry;
     - no file contains an `@`-import of a catalog file;
     - every `claude plugin eval` command in any `.md` under `plugins/tcs-helper/` (eval-loop.md, evals/README.md once they exist) carries `--no-publish` and `--output-dir`, and — from T2.4 on — eval-loop.md must exist (an `xfail(strict=True)` removed in T2.4);
     - the current `MUST BE USED` sentences in agent-author are pinned.

     The "consumers cite an ID" check is parametrised per consumer (skill-author, agent-author, memory-claude-md-optimize), each marked `xfail(strict=True)`. Each marker is removed in the Phase 3 task that makes that consumer cite: skill-author and agent-author in T3.1, memory-claude-md-optimize in T3.5. Seed the test with one deliberate copy and one dead ID in temporary fixture files and confirm both fail.
  3. Implement: Fix catalog fingerprints that collide with existing text in the repo. A collision means the fingerprint is not distinctive or the rule is still copied. A copy found now is recorded for Phase 3 and allow-listed in the test with the Phase 3 task ID, never silently.
  4. Validate: `pytest -q tests/tcs-helper/test_prompt_catalog.py` passes, with only the allow-listed pre-migration copies and the per-consumer strict xfails. Runtime < 5 s.
  5. Success:
     - [ ] A copied fingerprint, a dead or retired ID, or an `@`-import fails the test with file:line `[ref: PRD/F1 AC5, AC6]`
     - [ ] The allow-list of pre-migration copies is explicit and owned by Phase 3 tasks `[ref: SDD/SDD-ADR-2]`

- [x] **T1.5 Phase Validation** `[activity: validate]`

  - Run `pytest -q -rs`; the full suite stays green.
  - Run `prompt_lint.py --repo`. Both pass.
  - Verify against the SDD:
    - the entry list matches `solution.md` § Application Data Models (INITIAL ENTRIES);
    - the lint registry matches SDD-ADR-5;
    - the profiles match SDD-ADR-6.
  - Commit after each task. Record the measured repo lint numbers (errors, suppressions, W1 hits) in this file under a "Phase 1 results" heading.

- [ ] **T1.6 Evidence grade `research` and drift fixes** `[activity: technical-writing]` `[component: C1, C3]` — added after the phase 1 drift check (2026-11-05)

  1. Prime: Read the revised evidence definition and INITIAL ENTRIES grades `[ref: SDD/Application Data Models]` and the "Further as-built details" lines `[ref: SDD/Internal API Changes]`; PRD F1 AC1 (five grades).
  2. Test: Extend the grade tests (tests/tcs-helper/test_prompt_catalog.py and test_prompt_profiles.py) to the five-grade enum and to the expected grade per entry from solution.md INITIAL ENTRIES (first word of the grade column); red on the current catalog. Add a lint test that the E0 finding's entry is "uncatalogued" in text and JSON; red.
  3. Implement: Add `research` to the enum; regrade catalog entries and profile topics so that vendor means a model vendor's own guidance and published research or OWASP is `research` (at least PA-10, PA-15, PA-19, PA-30, PA-31; check every entry and topic against its Sources line); update index rows; set the E0 entry to "uncatalogued" in prompt_lint.py.
  4. Validate: catalog, profile and lint tests green; full suite green.
  5. Success: no source that is not a model vendor is graded vendor `[ref: PRD/F1 AC1 (amended)]`; every lint finding names an entry or "uncatalogued" `[ref: SDD/Quality Requirements]`

## Phase 1 results

- Commits: f8c4c183, fa272848 (T1.1); 28df8672, 3c27be38, 1fc6ccae (T1.2, escalated to opus@max after two review FAILs); ddb0f7df, 6393a844 (T1.3); bc075cbf, 69000545, ab94fb4a, 2b898499 (T1.4).
- Tests: full suite 2053 passed, 2 skipped, 4 strict xfails (eval-loop.md → T2.4; consumer citations skill-author, agent-author → T3.1, memory-claude-md-optimize → T3.5), all in tests/tcs-helper/test_prompt_single_source.py.
- Catalog tests split: tests/tcs-helper/catalog_helpers.py + test_prompt_catalog.py, test_prompt_profiles.py, test_prompt_single_source.py.
- Lint `--repo`: 258 files, ≈1.5 s; errors = 2 (both KNOWN_OPEN #253, semantic_detector.py:95 and :129); warnings W1 = 4, W3 = 4, W2 = 0; 0 suppressions; 0 error-level false alarms.
- Pre-migration fingerprint copies: none (paraphrased copies tracked via research-internal.md (A); Phase 3 red steps adjusted).
- Side fixes: `--output-dir` added to the documented plugin-eval runs in skill-author/reference/plugin-evals.md and tcs-workflow/evals/README.md (privacy check now covers all plugins/).

