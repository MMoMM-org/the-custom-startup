---
title: "Phase 3: Reading several records"
status: in_progress
version: "1.0"
phase: 3
---

# Phase 3: Reading several records

**Independent of phases 1 and 2.** This phase touches `scripts/observability/*.py` and `tests/*.py`
only; phases 1 and 2 touch `plugins/tcs-helper/skills/observability-setup/` and its bats suite. No
file is written by both, so the two sides can proceed concurrently.

---

## Phase Context

**GATE**: Read all referenced files before starting this phase.

**Specification References**:
- `[ref: SDD/ADR-6]` — the locations config: TOML, `repo_root` plus an optional `homes` list
- `[ref: SDD/ADR-7]` — split by `repo`; union only coverage
- `[ref: SDD/ADR-8]` — the denominator stays one repository's shipped inventory
- `[ref: SDD/Runtime View — Complex Logic]` — how the report splits without lying
- `[ref: PRD/F3]`, `[ref: PRD/F4]`, `[ref: PRD/F5]`

**Key Decisions**:
- **The config stores `repo_root` and an optional `homes` list, never a derived record path.**
  Those are exactly the values `report.py` already accepts, and `_resolve_events_path` already
  derives both location shapes from them — so the config cannot drift from the resolver that
  consumes it. `homes` is a list because one repository worked in both environments has two
  record locations but **one** identity: the writer freezes `repo` from the repository, so two
  config entries would collide on it and leave the renderer an undecided two-to-one mapping.
- **`repo` is the dimension the reader is missing.** Every record carries it, frozen in the writer
  and not caller-settable; `report.py` reads it nowhere today. Adding it is what makes reading
  several records safe rather than merely possible.
- **Merging is not uniformly safe**, and this is the phase where that gets built rather than
  discussed. Recording status and the hook `installed` flag collapse to a single winner across a
  merged stream, so one live source would report the whole set as fresh and hide a source that
  stopped months ago — the exact inversion of spec-018's SDD-AC-15.

**Dependencies**: none from this spec. Depends on spec-018's `report.py` existing, which it does.

---

## Tasks

Delivers a reader that answers the cross-repository question without pretending four repositories
are one.

- [x] **T3.0 Capture the spec-018 output fixture — before anything else** `[activity: test-strategy]`

  **This must happen before T3.1 touches `report.py`.** T3.5 asserts that `--events <path>` behaves
  exactly as it did in spec-018, "against a recorded fixture of the old output rather than by
  inspection". By the time T3.5 runs, T3.1, T3.3 and T3.4 have already changed the reader — there is
  nothing left to record the old behaviour from. A golden fixture captured after the change would
  only prove the new code agrees with itself.

  1. Prime: read `scripts/observability/report.py`'s current rendering path.
  2. Test: none yet — this task produces the baseline the later tests compare against.
  3. Implement: run the current reader over a fixed input and commit its output verbatim as a
     fixture, with a comment naming the commit it was captured from.
  4. Validate: the fixture reproduces byte-identically on a second run of the unmodified reader.
  5. Success: T3.5 has something real to compare against `[ref: SDD/SDD-AC-24]`

  **Deviation, approved by the maintainer 2026-09-10.** Step 2 said "Test: none yet", and the
  byte-diff assertion belonged to T3.5 step 1. It landed here instead, as
  `tests/test_observability_report_t30_golden.py`. Rationale: T3.0 exists to protect T3.1, T3.3
  and T3.4 from silently breaking `--events`, and an assertion that only lands at T3.5 lands
  *after* all three have changed the reader — its implementer would meet accumulated drift across
  three commits with no signal about which change caused what. Wired in now, whoever breaks
  SDD-AC-24 gets a red test at the commit that breaks it. Proven to have teeth before acceptance:
  three mutations of `report.py`'s rendered output (a section label, `never_loaded`'s sort order,
  an off-by-one in the unreachable count) each failed the test. Spec compliance had ruled this
  scope creep and was correct to; the ruling is the maintainer's, not the implementer's.

- [x] **T3.1 `repo` as a first-class dimension in the existing analyses** `[activity: backend-api]`

  1. Prime: read `scripts/observability/report.py` — `instruction_stats:151`, `_redact_path:453`,
     `recording_status:412`, `hook_duration_stats:1183` `[ref: SDD/Runtime View — Complex Logic]`.
  2. Test: over a fixture holding records from two repositories, instruction statistics key on
     `(repo, path)` so a file of the same name in both is counted twice, not once — **this is the
     defect the naive merge produces, so it is the first test written**; per-repository counts sum
     to the per-file totals; a record with an empty `repo` is attributed to an "unknown" bucket
     rather than silently joining another repository's.
  3. Implement: thread `repo` through the analyses that need it. No rendering yet.
  4. Validate: `pytest -q` green; existing single-record tests unchanged and still passing.
  5. Success: `[ref: SDD/SDD-AC-19]`; `[ref: SDD/ADR-7]`

