---
title: "Phase 5: The skills, the docs, end to end"
status: in_progress
version: "1.0"
phase: 5
---

# Phase 5: The skills, the docs, end to end

## Phase Context

**GATE**: Read all referenced files before starting this phase.

**Specification References**:
- `[ref: SDD/Interface Specifications/Process contract: the skills]` — the four verbs and the
  catalogue reader's argument
- `[ref: SDD/Interface Specifications/Process contract: the CLI the skill drives]` — the one
  entry point the skill runs, with `remove` and `status`; T5.1a builds it (added 2026-10-06)
- `[ref: SDD/Runtime View/Primary Flow]` — all nine steps, which this phase finally joins up
- `[ref: SDD/Cross-Cutting Concepts/User Interface & UX]` — three screens at most, costs shown per
  entry at the moment of choosing
- `[ref: SDD/Runtime View/Error Handling]` — the rows owned by the interview: not a git repository,
  partially unreadable target
- `[ref: PRD/F2 4th, F3, F4 3rd-4th]` and `[ref: PRD/F10]`
- `[ref: SDD/Risks and Technical Debt/Known Technical Issues]` — the `principles.md:167` correction

**Key Decisions**:
- **The skill owns the interview; the CLI owns every library call** (2026-10-06). A `SKILL.md`
  cannot import Python, so without `lib/cli.py` its only route to the library would be untested
  inline code.
- **The interview asks only what the gates opened** and presents costs per entry. The UX bar is
  `claude init`, not an interview; the gates are what enforce it.
- **The catalogue reader is one skill serving 21 bodies.** It is justified against the granularity
  rules in `docs/about/skill-and-agent-design.md` because the alternative is 21 descriptions in
  every session's listing, which is the problem this spec exists to remove.
- **Both changelogs, or the pull request fails.** `docs-sync` requires a root `CHANGELOG.md`
  entry for user-facing change; a previous spec lost a push to exactly this. It is a **pull
  request** gate -- `if: github.event_name == 'pull_request'`, and `push` triggers only on
  `main` -- so pushing a feature branch runs no legs at all and cannot tell you anything.
  Measured on 2026-10-03 after Phase 1: `docs-sync` already **fails** on this branch, because
  the relocated pattern files are user-facing and no changelog entry exists yet. That failure
  is expected and is this task's to clear -- do not read it as a regression if a pull request
  is opened before T5.4 lands. Run `check-docs-sync.sh` locally rather than waiting for CI,
  and note it wants a file path or `-`, never a space-separated list.

**Dependencies**:
- Phases 1-4 all complete. The interview needs detection and installation; the end-to-end test
  needs the advisory too.

---

## Tasks

Delivers the user-facing surface and the proof that the nine steps work as one flow rather than as
four passing test suites.

