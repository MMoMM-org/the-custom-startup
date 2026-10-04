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
     passes. (The literal `18` is what T2.1 was asked for and delivered; the count now lives in
     `tests/patterns_detection_corpus_lib.py`'s `EXPECTED_CASE_COUNT`, which T2.3 took to **26**
     when it added eight gate-coverage fixtures. The guard was renamed off its hardcoded count at
     the same time. The requirement here is the *standalone, non-parametrized* shape, not the
     number.) (2) assert `repo/` and `expected.json` exist per fixture before validating either;
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

- [x] **T2.3 The three gates and the unrecognised-stack flag** `[activity: backend-api]`

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

     **Eight fixtures were added on 2026-10-04 and the corpus is now 26, not 18** -- three for q1
     below (including the `// indirect` negative), five for q2 further down (including two
     threshold negatives). Two of the eight came from mutating T2.3's own output after the
     implementer reported done, which found two written thresholds that nothing enforced.
     Measured before
     dispatch: `q1_backend` had exactly one positive case in the whole corpus — `trap-03`, Python
     via `requirements.txt` — and one negative, `trap-04`, Node via `devDependencies`. No fixture
     declared a Node or Go server framework in `dependencies`, so a detector implementing Node's
     q1 path wrongly, or omitting Go's entirely, passed all 18. The two new cases close that, and
     both were written by the orchestrator from the rules as written, before any gate code existed,
     keeping T2.1's separation between who declares the expectation and who writes the rule:
     - `gate-q1-node-runtime-dependency` — `trap-04`'s package.json with the section renamed and
       nothing else changed except `name`, which no rule reads. The only detectable difference is
       the section, so it is the positive half of trap 4's pair. It also pins ADR-5 harder than
       `trap-06` does: no stack fact fires on a bare package.json, so `unrecognised_stack` stays
       **true while q1 AND q2 are open**.
     - `gate-q1-go-direct-require` — a `go.mod` with a direct `gin` and an indirect `chi`. q1 opens
       on `gin`; `chi` carries `// indirect` and must not be credited. The `gates` dict cannot
       separate those two, so the discrimination lives in q1's `gate_evidence`, which must list
       **every** contributing dependency, with `gin` present and `chi` absent. Completeness is what
       carries it and the naming does not: "names the direct one" is satisfied by luck, because a
       detector stripping `//` comments credits both and reports `gin` first anyway — it precedes
       `chi` at position 13 in file order and in sort order alike
       `[ref: SDD/Interface Specifications, "What a gate_evidence entry looks like when the signal
       is a dependency"]`.

     **`q2_architecture` had the same hole, and four more fixtures close it.** Measured: of the
     four weak content signals in the q2 row, only the `ports/`+`adapters/`+`domain/` triad had any
     fixture at all (`trap-06`). The per-module events files, the `event_store` directory and the
     broker dependency had **none**, so a detector implementing the triad and the q1 disjunct alone
     passed every case. One signal per fixture, because a fixture carrying two cannot say which one
     opened the gate:
     - `gate-q2-events-per-module` — two `events.py` in distinct module directories. q2 opens.
     - `gate-q2-single-events-file` — the same tree with **one**. q2 stays shut, enforcing the
       written "two or more" threshold and the reason given for it, that one such file is a utility
       rather than a convention. Note this case is **green on T2.2's all-`false` placeholder** and
       must stay green: it is a forward regression guard, not a RED→GREEN case, the same standing
       the spec gives traps 3, 4 and 6.
     - `gate-q2-event-store-dir` — one `src/event_store/` directory. q2 opens. Nested rather than
       at the root, so a detector inspecting only root-level names goes red.
     - `gate-q2-broker-dependency` — `kafkajs` in `dependencies`. q2 opens and **q1 stays shut**, so
       a detector matching any networking dependency for q1 goes red.

     Read also the 2026-10-04 ruling that the triad needs no common parent and that none of the
     four signals is depth-restricted `[ref: SDD/Interface Specifications/Detection rules]`. It was
     a genuine silence: `trap-06` places the three as siblings and therefore passes under either
     reading, so no fixture could have settled it.

     `EXPECTED_CASE_COUNT` is 24, and the guard was renamed from
     `test_corpus_has_exactly_18_cases` to `test_corpus_has_exactly_the_expected_number_of_cases`
     — it encoded the count in its own identifier and was cited by seven other assertion messages,
     so a corpus change left eight places reading `18` and only one of them checked.

     **Four assertions this step must direct, not merely require in its Success list.** Noted
     2026-10-04 after a gate observed that criteria 2 and 3 demand `gate_evidence`, `schema` and
     `repo` while this Test step never asked for any of them, and `grep -rn gate_evidence tests/`
     returned nothing but one fixture's prose. A requirement that lives only in a success checkbox
     is a requirement nobody is told to build. All four are **universal invariants in
     `tests/test_patterns_detect.py`**, never per-fixture data — the exact-key guard forbids a new
     `expected.json` key — and they follow the shape the existing `evidence` and `surface`
     invariants already use there:
     - every gate reported **open** has a non-empty `gate_evidence` entry, listing every signal
       that contributed, each citing a path that resolves inside that fixture's `repo/` and has no
       segment in `node_modules`, `.venv`, `venv` or `vendor`;
     - every gate reported **closed** has no entry at all;
     - `report["schema"] == 1`;
     - `report["repo"]` is the directory that was passed in, since all evidence is relative to it.

     Each must be shown to discriminate by deleting or weakening it and watching something go red.
     An invariant that survives its own mutation is decoration, and four tests in this phase were
     already found re-implementing the loop they claimed to exercise.

     Read the 2026-10-04 ruling **"Which declaration counts as `dependencies` outside
     `package.json`"** before implementing q1 `[ref: SDD/Interface Specifications/Detection rules]`.
     It is new, and without it three of the four ecosystems' q1 path are unwritten: a gate reads
     `package.json` `dependencies`, `pyproject.toml`'s `[project]` and `[tool.poetry]`
     dependencies, every line of `requirements.txt`, `setup.py`'s `install_requires`, and only
     **direct** `go.mod` requires. Note that `_go_mod_requires` currently strips `//` comments, so
     the indirect marker does not survive parsing and must be made to.
  3. Implement: the gate evaluation and `gate_evidence` in `detect.py`. `unrecognised_stack` is
     **already done** — T2.2 computed it from `auto` alone per ADR-5, which is independent of
     the gates by construction. Do not rework it; confirm it still holds once gates are live,
     since the whole point of ADR-5's clause is that an open gate must not flip the flag.
  4. Validate: all 24 fixtures green — `python3 -m pytest tests/test_patterns_detect.py -q`
     reports **`32 passed`** plus whatever this task adds, exit 0. The figure was `19` until
     2026-10-04 and was stale twice over: it counted 18 comparisons plus the standalone corpus
     guard, written before T2.1 and T2.2 added the four evidence-invariant tests, the wiring test
     and the two interpreter tests, and before the six gate fixtures took the corpus to 24.
     Measured after those were added: 32 collected, 11 failed / 21 passed; the corpus later grew to 26 as T2.3 found two more unenforced thresholds. A target figure nobody
     re-measures is the same defect class as an unasserted field — count the file, do not inherit
     the number. Then `python3 -m pytest -q`; baseline before this task is
     **11 failed, 852 passed, 1 skipped, 1 deselected**.

     This task inherits **11 red fixtures** and its job is to turn exactly those green:
     `auto-testing-baseline`, `edge-unrecognised-stack-with-tests`, `trap-01` and `trap-02` (q3),
     `trap-03` (q1+q2), `trap-06` (q2), the two q1 cases (q1+q2) and the three q2-positive cases
     (q2). The sixth added fixture, `gate-q2-single-events-file`, is already green and must stay
     green. Verified before dispatch that all eleven fail on the `gates` comparison at
     `test_patterns_detect.py:161` and on nothing else — every new fixture passes its `auto` and
     `baseline` assertions already, which is
     independent agreement between rules derived by the orchestrator and a detector written by
     T2.2's implementer. It also replaces T2.2's all-`false` gate placeholder with real
     evaluation, so a fixture that was green on the placeholder and goes red here means the
     gate logic is wrong, not the fixture.
  5. Success — restated 2026-10-04 to what this task's output can actually show. Two of the
     four criteria were transcribed from PRD/F3 lines about **questions asked**, which is
     C3's behaviour and T5.1's task; one of those could not fail at all, since there are
     exactly three gate keys and `EXPECTED_GATE_KEYS` enforces them:
     - [ ] The bare repository closes all three gates. "Zero questions" rests on that, but
           the question count itself is T5.1's to show `[ref: PRD/F3 1st]`
     - [ ] Every gate reported open carries non-empty `gate_evidence` whose paths resolve in
           the fixture's `repo/` and avoid excluded directories; every gate reported closed
           carries none. Asserted as invariants because no fixture declares `gate_evidence`
           and the exact-key guard would reject one
           `[ref: SDD/Interface Specifications/Data model: fixture expectation]`
     - [ ] `schema` and `repo` asserted too — the 2026-10-04 sweep over every report field
           found both unasserted. `schema == 1` is the handle a consumer would use to refuse
           an incompatible report; `repo` is what all evidence is relative to. Cheap, and
           they close the last of the six fields found this way
           `[ref: SDD/Interface Specifications/Data model: fixture expectation]`.
           **Kept deliberately against the objection** that these guard constants T2.2 already
           shipped rather than logic T2.3 writes, and so share the character of the two criteria
           this phase discarded. They do not: those two could not fail under any report the
           detector is able to emit, while changing the `schema` literal turns this one red. A
           regression guard on a one-line contract field is weak, which is a different thing
           from vacuous, and weakness is the correct price for the only versioning handle the
           report has
     - [ ] Q1 stays shut on a server framework that appears only in `devDependencies`
           (trap 4), and Q2 opens on a content signal alone with Q1 shut (trap 6)
     - [ ] An uncovered language with an architectural shape still opens Q2, and
           `unrecognised_stack` stays true there `[ref: SDD/ADR-5]`
     - [ ] Added 2026-10-04 with the two new fixtures. `q1_backend` opens on all three
           ecosystems and not only Python: Node from `dependencies`
           (`gate-q1-node-runtime-dependency`) and Go from a direct `go.mod` require
           (`gate-q1-go-direct-require`). Before those existed, q1 had one positive case in
           the corpus and omitting Go's path entirely cost nothing
           `[ref: SDD/Interface Specifications/Detection rules, "Which declaration counts as
           `dependencies` outside `package.json`"]`
     - [ ] A `go.mod` require marked `// indirect` does not open `q1_backend`, shown by q1's
           `gate_evidence` in `gate-q1-go-direct-require` listing **every** contributing
           dependency and that list containing `gin` and not `chi`. The completeness is what
           carries the check, not the naming: "names the direct one" alone is satisfied by luck,
           since a detector that strips `//` comments — which `_go_mod_requires` does today —
           credits both and would report `gin` first anyway, in file order and in sort order
           alike. `_go_mod_requires` must be made to preserve the marker
           `[ref: SDD/Interface Specifications, "What a gate_evidence entry looks like when the
           signal is a dependency"]`

     Moved to T5.1, where the behaviour actually lives: "no more than three questions, each
     allowing multiple answers" `[ref: PRD/F3 2nd]` and "a closed gate yields no question
     rather than a question answered 'none'" `[ref: PRD/F3 3rd]`.