- [x] **T3.2 The locations config and its reader** `[activity: backend-api]`

  1. Prime: read ADR-6 and `_resolve_events_path:1603-1614`, which the reader must feed rather than
     duplicate `[ref: SDD/ADR-6]` `[ref: PRD/F3]`.
  2. Test: a config with a container source (`homes` given) and a host source (none) resolves both
     record paths correctly; **a single source carrying two homes resolves both its record
     locations, merges them into one section under one label, and takes its instruction inventory
     as the **union of both homes' trees** — a file present in only one home still appears in the
     denominator, because a primary-home rule would have dropped it with nothing to show it was
     gone —
     the case a completeness audit found the PRD promised and the first schema could not express; a source whose record does not exist yet is reported as *not yet
     recording*, distinct from a source whose path is gone entirely, which is reported as *missing*;
     an absent config file is not an error — the report falls back to single-record behaviour; a
     malformed config is an error naming the line; duplicate labels are rejected, since a label is
     how a human tells two sources apart; the config is confirmed gitignored by a test, because that
     property is a requirement rather than a convenience.
  3. Implement: `scripts/observability/sources.py`, and the example config documented in the SDD.
  4. Validate: `pytest -q` green; **assert `sources.py` imports nothing outside the standard
     library** — CON-3 is otherwise honoured by intention only, and a future `import tomli` or
     `import yaml` would pass every other gate in this plan.
  5. Success: `[ref: SDD/SDD-AC-16, SDD-AC-17, SDD-AC-18, SDD-AC-25]`; `[ref: PRD/F3]`;
     `[ref: SDD/Constraints — CON-3]`

  **Three rulings, 2026-09-10, after the TDD gate blocked on genuine gaps.**

  **(a) A two-home source reports one verdict plus per-home sub-lines** *(maintainer ruling — the
  plan and the SDD were both silent, and SDD-AC-25 is one of this task's own success criteria).*
  SDD-AC-25 requires one section under one label, but each home is independently *missing*, *not
  yet recording* or *recording*, and no rule said how to combine two into one. The section's
  headline is **recording if any home is recording** — there is real data, and the two streams
  merge exactly as `read_events` already merges a rotation chain, one level up — and each home's
  own state is listed beneath it:

  ```
  repo3 -- recording
    container home: recording (newest 2026-09-10T08:12Z)
    host home:      missing (path no longer exists)
  ```

  A single combined verdict with no sub-lines was rejected: a source whose second home died months
  ago would look identical to a healthy one, which is the collapse ADR-7 exists to prevent, at
  per-home scale. This mirrors the reasoning already recorded for the inventory union — a
  primary-home rule "would have dropped it with nothing to show it was gone".

  **(b) "An error naming the line" applies to TOML syntax errors only.** `tomllib` reports a
  position while parsing and nothing afterwards, so once a document parses into a plain dict there
  is no line to name. A *schema* violation — a `[[source]]` missing `repo_root`, a `homes` given as
  a string, an unknown key, a duplicate label — therefore cannot name a line without a
  span-preserving parser, and pulling one in would violate CON-3. Two error classes: syntax errors
  name the line; schema errors name the source, e.g. `source #2 (label='repo3'): homes must be a
  list, got str`.

  **The line number must NOT be read from `TOMLDecodeError.lineno`.** Measured on both
  interpreters: `lineno`/`colno`/`msg` exist on Python 3.14.3 (local) and do **not** exist on
  3.11.14, where the position survives only inside `str(e)` ("Invalid value (at line 2, column
  13)"). CI runs 3.11 on both ubuntu and macos (`.github/workflows/tests.yml:61-72`), so an
  implementation reading `e.lineno` passes locally and raises `AttributeError` in CI.

  **The line number comes from the message text only — the native attribute is deliberately not
  read at all.** The obvious remedy, `getattr(e, "lineno", None)` with a message fallback, is also
  wrong, and hides the same failure inside the fix for it. Measured on both interpreters against
  `'[[source]]\nlabel = '` (an error at end of document): `getattr` yields **2** on 3.14 and no
  attribute at all on 3.11, while the message yields `None` on both. A test asserting a line for
  that fixture would pass locally and fail in CI. Every message string, by contrast, is
  byte-identical across 3.11.14 and 3.14.3 — verified over four malformed documents — so
  `re.search(r"at line (\d+)", str(e))` is the one path that cannot diverge. `None` is a legitimate
  result on **both** versions, meaning the position could not be determined; the error must then
  read as position-unknown rather than formatting `None` into "at line None". `sources.py` raises
  its own error type carrying `lineno: int | None`, and the tests assert against that contract —
  never against `tomllib`'s version-dependent surface. A test for the end-of-document case
  asserting `lineno is None` is what keeps this ruling enforced, since that is the single input
  where the two designs disagree.

  **(c) T3.2 does not touch `report.py`.** Step 3's deliverables are `sources.py` and the example
  config. `sources.py` stays pure: it parses the config into sources carrying `repo_root` and
  `homes`, classifies each home's state from the filesystem, and imports **nothing local** — not
  even `report`. `_resolve_events_path` stays private to `report.py`; the caller feeds it, which is
  what step 1's "feed rather than duplicate" means. That also keeps the CON-3 import test's
  allowlist exactly `sys.stdlib_module_names` with no local-module exception, and keeps the T3.0
  golden fixture green trivially. **Wiring the config into `main()` is T3.3's**, which is the first
  task that actually needs several sources read; step 2's "the report falls back to single-record
  behaviour" is exercised here as a `sources.py` contract (an absent config yields no sources, not
  an error) and rendered there.

  **(d) SDD-AC-25 is jointly owned, and the plan said otherwise.** The criterion has two halves:
  records from both homes merged into one section under one label, and the instruction inventory
  taken as the union of both homes' trees. T3.2 delivers the *data* for both — `Source.homes` is an
  ordered list of per-home states, which is everything a caller needs — but it cannot perform
  either merge itself: `walk_instruction_inventory` and `_resolve_events_path` both live in
  `report.py`, which ruling (c) bars this task from importing. Both halves therefore land in T3.3,
  whose text and Success line have been amended to say so. Caught by review before T3.3 began: the
  coverage map assigned AC-25 to T3.2 alone and T3.3's Success line did not cite it at all, so the
  union walk was assigned to the task that could not do it and absent from the one that could. Left
  alone, T3.3 would have walked one home per source, every test would have passed, and a file
  present only in the other home would have vanished from the denominator — a wrong number that
  looks right.

  **(e) One verdict combination the ruling did not name.** `Source.verdict` resolves
  `missing` + `not_yet_recording` to **not yet recording**, on the reading that a configured but
  silent home is more informative than a dead one. Reasonable, and previously written down
  nowhere; recorded here so it is a decision rather than an accident.

