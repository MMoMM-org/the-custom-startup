---
title: "Phase 2: Detection, fixtures before rules"
status: in_progress
version: "1.0"
phase: 2
---

# Phase 2: Detection, fixtures before rules

## Phase Context

**GATE**: Read all referenced files before starting this phase.

**Specification References**:
- `[ref: SDD/Interface Specifications/Data model: detection report]` — the JSON contract, including
  why `baseline`, `gates` and `unrecognised_stack` are separate fields
- `[ref: SDD/Interface Specifications/Data model: fixture expectation]` — `expected.json` and why
  `must_not_propose` is deliberately redundant
- `[ref: SDD/Runtime View/Complex Logic]` — the gating traced step by step against a real stack,
  ending in the 7 + 8 + 6 = 21 arithmetic
- `[ref: SDD/Implementation Examples]` — nested manifests and runtime-only dependencies
- `[ref: SDD/Architecture Decisions/ADR-2]` — why this is Python
- `[ref: SDD/Architecture Decisions/ADR-5]` — unrecognised stack versus closed gates
- `[ref: SDD/Architecture Decisions/ADR-7]` — the duplicated Obsidian rule
- `[ref: PRD/F2, PRD/F3]` — nine acceptance criteria between them
- `[ref: PRD/Detailed Feature Specifications]` — the six business rules and seven edge cases
- `[ref: PRD/Risks and Mitigations]` — the top risk this phase exists to answer

**Key Decisions**:
- **Fixtures come before rules.** The PRD's top risk is that the detection rules were authored and
  graded by the same party. A fixture written after the rule it checks inherits that rule's blind
  spots, so `expected.json` is written from the *specification* and the rule is then made to
  satisfy it.
- The detector is **pure**: it reads a directory and returns a report. It writes nothing, asks
  nothing, and never consults the catalogue for anything but the list of pattern names. That is
  what makes it callable against a fixture without the interactive setup.
- A gate decides **whether to ask**, never what to install. No pattern is installed because a gate
  opened.

**Dependencies**:
- Phase 1 complete — the detector needs the catalogue's pattern name list, and the Obsidian
  agreement test needs the relocated pattern.

---

## Tasks

Delivers a detector that a second party can trust, because the corpus it is measured against was
written from the specification rather than from the implementation.