- [ ] **T2.4 The companion map, derived from the catalogue** `[activity: domain-modeling]`

  1. Prime: Read the companion map contract `[ref: SDD/Interface Specifications/Data model: companion map]`
     and the install unit `[ref: SDD/Runtime View]` — C5 copies one pattern directory, which is the
     whole reason this exists. Read `tests/test_tcs_patterns_catalogue_links.py`, whose **extraction
     plumbing** this reuses — and whose **resolution rule** it must not.

     That sentence read "whose resolution rule this reuses rather than reinvents" until
     2026-10-04. **Checked before dispatch, and the half about the resolution rule was false.**
     Reuse what is genuinely shared and do not reach for the rest:

     | In `test_tcs_patterns_catalogue_links.py` | For T2.4 |
     |---|---|
     | `_pattern_root(path)` | **reuse** — maps a catalogue file to its pattern directory |
     | `_non_fenced_lines(text)` | **reuse** — a fenced example must not read as a real citation |
     | `FENCE`, `INLINE_CODE`, `LINK` | **reuse** — the same two citation surfaces |
     | `CODE_SPAN_PATH` | **do not reuse** — it requires `^(?:\.\./)+`, a leading climb, and rejects every companion citation, which has none |
     | `_violation(path, target, n)` | **do not reuse** — it resolves `path.parent / target`, relative to the *citing* file; T2.4 resolves against each *target pattern's* root |

     The two rules also have **opposite polarity**, which is worth holding in mind while reading
     that file: for the link test a path leaving its own pattern directory is a **defect**; for
     T2.4 a path resolving under another pattern is a **companion edge**. They do not conflict in
     practice — the link test keys on climbs and the companion citations never climb, so the two
     operate on disjoint sets — but an implementer who reuses `_violation` will report every
     companion as an escape violation. An instrument built on the `../` rule was measured at
     **zero** edges, which is how this was found.
  2. Test: Assert the derived map equals the **seven measured pattern-to-pattern edges** exactly —
     `ddd`→`hexagonal`, `event-driven`→`hexagonal`+`event-sourcing`,
     `event-sourcing`→`event-driven`+`hexagonal`, `hexagonal`→`ddd`, `observability`→`hexagonal`.
     Assert the relation is treated as a cycle and not a tree: `ddd`/`hexagonal` and
     `event-driven`/`event-sourcing` are mutual, so the closure traversal must carry a visited set.
     Assert a cross-pattern reference to a **new target**, injected into a fixture, makes
     the test fail — a hardcoded table would pass and go stale.

     **"Injected into a fixture" needs a mechanism, and the precedent already exists.** The
     derivation reads the catalogue, and a test must never mutate
     `plugins/tcs-patterns/templates/patterns/` — the `.claude` incident on 2026-10-04 showed how
     loudly a stray entry there breaks unrelated suites, and a mutated real catalogue would be
     worse. So the derivation takes the **catalogue root as a parameter**, defaulting to the real
     one, exactly as `detect(repo_dir)` takes the repository root. The injection test then builds a
     two-pattern tree under `tmp_path`, plants a citation crossing into a target the real catalogue
     has no edge to, and asserts the derived map contains that edge — which a hardcoded table
     cannot produce. Parameterising it is also what makes the ambiguity assertion cheap: a
     `tmp_path` catalogue with the same filename under two patterns is one fixture, not a
     contortion.

     **Expansion is the transitive closure (Marcus, 2026-10-04), and three sources make the depth
     observable** `[ref: SDD/Interface Specifications/Data model: companion map, "Expansion is the
     transitive closure"]`. Assert all three, because a one-level implementation passes the other
     two and the seven-edge map equally:
     - `observability` → `hexagonal`, **`ddd`** (direct would give `hexagonal` alone)
     - `event-driven` → `event-sourcing`, `hexagonal`, **`ddd`**
     - `event-sourcing` → `event-driven`, `hexagonal`, **`ddd`**

     And assert the two that do **not** discriminate, so the closure is not over-applied:
     `ddd` → `hexagonal` only, and `hexagonal` → `ddd` only — a closure that returned the source
     itself, or that walked into `ddd`'s own companions and back, would differ here.

     **The cycle criterion is only falsifiable now that a traversal exists.** Until the closure was
     the rule, step 3 asked for a flat edge map and nothing recursed, so "must not recurse forever"
     could not fail — the same shape as two criteria this phase already discarded. With the closure
     it is real: an unguarded depth-first walk from any of the four patterns in a mutual pair never
     terminates. Test it with a timeout or a recursion-depth guard rather than by inspection, so
     the assertion fails rather than hangs the suite.

     **This step said "the nine measured pairs" three times until 2026-10-04 and then listed the
     seven-edge table beneath it.** Both numbers are real and describe different things, re-measured
     against the catalogue before this correction: **14** raw cross-pattern references, **9**
     distinct (source pattern, cited *path*) pairs, **7** distinct (source, target) *edges*, which
     is what the rows above sum to. Nine collapses to seven because two sources each cite two files
     inside one target. The map is the seven edges — a companion is a pattern to add to a proposal,
     not a path — so that is what the test asserts; the 9 and the 14 are provenance for how the 7
     was found. An implementer reading the old text could have asserted either count and been
     compliant, and AC-18 carried the same ambiguity.
  3. Implement: Derive the map by a **new** resolution rule, reusing only the plumbing named in
     step 1: a code-span path resolving under no pattern root but another's is a companion edge.
     This sentence read "by the link test's resolution rule" until 2026-10-04 — the substance after
     the colon was always right, the attribution never was, and leaving it there meant a reader of
     this step met the false instruction twice before the correction below landed. Expose **two**
     things for C3 to read:
     the seven-edge map itself, and a closure function that takes a set of selected patterns
     and returns the companions to propose. The closure carries a visited set; it excludes
     the selections themselves from its result, so a caller can present "and these come
     with it" without filtering.

     **Read the 2026-10-04 clause "How the citations are actually written, and why the path rule is
     the right one" before writing the derivation**
     `[ref: SDD/Interface Specifications/Data model: companion map]`. The real citation shape is
     not a `../` climb — a derivation written for that shape, which is what the link test's own
     rule keys on, finds **zero edges**, measured. The path is relative to the **target** pattern's
     root and a `tcs-patterns:<name>` marker names the target beside it:

     ```
     ddd/reference/testing-by-layer.md:3
       … see `tcs-patterns:hexagonal` `reference/testing-hex-arch.md`.
     ```

     So: resolve each candidate against **every** pattern root, not against the citing file's
     directory. Treat a path resolving under more than one other pattern as **ambiguous** rather
     than picking one; zero are ambiguous today, which is worth asserting so that the day one
     appears is the day the suite says so. And do **not** derive from the marker: it yields **43**
     edges against the path rule's 7, because a marker means "mentions" while a path means
     "breaks when installed alone", and the second is the defect this map exists to prevent. A
     marker-derived map would add up to six companions to a single-pattern selection and justify
     none of them.
  4. Validate: `python3 -m pytest -q`; confirm the derived map's seven edges against the table in
     the SDD, and that the 9 and the 14 appear nowhere as an assertion -- they are provenance.
  5. Success:
     - [ ] The derived map equals the seven pattern-to-pattern edges, and the derivation is
           keyed on paths resolving under another pattern's root rather than on the
           `tcs-patterns:<name>` marker, which yields 43 `[ref: SDD/Acceptance Criteria/AC-18]`
     - [ ] A cross-pattern reference to a new target fails the test `[ref: SDD/Acceptance Criteria/AC-18]`
     - [ ] No candidate path resolves under more than one other pattern -- zero do today, and
           the assertion is what makes the first one audible `[ref: SDD/Interface Specifications]`
     - [ ] The closure traversal terminates on both mutual pairs, shown by a timeout or a
           recursion-depth guard rather than by inspection -- falsifiable only because the
           closure is now the rule; while step 3 asked for a flat map, nothing recursed and
           this criterion could not fail `[ref: SDD/Interface Specifications]`
     - [ ] The closure equals the direct edges for `ddd` and `hexagonal`, and adds `ddd` for
           `observability`, `event-driven` and `event-sourcing` -- the three cases where
           depth is observable `[ref: SDD/Interface Specifications/Data model: companion map]`

     Moved to T5.1, where the behaviour lives: "nothing is installed by the map alone -- it
     produces a proposal the user can decline" `[ref: ADR-8]`. T2.4 returns data and runs no
     installer, so nothing in its output can observe it; the same reason two of T2.3's
     criteria moved there.

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
  invariant; only `gates` diverged, which is T2.2's placeholder.

  **Re-run after T2.3 (`03d3c31`): zero divergence on all four.** `auto`, `baseline`, `gates`,
  `unrecognised_stack`, `schema`, `must_not_propose` and every evidence and `gate_evidence`
  invariant matched the clauses as written, on trees the detector had never seen. Two results
  worth keeping: q1 fired from a **nested** `pyproject.toml`
  (`services/api/backend/pyproject.toml: dependencies.django`), which is the four-manifest table
  working at depth and which no fixture reaches; and q2's evidence was q1's folded in, which is
  the 2026-10-04 pure-disjunct ruling holding outside the corpus. This is the PRD's top-risk
  mitigation actually discharged rather than asserted -- green fixtures could never have done it,
  because the fixtures are the detector's own test data.

  **Do not promote these four into tracked tests, tempting though the rebuild cost makes it.**
  Three sessions have now rebuilt them, and the tax is the price of the property: a tracked test
  is visible to the next implementer and can be fitted exactly as a fixture can. Held-out means
  held out of the tree, not merely out of `tests/fixtures/`. The specification above is what
  makes them reconstructible; keep it accurate instead.

  **The rule that makes this worth anything:** a divergence is resolved against the SDD, never
  against the fixtures, and never by editing an expectation to match the output.

  - Success: all **26** fixtures green -- the figure read 18 until 2026-10-04, before T2.3 added
    eight gate-coverage cases; count `EXPECTED_CASE_COUNT`, do not inherit the number. All four
    held-out cases matching the written rules with no divergence; detection suite runnable
    standalone; both legs green per leg
    `[ref: SDD/AC-3, AC-4, AC-5, AC-6, AC-14; PRD/Risks and Mitigations]`