- [ ] **T3.3 Per-source rendering, and the honesty rules** `[activity: backend-api]`

  1. Prime: re-read why merging is misleading for two specific analyses `[ref: SDD/ADR-7]`
     `[ref: SDD/Runtime View — Complex Logic]`.
  2. Test: with one source recording now and one whose newest record is months old, each source's
     recording state is reported separately and the stale one is named — **the merged form of this
     test must fail before the split is implemented**, so write it against the merged behaviour
     first and watch it report everything as fresh; the never-loaded list is a per-source difference
     against that source's own inventory walk, never against a pooled set; **for a source with
     several homes that walk is the UNION of every home's tree, walked from the one `repo_root`
     (SDD-AC-25, CON-6)** — `walk_instruction_inventory(repo_root, home_dir)` takes a single home,
     so it must be called once per entry in `source.homes` and the results combined; a file present
     in only one home must still appear in the denominator, or it shows up as neither loaded nor
     never-loaded and vanishes with nothing to say it was gone, which is precisely the failure the
     SDD says a primary-home rule causes; byte accounting is reported per source.
  3. Implement: per-source sections in the renderer.
  4. Validate: `pytest -q` green.
  5. Success: `[ref: SDD/SDD-AC-20]`; `[ref: SDD/SDD-AC-25]` (the inventory-union half — T3.2 delivers the per-home data, this task performs the walk); `[ref: SDD/ADR-7]`

  **Rulings, 2026-09-10, after the TDD gate blocked.**

  **(f) A section is looked up by `repo_root.name` and headed by `label`.** Nothing said how a
  per-source section finds its own entry in `instruction_stats_by_repo`, and the two candidates are
  not interchangeable: the outer key is the record's own `repo` field, which `logwrite.sh` freezes
  as the git toplevel's **basename** (`:328-329,339-347`), while `Source.label` is free text a human
  chose. The SDD's own example config uses `label = "repo3"` for a `repo_root` whose basename could
  be anything. So: look up `stats_by_repo.get(source.repo_root.name, {})`, render under
  `source.label`. Not a design choice — the label is display-only and the basename is the only key
  the data actually carries. **The plan lacked the test that would catch getting this wrong**: a
  source whose `label` differs from its `repo_root.name`, asserting the section is headed by the
  label and populated from the basename key. Without it every specified test passes either way.

  **(g) Two sources whose `repo_root` basenames collide are rejected at config load** *(maintainer
  ruling; reopens T3.2 for a follow-up).* `_record_base_path` derives the data directory from
  `repo_root.name` alone, and `logwrite.sh` freezes `repo` to the same basename — so `~/work/tcs`
  and `~/archive/tcs` resolve to the **same record file**, carry the **identical `repo` value**, and
  cannot be told apart even in principle. They would render as two sections with identical content
  under different labels: two plausible, wrong repositories, which is the dishonesty ADR-7 exists to
  prevent. `sources.py` already rejects duplicate labels; it now rejects duplicate basenames the
  same way, naming both offending sources. Failing loudly at load beats a silent duplicate in the
  report.

  **(h) `--events` keeps the golden green because the mode branch lives in `main()`.** The SDD is
  explicit that "`--events` continues to mean 'this one record', so every existing invocation keeps
  working" (`solution.md:333-334`) — it is a mode selector, and when given, the config is never
  consulted. So `main()` branches: `--events` takes today's block unchanged; otherwise load
  `args.repo_root/.claude/observability-sources.toml` and loop. `build_load_report` gains one more
  optional `None`-default keyword (a section title), exactly the precedent every prior extension
  used, and never branches on how many sources exist. The golden test never executes the new branch,
  so it stays green trivially. **No deviation, and no reason to regenerate the golden — if it goes
  red, something is wrong with the change, not with the fixture.** An absent config and a config
  with zero sources both fall back to the single-record path identically; there is no third case.

  **(i) The inventory union: `entries` unions, `git_filtered` ANDs.** `InstructionInventory` has
  exactly two fields. `entries` is a plain set union — safe by construction, because
  `walk_instruction_inventory` already redacts to strings and is documented to over-list rather than
  under-list, so unioning is the same collapse it already performs internally, one level up.
  `git_filtered` combines with **AND**: both walks share a `repo_root` so they should always agree,
  but if they ever disagree, reporting the *less* confident state is honest and `or` would overclaim
  filtering the other home never achieved.

  **(j) Within a source, concatenate; across sources, never.** Each home's stream is read with
  `read_events`, which is safe on a path that does not exist (`rotation_chain` returns `[]`), so a
  *missing* or *not yet recording* home needs no special case. The homes' streams concatenate for
  that one source — it is one repository, and `newest_ts` taking a max is exactly why that is
  honest, the rotated-chain merge one level up. Concatenating two different sources is the ADR-7
  collapse and is forbidden.

  **(k) Scope: leave T3.4 its work.** Every per-source `build_load_report` call this task writes
  passes `skill_agent_inventory=None`, `firing=None`, `hooks=None`. The firing-coverage union
  (ADR-8) and the per-source hook-timing split are T3.4's, and this leaves them clean insertion
  points — the union appended after the per-source loop, not inside it.