- [x] **T5.1a The CLI the skill drives, with remove and status** `[activity: backend-api]`

  Added 2026-10-06 by Marcus, before T5.1 was dispatched. The skill contract has four verbs, but
  the library had code for two of them, and a Markdown skill had no way to call a Python module.
  T5.1 as written would have had to put `remove` and `status` into Markdown prose, or into inline
  `python3 -c` calls with nothing testing them. Everything this task builds is specified in
  `[ref: SDD/Interface Specifications/Process contract: the CLI the skill drives]`. Read it
  before anything else: every point it settles that neither the code nor the earlier spec did is
  marked "decided here", with its reason.

  1. Prime: Read the CLI contract in full, the Error Handling rows dated 2026-10-06
     `[ref: SDD/Runtime View/Error Handling]`, the install plan's decisions 3 and 6 and the update
     path's decisions 2, 3 and 8 `[ref: SDD/Interface Specifications/Data model: the install plan
     and report (C5); Data model: the update path (C5's second verb)]`, and the drift reporter's
     contract `[ref: SDD/Interface Specifications/Process contract: drift reporter (C7)]`. Read
     `lib/install.py` (`_stash_path`, `_replace_subtree` — the move-aside-and-roll-back shape
     `remove()` mirrors), `lib/manifest.py` (`upsert`, `with_pattern` — the shape `drop` and
     `without_pattern` mirror), `lib/companions.py` (`_derive`), and `scripts/patterns_drift.py`
     with `tests/test_patterns_drift.py`, whose existing tests must stay green **unmodified**
     through the refactor; T5.1a adds one test to it and changes none. `tests/test_patterns_installer.py` shows this repository's loader conventions:
     import inside each test, never at module level.
  2. Test: Written first, failing for want of the code, and the RED commit says which tests fail
     on `ImportError`/`AttributeError` (the module or function is absent) and which on an
     assertion (the behaviour is wrong). Only the second kind proves a defect, the same lesson
     T3.2b recorded.
     - **`remove()`**, `tests/test_patterns_remove_status.py`: each of the six rules in its table,
       one test per rule, each asserting a digest of `.claude/skills/` **and** the manifest bytes
       are unchanged for a refused pattern. Three tests the rest depend on: a hand-made
       `tcs-foo/` the manifest does not list survives `remove(…, ["foo"])` byte-for-byte; a
       pattern whose installed `SKILL.md` was edited is refused without `force`, removed with it;
       an edit confined to `reference/` is removed without `force` (ADR-4's stated limit, pinned
       so nobody "fixes" it by accident). **Two** diverged patterns with only one named in
       `force`: that one is removed and the other refused, which is what kills a blanket-flag
       `force`. A `.replaced` stash beside a present directory is deleted with it; with the
       directory absent it is refused and the reason names the stash. An `OSError` injected
       in step 2 after a partial delete of the stash reports `failed`, leaves `tcs-<p>/` present
       and the manifest bytes unchanged, and never reaches step 3 (no `.removing`). A fault
       injected right after the move-aside (step 3), with a stash present at the start, leaves no
       entry `status` classifies as `replaced`. Order, from both sides:
       a fault injected into `manifest.drop` leaves `<installed_as>/` back in place,
       byte-identical, and reports `failed`; a fault injected into the move-aside rename
       (`os.rename`) leaves the manifest bytes unchanged and the directory intact, and reports
       `failed` — only this second test can see the manifest written before the rename. On the
       resume path, a fault in `manifest.drop` renames nothing back: spies on `os.rename` and
       `os.replace` record **zero** calls, on either, after the fault, and the `failed` reason contains the injected exception's
       text. The spy is what kills the mutant even if the rename-back sits inside an `OSError`
       handler, which "rolled back where possible" invites. Interrupted states, built by
       hand: (a) entry listed, directory absent, `.removing` present — a re-run removes the entry
       and the debris, `directory_existed: false`; (b) `.removing` alone, entry gone — a re-run is
       **refused** by rule 1 and deletes nothing, and `status` reports the entry as `removing`
       debris whose resolution says it is safe to delete; (c) interrupted after step 4, then
       `install p` — `status` classifies the `.removing` as safe to delete and does not advise
       `remove`. Removing the last pattern leaves a manifest
       that `manifest.read` returns with `patterns == {}` and for which `patterns_drift.py` prints
       `OK`. A second pattern's manifest block is byte-identical before and after removing the
       first.
     - **`status()`**, same file: a **hand-typed** table of (installed version, catalogue state)
       → expected verdict, covering behind, equal, ahead, `01` against `1`, `VERSION` absent,
       non-numeric, empty, and the pattern directory deleted. Each row is asserted against
       **both** `status()`'s `state` and `patterns_drift.py`'s stdout line for the same fixture.
       The expected column comes from neither implementation, so the test is not one that shares
       the logic it checks, even though the two now share `drift_verdict`. Also: `unparseable`
       and `unreadable` manifests report `manifest_state` and the exception text verbatim (the
       mode-000 case skips when `os.geteuid() == 0`, where permissions do not bite); `unlisted`
       names a `tcs-*` directory the manifest does not; `debris` classifies `.tcs-ddd.tmp`,
       `.tcs-ddd.removing`, `.tcs-ddd.replaced` (once with `tcs-ddd/` present, once absent — two
       different resolutions) and a `..tcs-patterns-manifest.x.tmp` file, and does **not** list
       `.tcs-patterns-manifest`; `diverged` is `None`, not `False`, when `SKILL.md` is absent.
       `status()` writes nothing: digest before and after, and the SDD's `ast` **allowlist** —
       sibling imports only `import manifest` and `import paths`, no alias and no `from` form,
       and `manifest.<attr>` only for `read`, `_manifest_path`, `ManifestUnparseableError`,
       `MANIFEST_FILENAME`, `Manifest` and `PatternEntry`. The test fails on anything else rather
       than looking for named writers; `getattr`/`importlib` bypasses are out of scope.
     - **The reporter's lazy import**, in `tests/test_patterns_drift.py` as a **new** test (the
       existing ones stay unmodified): a copy of the plugin with `lib/manifest.py` present and
       `lib/status.py` absent — the partial lib the refactor creates a new way to have — run as a
       subprocess, exits 0 with empty stdout and one `patterns_drift:` line on stderr that names
       `status`. The repository fixture **must
       hold a manifest listing at least one pattern**: without one, `drift_lines` returns
       `MISSING` before it reaches the lazy `import status`, and the test passes without
       exercising the import it exists for. It also asserts stdout is not `MISSING`.
     - **The CLI**, `tests/test_patterns_cli.py`, every verb run as a **subprocess** of
       `python3 <abs path>/lib/cli.py` from a cwd that is not the repository, with `HOME`
       pointed at a `tmp_path` and `--catalogue` at a fixture catalogue unless a bullet says
       otherwise. Fixture repos are created with `git -C <tmpdir> init` and
       `GIT_CONFIG_GLOBAL=/dev/null`: the hazard is initialising in the wrong working directory,
       and `-C` removes the dependence on cwd. Asserted:
       - Every verb's stdout on exit 0 parses as **one** JSON document whose top-level key set
         **equals** the contract's table for that verb — `==`, not `>=`, so an extra key fails
         too — and every nested channel has its named fields.
       - Outside a git repository, with `GIT_CEILING_DIRECTORIES` set so the test cannot pass by
         accident inside one, every verb exits **3** with empty stdout. An in-process run of
         `cli.main()` with `detect.detect`, `manifest.read`, `status.status`, `install.install`,
         `install.update` and `install.remove` monkeypatched to raise proves none of them was
         reached.
       - `update` with no `--accept` on a diverged pattern exits 0, lists it under `declined`
         with a diff whose `---` label is `installed`, and leaves its `SKILL.md` **byte-identical**.
         The same run refreshes a merely-behind pattern. A second run with `--accept <it>`
         refreshes it. `--accept` naming an unlisted pattern exits 3 and writes nothing.
       - `install` installs only what the guard cleared. A name colliding in the user namespace
         under `HOME` appears under `refused` with both `path` and `intended_path`, and its
         sibling still installs (F5). Companions are not added: installing `ddd` alone does not
         write `tcs-hexagonal`. An unparseable manifest exits 3 and its bytes are unchanged.
       - `scan` without `--answers` has `outcomes: null`. With `--answers`, the four sets are
         disjoint and sum to 21. An answer naming a closed gate, or a pattern its gate does not
         settle, exits 2. Against the fixture catalogue, `listing_cost`'s keys equal that
         catalogue's pattern directories, and one hand-computed entry matches. Each companion
         under `proposed` carries at least one citation for which `<catalogue>/<source_file>` is
         a file — `source_file` is catalogue-relative.
       - **One real-catalogue test, named as such:** `scan --catalogue` omitted, `listing_cost`
         has 21 keys and sums to **5990**, measured 2026-10-06. Its docstring says it is expected
         to change whenever a pattern description changes, and the figure is updated in the same
         commit. Kept out of every fixture test.
       - A non-ASCII value round-trips under `PYTHONIOENCODING=ascii`: exit 0, and stdout's bytes
         decode as UTF-8 and contain the character itself, not a `\u` escape. `LC_ALL=C` cannot
         show this — on Python 3.7+ it switches to UTF-8 mode (PEP 538/540; measured on 3.14:
         `sys.stdout.encoding` is `utf-8`), while `PYTHONIOENCODING=ascii` makes a text-stream
         write raise. This test kills the mutant that writes to `sys.stdout` instead of
         `sys.stdout.buffer`; the `\u` check kills the one that drops `ensure_ascii=False`.
     - **`detect.py`'s `unreadable`**, in `tests/test_patterns_detect.py`: a mode-000
       subdirectory and a mode-000 `package.json` both appear, root-relative and sorted, the
       directory with a trailing `/`. A non-UTF-8 manifest does **not** appear. Every corpus
       fixture reports `[]`. Skipped under `geteuid() == 0`, like the `status` permissions test.
       The hand-built control reports in that file (`report_with` and `base_report`, near lines
       447 and 509) gain `"unreadable": []`, so the controls keep describing a whole report.
     - **`companion_citations()`**, in `tests/test_tcs_patterns_companion_map.py`: its outer two
       key levels equal `companion_map()`'s edges on the real catalogue, and on a two-pattern
       `tmp_path` catalogue it names the citing file and line.
  3. Implement: `lib/cli.py` (NEW); `lib/paths.py` (NEW leaf: plugin root, catalogue default,
     the three debris suffixes, `sha256_or_none` moved from `install._hash_if_present`);
     `lib/status.py` (NEW: `status()`, `StatusReport`, `PatternStatus`, `Debris`,
     `drift_verdict()`, `catalogue_version()`); `remove()` and `RemoveReport` in
     `lib/install.py`, which also takes its root and suffixes from `paths`; `companions.py`
     takes its catalogue default from `paths`; `drop()` and `Manifest.without_pattern()` in
     `lib/manifest.py`; `unreadable` in `lib/detect.py`; `companion_citations()` and `Citation`
     in `lib/companions.py`. In `scripts/patterns_drift.py`, **extract** the rule: today it has
     `_catalogue_version` and an integer comparison inline in `drift_lines`, not a function.
     Move the first to `status.catalogue_version` unchanged and the second into
     `status.drift_verdict`, then import both lazily inside `drift_lines`. No other behaviour of
     the reporter changes, and it keeps its own `parents[1]` derivation.
  4. Validate: `python3 -m pytest tests/test_patterns_remove_status.py tests/test_patterns_cli.py
     tests/test_patterns_drift.py -q`, then the whole suite. Report each leg separately, and
     compare against a same-harness baseline taken before the change. Delete `__pycache__`
     before each mutation run. At minimum, mutate:
     - drop rule 1, so a pattern the manifest does not list is deleted (must fail the unowned
       test);
     - make `force` a blanket flag rather than per-name (must fail the two-diverged test);
     - swap `remove()`'s rename and manifest steps (must fail the rename-fault test);
     - make the rename-back on a `manifest.drop` failure unconditional (must fail the resume-path test);
     - refuse on any `.replaced` stash, present directory or not (must fail the "stash beside a
       present directory is deleted with it" test);
     - delete the stash after the manifest write instead of first (must fail the fault-after-step-3
       test, which finds an entry `status` classifies as `replaced`);
     - continue after a step-2 failure (must fail the step-2 `OSError` test);
     - make `status.py` reference `manifest.write` (must fail the `ast` allowlist test);
     - hoist `import status` to module level in `patterns_drift.py` (must fail the partial-lib
       test);
     - write to `sys.stdout` instead of `sys.stdout.buffer` (must fail the `PYTHONIOENCODING=ascii` test);
     - delete the manifest on the last remove;
     - make `drift_verdict` compare strings (must fail both the `status` and the reporter rows);
     - make the CLI's `decide` accept everything;
     - resolve the repository after calling `detect`;
     - drop `ensure_ascii=False`.
     Then walk `scan`, `install`, `status`, `update` and `remove` by hand against a fixture
     repository and read each JSON document. Green tests over this boundary are not the
     walkthrough T5.1 depends on.
  5. Success:
     - [x] `remove` never deletes a directory the manifest does not own `[ref: SDD/Process contract: the CLI the skill drives, remove rule 1]`
     - [x] `remove` refuses a diverged pattern unless forced by name `[ref: SDD/ADR-4; SDD/Error Handling]`
     - [x] Interrupted after the move-aside (entry listed, directory absent), a re-run of `remove` completes; interrupted after the manifest write (`.removing` alone), a re-run is refused and `status` reports the leftover as safe-to-delete debris `[ref: SDD/Process contract: the CLI the skill drives, "Order"]`
     - [x] `status` agrees with `patterns_drift.py` on every row of a hand-typed verdict table `[ref: SDD/AC-11]`
     - [x] `status` reports an unparseable manifest verbatim, exit 0 `[ref: SDD/Error Handling, "Manifest present but unparseable"]`
     - [x] `update` without `--accept` leaves every diverged file byte-identical `[ref: PRD/F8; SDD/AC-12; ADR-4]`
     - [x] Every verb's JSON parses and has exactly the specified keys `[ref: SDD/Process contract: the CLI the skill drives]`
     - [x] Outside a git repository every verb exits 3 before reading anything `[ref: SDD/Runtime View/Primary Flow, step 1; SDD/Error Handling]`
     - [x] `scan` reports per-entry listing cost and what it could not read `[ref: PRD/F2 4th; SDD/AC-16; SDD/Error Handling, "Target repository unreadable in part"]`
     - [x] `tests/test_patterns_drift.py`: existing tests unmodified and passing; one test added `[ref: SDD/AC-11]`

- [ ] **T5.1 The patterns-setup skill** `[activity: frontend-ui]`

  1. Prime: Read the skill contract
     `[ref: SDD/Interface Specifications/Process contract: the skills]`, **the CLI it drives**
     `[ref: SDD/Interface Specifications/Process contract: the CLI the skill drives]`, the full flow
     `[ref: SDD/Runtime View/Primary Flow]`, and the UX section
     `[ref: SDD/Cross-Cutting Concepts/User Interface & UX]`. Read
     `plugins/tcs-helper/skills/observability-setup/SKILL.md` for the verb-and-abort shape; note
     that its stance on committability is the opposite of ours and why. **Amended 2026-10-06 with
     T5.1a:** the skill owns the interview and nothing else. Every read and write of the target
     goes through `lib/cli.py`. The skill treats each exit code exactly as the SDD's exit-code
     table says (the one authority; not restated here), and it never imports, inlines or
     re-derives library logic.
  2. Test: The frontmatter parses with a YAML parser — a clause ending in `: ` inside a value makes
     YAML read it as a key, which broke ten descriptions in this repository while
     `claude plugin validate` passed over all ten; the description names the situation the skill is
     for and the neighbouring skills it is not; all four verbs are documented with their arguments;
     outside a git repository the skill aborts before reading the target; a partially unreadable
     target reports what it could not read so a thin proposal is never silently a permissions
     artefact.
  3. Implement: `plugins/tcs-patterns/skills/patterns-setup/SKILL.md` — persona, interface, the
     four verbs, the gated questions with their exact option lists, the proposal format including
     per-entry listing cost, and the commit offer. `user-invocable: true`,
     `argument-hint: "<install|update|remove|status> [path]"`. Each verb is a sequence of CLI calls
     (amended 2026-10-06):
     - `install`: `scan`, ask the open gates, `scan --answers`, confirm, offering each companion
       with its citation, then `install` with the confirmed names.
     - `update`: `update`, show each `declined` diff, ask, then `update --accept` for each one
       approved.
     - `remove`: `remove`. On a `refused` divergence, ask, then `remove --force`.
     - `status`: `status`.

     `[path]` defaults to the session's working directory, and the skill passes it as `<repo>`.
     The CLI resolves the toplevel.
  4. Validate: `python3 -m pytest -q`; `claude plugin validate plugins/tcs-patterns` as a smoke
     test; walk the skill by hand against a fixture repository — green tests over skill Markdown
     have missed defects here before that a walkthrough found at step one.
  5. Success:
     - [ ] No more than three questions in total, each allowing multiple answers — moved here
           from T2.3 on 2026-10-04, where it had been transcribed as "never more than three
           gates open" and could not fail: there are exactly three gate keys and the corpus
           guard enforces them. The falsifiable form is about questions, which only this task
           asks `[ref: PRD/F3 2nd]`
     - [ ] A question whose gate is closed is skipped entirely, never asked and answered
           "none" — also moved from T2.3, which builds gates in `detect.py` and asks nothing
           `[ref: PRD/F3 3rd]`
     - [ ] Frontmatter parses; description is a routing contract `[ref: SDD/Quality Requirements]`
     - [ ] Proposal shows per-entry listing cost; baseline listed separately from recommendations `[ref: PRD/F2 4th, 5th; SDD/AC-16]`
     - [ ] The outcome report distinguishes **not reached** from **excluded by stack fact**,
           because they explain differently: "`typescript-strict` does not apply, no
           `tsconfig.json` anywhere" is about the repository, while "you were not asked about
           DDD, because nothing indicated a backend service" is about the detection -- and a
           user who disagrees with the second must be able to see it and say so. Added
           2026-10-04 with the fourth outcome set `[ref: SDD/AC-6; SDD/Runtime View/Complex
           Logic, "There are four outcomes, not three"]`
     - [ ] Commit is offered and never performed unasked `[ref: PRD/F4 3rd, 4th; SDD/ADR-8]`
     - [ ] A walkthrough from a clean fixture reaches an installed selection `[ref: SDD/Runtime View/Primary Flow]`
     - [ ] Nothing is installed by the companion map alone: a selection's transitive companions
           join the **proposal**, each with the citation that justified it named, and every one is
           individually declinable. Moved here from T2.4 on 2026-10-04 — that task derives the map
           and runs no installer, so nothing in its output could observe this, the same reason the
           two criteria above moved from T2.3 `[ref: ADR-8; SDD/Interface Specifications/Data
           model: companion map]`
     - [ ] A declined intermediate companion is handled honestly: accepting `hexagonal` for
           `observability` while declining `ddd` still ships a dangling citation, and the closure
           informs rather than guarantees. The proposal must not claim every citation will resolve
           `[ref: SDD/Interface Specifications/Data model: companion map, "Expansion is the
           transitive closure"]`

- [ ] **T5.2 The catalogue reader skill** `[activity: frontend-ui]` `[parallel: true]`

  1. Prime: Read the reader's contract
     `[ref: SDD/Interface Specifications/Process contract: the skills]` and F10's criteria
     `[ref: PRD/F10]`.
  2. Test: A named pattern's full body is returned and **nothing** is written to the repository; an
     unknown name lists the 21 available rather than returning empty; the frontmatter parses.
  3. Implement: `plugins/tcs-patterns/skills/pattern/SKILL.md`, `argument-hint: "<pattern-name>"`.
  4. Validate: `python3 -m pytest -q`; invoke it for a pattern and confirm the repository is
     untouched afterwards.
  5. Success:
     - [ ] Body served, nothing written `[ref: PRD/F10 1st; SDD/AC-15]`
     - [ ] Unknown name lists the 21 `[ref: PRD/F10 2nd]`

- [ ] **T5.3 Documentation** `[activity: technical-writing]` `[parallel: true]`

  1. Prime: Read `docs/about/principles.md:167`, which states that plugin skills do not support
     `disable-model-invocation`. Measured false: the flag removes a plugin skill's entry from the
     listing entirely. The correction matters even though the flag is not the chosen mechanism,
     because the next person weighing these options will read that line
     `[ref: SDD/Risks and Technical Debt/Known Technical Issues]`.
  2. Test: `scripts/ci/check-docs-sync.sh` passes; no document still describes `tcs-patterns` as
     shipping 21 skills; the audit snippet in `docs/about/skill-and-agent-design.md` globs a path
     that exists after the relocation; `docs/guides/tcs-patterns.md` describes the new setup flow
     and no longer promises the old all-21 install.
  3. Implement: correct `principles.md:167` with the measurement and its date; rewrite
     `plugins/tcs-patterns/README.md` for the catalogue-plus-installer shape and the now-kept
     promise in the plugin description; update `docs/guides/tcs-patterns.md`; update
     `docs/reference/` wherever the 21 are enumerated as skills.
  4. Validate: `scripts/ci/check-docs-sync.sh`; grep the repository for stale claims about the 21.
  5. Success:
     - [ ] `principles.md:167` corrected with the measurement `[ref: SDD/Known Technical Issues]`
     - [ ] No document claims the plugin ships 21 skills `[ref: PRD/F1]`
     - [ ] `docs-sync` passes locally before any push `[ref: SDD/Project Commands]`

- [ ] **T5.4 Both changelogs** `[activity: technical-writing]` `[parallel: true]`

  1. Prime: Read both files and `scripts/ci/check-changelog-version-sync.sh`. The plugin entry
     names the version `plugin.json` is about to carry; the PR-side check tolerates being one
     ahead. **Never hand-bump `plugin.json`** — `scripts/ci/bump-and-push.sh` does it on merge.
  2. Test: `check-changelog-version-sync.sh` passes; `check-docs-sync.sh` passes; the root entry
     states the breaking change in terms a user can act on.
  3. Implement: `plugins/tcs-patterns/CHANGELOG.md` gets the `2.0.0` entry — what moved, what the
     prefix means for anyone who typed `/tcs-patterns:ddd`, and that the promise in the plugin
     description is now kept. Root `CHANGELOG.md` gets the user-facing summary including the
     measured reason: the listing is budgeted, and 5918 characters of it were being spent on
     patterns most repositories never use.
  4. Validate: both CI scripts locally.
  5. Success:
     - [ ] Both changelogs updated; both sync checks pass locally `[ref: SDD/Project Commands]`
     - [ ] The breaking change is stated in terms of what a user must now do `[ref: SDD/Deployment View]`

- [ ] **T5.5 End-to-end validation** `[activity: validate]`

  1. Prime: Read the full primary flow `[ref: SDD/Runtime View/Primary Flow]` and the acceptance
     criteria table `[ref: SDD/Acceptance Criteria]`.
  2. Test: In a throwaway git repository fixture, walk all nine steps: scan, proposal, questions,
     confirmation, guard, write, manifest, commit offer declined, then **a new session** confirming
     the installed patterns appear in that session's skill listing (SDD/AC-8 — and it must be a new
     session, because the plugin cache is stale inside the one that changed it). Then bump a
     catalogue `VERSION`, start another session, and confirm the advisory names exactly that
     pattern. Then run `update` and confirm the manifest matches. Then `remove` and confirm both
     the files and the manifest entry are gone.
  3. Implement: no new production code. Anything missing at this point is a defect against a
     phase that reported complete, and is fixed in that phase's component rather than patched here.
  4. Validate: both legs reported **per leg**, never from a run verdict; all 17 SDD acceptance
     criteria walked and ticked; the CI gate, `docs-sync` and `changelog-version-sync` all run
     locally before pushing.
  5. Success:
     - [ ] The nine-step flow completes in a fixture repository `[ref: SDD/Runtime View/Primary Flow]`
     - [ ] Installed patterns appear in a **new** session's listing `[ref: SDD/AC-8]`
     - [ ] The advisory names exactly the bumped pattern `[ref: SDD/AC-11]`
     - [ ] All 17 SDD acceptance criteria verified `[ref: SDD/Acceptance Criteria]`
     - [ ] Both test legs green, each reported separately `[ref: SDD/Quality Requirements]`