- [x] **T2.1 The fixture corpus and its expectation format** `[activity: testing]`

  1. Prime: Read the fixture expectation contract
     `[ref: SDD/Interface Specifications/Data model: fixture expectation]`, **the detection rules
     themselves** `[ref: SDD/Interface Specifications/Detection rules: the eight stack facts and
     the three gates]`, the numbered traps `[ref: SDD/Quality Requirements/The seven traps,
     numbered]` and the PRD's edge cases `[ref: PRD/Detailed Feature Specifications]`. Build each
     fixture from the written rule, not from any code — no detector exists yet, which is the
     point. Both of those first two references were added on 2026-10-03 because neither the rule
     signals nor the trap numbering had ever been written down; before that there was no written
     rule for this step to read.
  2. Test: The loader itself is tested first: every fixture directory contains `repo/` and
     `expected.json`; every `expected.json` validates against the declared shape; every pattern
     named anywhere in any fixture is one of the 21 read from the catalogue, not hardcoded. A typo
     in a fixture must fail loudly rather than quietly assert nothing.

     **Three guards are mandatory, because "fail loudly" does not happen by default.** Measured
     on 2026-10-03, same pytest as the repo baseline:

     - a bare `for p in corpus.glob(...)` loop over an **empty** corpus reports `1 passed` —
       the body never runs and the test asserts nothing;
     - `@pytest.mark.parametrize` over that same empty glob reports `1 skipped`, **exit 0**,
       with `got empty parameter set` — a green suite containing zero cases, which is worse,
       because T2.1's own validate step reads "every case collected";
     - a module-level `ImportError` reports `ERROR collecting` and **exit 2** — and aborts the
       **whole session**, so `pytest -q` runs none of the repo's other tests. Measured on this
       branch when the detection test imported the absent detector at module level:
       `1 deselected, 1 error`, exit 2, with all 821 existing tests left unmeasured.

     So: (1) assert the corpus size in a **standalone, non-parametrized** test —
     `assert len(fixtures) == 18` — never only as a parametrize source, or an empty corpus
     passes; (2) assert `repo/` and `expected.json` exist per fixture before validating either;
     (3) accumulate every validation failure and assert once at the end, so eight bad pattern
     names report as eight and not as the first one.
  3. Implement: `tests/fixtures/patterns-detection/<case>/` with `repo/` and `expected.json`.
     Cases required:
     - one per auto rule (8)
     - one per trap (7), each naming the trap in `why` and listing `must_not_propose`
     - one true-negative: a stack none of the 21 cover, `auto: []`, `unrecognised_stack: true`.
       It may carry tests: `unrecognised_stack` reads `auto` alone, so `baseline: ["testing"]`
       alongside `unrecognised_stack: true` is the correct, consistent verdict and the fixture
       must not be made artificially testless to reach it
       `[ref: SDD/Architecture Decisions/ADR-5]`
     - one monorepo: empty root `dependencies`, the real signal three levels down, **and a
       populated `node_modules`** so the exclusion is asserted rather than assumed
     - one bare repository: no server framework, no tests — all gates closed, zero questions
     Fixtures are synthetic. No real repository is copied, and no real repository name or path
     appears in any fixture `[ref: SDD/Constraints/CON-8]`.
  4. Validate: `python3 -m pytest tests/test_patterns_detect.py -q` — every case collected, every
     one failing for want of a detector. A case that passes at this point is a case that asserts
     nothing.

     **The detector must be imported at *runtime*, inside the test or a fixture — never at module
     level.** "Every case collected" and a module-level `ImportError` are mutually exclusive: a
     collection error collects **zero** cases, fails this step and its success criterion on its
     own terms, and additionally aborts the full suite so the other 821 tests go unrun. The
     correct RED state is 18 collected, 18 failed, exit 1, with the rest of the suite still
     reported. This is written down because the opposite was tried on 2026-10-03 — the
     orchestrator's own dispatch brief demanded the module-level form, citing the exit-2
     measurement above as if it were the target rather than a hazard, and the implementer
     followed it and flagged the consequence.
  5. Success:
     - [ ] 18 fixtures collected, all failing for the right reason `[ref: PRD/Risks and Mitigations]`
     - [ ] Each of the seven traps has a fixture naming it `[ref: SDD/Quality Requirements]`
     - [ ] The true-negative and the monorepo case exist `[ref: PRD/F2 3rd; SDD/AC-4]`