- [ ] **T3.4 The one union: firing coverage across sources** `[activity: backend-api]`

  1. Prime: read `walk_skill_agent_inventory:857-922` and `fired_names:927`, and ADR-8 on why the
     denominator must not be globbed across sources `[ref: SDD/ADR-8]` `[ref: PRD/F4]`.
  2. Test: numerators union across sources while the denominator stays this repository's shipped
     inventory; a skill that fired in one source and not another appears in both the union figure
     *and* the per-source detail, because "fired somewhere" and "fired in both places it should" are
     different questions and the PRD asks the second; a target's own local agents do **not** enter
     the denominator; a record naming something outside the inventory is reported as unrecognised
     rather than dropped; hook timing's `installed` is per source, so a wrapper installed in one
     source does not present timing as available for the others.
  3. Implement: the union figure and the per-source coverage detail beside it.
  4. Validate: `pytest -q` green.
  5. Success: `[ref: SDD/SDD-AC-21, SDD-AC-22, SDD-AC-23]`; `[ref: PRD/F4]`

- [ ] **T3.5 Backwards compatibility and phase validation** `[activity: validate]`

  1. Test: `--events <path>` behaves exactly as it did in spec-018 — same output for the same input,
     asserted against a recorded fixture of the old output rather than by inspection **(already
     delivered by T3.0 as `tests/test_observability_report_t30_golden.py`, by approved deviation —
     verify it is still green and still frozen against commit `eb9b529`; do NOT regenerate the
     golden to make it pass)**; no argument reads the config; `--data-dir` still means what it
     meant. The last two assertions remain T3.5's to write.
  2. Validate: run `pytest -q` in full. Every spec-018 report test must still pass unmodified; if one
     needs changing, that is a deviation and is recorded rather than absorbed.
  3. **Optional scope, PRD F6 (Could-have)**: assisted discovery. If implemented, a discovered
     location is *proposed* and never added silently. The three test-fixture record directories on
     this machine are the standing argument for that rule — a discovery pass would have offered them
     as repositories, and they look entirely plausible.
  4. Success: `[ref: SDD/SDD-AC-24]`

---

## Phase Acceptance Criteria

- The report reads several records, splits every per-repository analysis by `repo`, and unions
  exactly one figure.
- Every spec-018 report test passes unmodified.
- No analysis presents a merged value where the SDD says merging is misleading.