- [x] **T2.2 The eight stack-fact rules** `[activity: backend-api]`

  1. Prime: Read the auto rules and their evidence requirements
     `[ref: SDD/Interface Specifications/Detection rules: the eight stack facts and the three
     gates]`, the report they fill
     `[ref: SDD/Interface Specifications/Data model: detection report]` and the parsing example
     `[ref: SDD/Implementation Examples]`. The first reference replaces a mis-pointer: this step
     used to send you to the detection-report model for "the auto rules", and that model is a
     JSON shape naming two patterns, not a rule set. Two traps are load-bearing here: runtime dependencies
     only, and nested manifests with vendored trees excluded.
  2. Test: The T2.1 fixtures for the eight rules, plus traps 2, 3, 4, 5 and 7 — DOM-render evidence
     required rather than a `ui/` directory name or `jsdom`; federated identity never inferred from
     session-token or password-hashing libraries; `devDependencies` never read as a runtime signal;
     nested manifests found and `node_modules` skipped; both `venv` and `.venv` recognised.
  3. Implement: `plugins/tcs-patterns/skills/patterns-setup/lib/detect.py` — the manifest walk, the
     runtime-dependency reader, the eight rules, and `evidence` naming the concrete file or
     dependency for every proposal. An unparseable manifest is skipped, never fatal.
  4. Validate: **12 of the 18 fixtures green, 6 still red** — `python3 -m pytest tests/test_patterns_detect.py -q` reports `12 passed, 6 failed` plus the standalone corpus
     guard, so `13 passed, 6 failed`, exit 1. Then `python3 -m pytest -q` for the full leg.

     **Not "those fixtures green", which this task cannot achieve.** The detection test
     asserts `report["gates"] == expected["gates"]`, so a fixture with any gate open stays
     red until T2.3 evaluates gates — including three this task's own Test step names:
     `auto-testing-baseline` and `trap-02` (q3), and `trap-03` (q1 and q2). Counted against
     the corpus, not estimated: 12 of the 18 fixtures have all three gates closed and are
     reachable here; the 6 that are not are `auto-testing-baseline`,
     `edge-unrecognised-stack-with-tests`, `trap-01`, `trap-02` (q3), `trap-03` (q1+q2) and
     `trap-06` (q2).

     This task must still **emit** the `gates` key or every fixture fails on a missing key.
     Emit all three as `false` — an honest placeholder that T2.3 replaces with real
     evaluation, not a rule. `unrecognised_stack` is different and belongs here: it is
     derived from `auto` alone `[ref: SDD/Architecture Decisions/ADR-5]`, so this task can
     and must compute it correctly.
  5. Success:
     - [ ] Every auto and baseline proposal carries `evidence` naming the file or dependency
           that justified it, asserted as three invariants in the detection test rather than
           declared per fixture: non-empty; its path part resolves to a file that exists in
           the fixture's `repo/`; and that path is not under `node_modules`, `.venv`, `venv`
           or `vendor`. Nothing asserted `evidence` before 2026-10-03, so a detector emitting
           `evidence: ""` satisfied all 18 fixtures while failing this criterion
           `[ref: PRD/F2 1st; SDD/Interface Specifications/Data model: fixture expectation]`
     - [ ] Traps 2, 3, 4, 5 and 7 each have a passing fixture that fails if the trap returns `[ref: SDD/Quality Requirements]`
     - [ ] `testing` is reported in `baseline` with `surface: false`, never as a recommendation `[ref: PRD/F2 5th; trap 1]`

- [ ] **T2.3 The three gates and the unrecognised-stack flag** `[activity: backend-api]`

  1. Prime: Read the gate table
     `[ref: SDD/Interface Specifications/Detection rules: the eight stack facts and the three
     gates]`, the gating walkthrough `[ref: SDD/Runtime View/Complex Logic]` and ADR-5
     `[ref: SDD/Architecture Decisions/ADR-5]`. The walkthrough traces one stack; the table is
     the rule set. The subtlety: `unrecognised_stack` is not "all
     gates closed". A repository in an uncovered language with a ports-and-adapters shape must
     still open Q2.
  2. Test: Q1 opens on a server framework in `dependencies` and not on one in `devDependencies`;
     Q2 opens on Q1 or on a content signal alone; Q3 opens on any test framework; the bare
     repository closes all three; the true-negative sets `unrecognised_stack` true while gates
     follow their own evidence; trap 6 — a hand-rolled event store with no broker dependency opens
     Q2 and auto-proposes nothing.
  3. Implement: the gate evaluation and `gate_evidence` in `detect.py`, plus `unrecognised_stack`
     computed independently of the gates.
  4. Validate: all 18 fixtures green — `python3 -m pytest tests/test_patterns_detect.py -q`
     reports `19 passed`, exit 0, the 18 comparisons plus the standalone corpus guard. Then
     `python3 -m pytest -q`. This task inherits **6 red fixtures** from T2.2 and its job is
     to turn exactly those green: `auto-testing-baseline`,
     `edge-unrecognised-stack-with-tests`, `trap-01` and `trap-02` (q3), `trap-03` (q1+q2),
     `trap-06` (q2). It also replaces T2.2's all-`false` gate placeholder with real
     evaluation, so a fixture that was green on the placeholder and goes red here means the
     gate logic is wrong, not the fixture.
  5. Success:
     - [ ] Zero questions for the bare repository `[ref: PRD/F3 1st]`
     - [ ] Never more than three gates open `[ref: PRD/F3 2nd]`
     - [ ] A closed gate yields no question rather than a question answered "none" `[ref: PRD/F3 3rd]`
     - [ ] An uncovered language with an architectural shape still opens Q2 `[ref: SDD/ADR-5]`

- [ ] **T2.4 The companion map, derived from the catalogue** `[activity: domain-modeling]`

  1. Prime: Read the companion map contract `[ref: SDD/Interface Specifications/Data model: companion map]`
     and the install unit `[ref: SDD/Runtime View]` — C5 copies one pattern directory, which is the
     whole reason this exists. Read `tests/test_tcs_patterns_catalogue_links.py`, whose resolution
     rule this reuses rather than reinvents.
  2. Test: Assert the derived map equals the nine measured pairs exactly — `ddd`→`hexagonal`,
     `event-driven`→`hexagonal`+`event-sourcing`, `event-sourcing`→`event-driven`+`hexagonal`,
     `hexagonal`→`ddd`, `observability`→`hexagonal`. Assert the relation is treated as a cycle and
     not a tree: `ddd`/`hexagonal` and `event-driven`/`event-sourcing` are mutual, so a naive
     transitive closure must not recurse forever. Assert a tenth cross-pattern reference, injected
     into a fixture, makes the test fail — a hardcoded table would pass and go stale.
  3. Implement: Derive the map by the link test's resolution rule: a code-span path resolving under
     no pattern root but another's is a companion edge. Expose it for C3 to read.
  4. Validate: `python3 -m pytest -q`; confirm the derived map's nine pairs against the table in
     the SDD.
  5. Success:
     - [ ] The derived map equals the nine pairs `[ref: SDD/Acceptance Criteria/AC-18]`
     - [ ] A tenth cross-pattern reference fails the test `[ref: SDD/Acceptance Criteria/AC-18]`
     - [ ] The cycle does not cause unbounded recursion `[ref: SDD/Interface Specifications]`
     - [ ] Nothing is installed by the map alone — it produces a proposal the user can decline
           `[ref: ADR-8]`

- [ ] **T2.5 The decided-exactly-once invariant** `[activity: testing]` `[parallel: true]`

  1. Prime: Read the arithmetic at the end of the walkthrough
     `[ref: SDD/Runtime View/Complex Logic]`. "Each of the 21 is decided exactly once" is F3's
     fourth criterion and is only a claim until something sums it.
  2. Test: For every fixture, and for every combination of answers to the open gates, the three
     outcome sets — installed, declined by question, excluded by stack fact — are pairwise disjoint
     and their union is exactly the 21 pattern names. Generated over the answer space, not written
     per case.
  3. Implement: the partition function in `detect.py` (or a thin module beside it) that returns the
     three sets, and the parametrized test that asserts the invariant.
  4. Validate: `python3 -m pytest -q`; introduce a deliberate double-assignment locally and confirm
     the test fails — an invariant test that cannot fail is decoration.
  5. Success:
     - [ ] Disjoint and summing to 21 for every fixture and every answer combination `[ref: PRD/F3 4th; SDD/AC-6]`
     - [ ] The test demonstrably fails on a seeded double-assignment `[ref: SDD/Quality Requirements]`

- [ ] **T2.6 The Obsidian rule agreement test** `[activity: testing]` `[parallel: true]`

  1. Prime: Read ADR-7 `[ref: SDD/Architecture Decisions/ADR-7]` and the existing bash gate in
     `plugins/tcs-patterns/scripts/block-eslint-disable.sh`. The hook must stay standalone: giving
     a write-time guard a dependency outside itself is the failure mode issue #163 already records
     twice here.
  2. Test: For every detection fixture, the bash gate's verdict on `repo/` equals the Python rule's
     `obsidian-plugin` proposal. Both directions matter — a fixture the bash gate accepts and the
     detector rejects is as much a divergence as the reverse.
  3. Implement: `tests/test_obsidian_rule_agreement.py`, invoking the bash gate as a subprocess
     against each fixture and comparing. No new abstraction, no shared source.
  4. Validate: `python3 -m pytest tests/test_obsidian_rule_agreement.py -q`; change one rule
     locally and confirm the test fails.
  5. Success:
     - [ ] Identical verdicts across all fixtures `[ref: SDD/AC-14]`
     - [ ] A one-sided change to either rule fails the test `[ref: SDD/ADR-7]`

- [ ] **T2.7 Phase validation** `[activity: validate]`

  Both legs, reported per leg. Confirm the detector is callable against a fixture directory with no
  interactive setup and no catalogue writes — the property the PRD's top-risk mitigation depends on.
  Confirm every fixture's `why` field reads as an explanation a second party could act on, because
  a fixture whose purpose is unclear will be deleted by someone later.

  **Held-out validation, mandatory and specified here because the corpus cannot provide it.**
  The 18 fixtures are the detector's own test data, so a detector that fits them passes them.
  The PRD's top risk is not answered by green fixtures; it is answered by rules holding on a
  tree the implementer never saw. Four such cases were built on 2026-10-03 **before** T2.2's
  implementer began, with every expectation derived from `[ref: SDD/Interface Specifications/
  Detection rules: the eight stack facts and the three gates]` and cited clause by clause.
  Rebuild and run them; they are deliberately **not** fixtures, because the corpus count is
  asserted at exactly 18 and these must never become data the implementation is tuned to:

  | Case | Tree | What only this case proves |
  |---|---|---|
  | mixed Go + Python | root `go.mod`, `cmd/main.go`, `cmd/main_test.go`, `services/api/backend/pyproject.toml` with `django` + `pyjwt`, `services/api/backend/app.py`, `vendor/github.com/x/ui/tsconfig.json` | two ecosystems at once; `vendor/` as the excluded dir; a **server framework three levels down**; Go tests as framework evidence; `typescript-strict` refused from a vendored tree |
  | bare Go | `go.mod`, `cmd/main.go`, `cmd/hello_test.go` | `testing` firing with no test directory at all, via the tests-beside-code clause |
  | vendor only | `vendor/x/tsconfig.json` and nothing else | `auto: []` with `unrecognised_stack: true`, and the exclusion applying to a non-manifest file search |
  | setup.py | `setup.py` with `install_requires` holding `mcp`, plus `src/app.py` | the `setup.py` reader, which **no fixture exercises** -- flagged by T2.2's implementer as implemented and unverified |

  Run the evidence invariants against these too, since they are the only trees where a
  fabricated `evidence` path cannot hide behind a fixture that happens to contain it.

  Measured against T2.2's detector (`94da599`..`bc6e28f`): all four correct on `auto`,
  `baseline`, `unrecognised_stack`, `must_not_propose`, `manifests_walked` and every evidence
  invariant; only `gates` diverged, which is T2.2's placeholder. Re-run after T2.3 and expect
  zero divergence.

  **The rule that makes this worth anything:** a divergence is resolved against the SDD, never
  against the fixtures, and never by editing an expectation to match the output.

  - Success: 18 fixtures green; all four held-out cases matching the written rules with no
    divergence; detection suite runnable standalone; both legs green per leg
    `[ref: SDD/AC-3, AC-4, AC-5, AC-6, AC-14; PRD/Risks and Mitigations]`
