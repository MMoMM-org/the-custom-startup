---
title: "Phase 3: The install path"
status: in_progress
version: "1.0"
phase: 3
---

# Phase 3: The install path

## Phase Context

**GATE**: Read all referenced files before starting this phase.

**Specification References**:
- `[ref: SDD/Interface Specifications/Data model: the manifest]` — the TOML shape, and the stated
  limit that the hash covers `SKILL.md` only
- `[ref: SDD/Implementation Examples]` — the frontmatter rename, and why it raises rather than
  no-ops
- `[ref: SDD/Runtime View/Primary Flow]` — steps 6 to 8, guard then write then offer
- `[ref: SDD/Runtime View/Error Handling]` — ten error rows, six of which land in this phase
- `[ref: SDD/Cross-Cutting Concepts/System-Wide Patterns]` — nothing written before every check
  passes; atomic single-file writes in the destination directory
- `[ref: SDD/Architecture Decisions/ADR-1]` — the `tcs-` prefix and what defeats it
- `[ref: SDD/Architecture Decisions/ADR-4]` — hash at install, diff on conflict
- `[ref: SDD/Architecture Decisions/ADR-8]` — offer to commit, never commit
- `[ref: SDD/Risks and Technical Debt/Implementation Gotchas]` — the cross-device rename
- `[ref: PRD/F4, F5, F6, F8]` — fourteen acceptance criteria between them

**Key Decisions**:
- **The guard is a separate component from the installer** so that refusal is testable without any
  write happening. C4 runs to completion across the whole selection before C5 writes anything.
- **A skill registers under its frontmatter `name:`, not its directory.** Copying to `tcs-ddd/`
  without rewriting the frontmatter installs the pattern as `ddd` and silently defeats ADR-1. The
  installer raises instead of no-opping.
- **Temporary files are created in the destination directory**, never in `$TMPDIR`. Here they are
  different filesystems: `os.rename` raises `Cross-device link`, and `shutil.move` silently
  degrades to copy-then-delete, which is not atomic.
- **Skip is the default** on a divergence prompt, so an unanswered question cannot destroy local
  work.

**Dependencies**:
- Phase 1 — the catalogue is the copy source and holds the `VERSION` files.
- Phase 2 — not strictly required to build this, but the end-to-end test in Phase 5 needs both.

---

## Tasks

Delivers the write path: a manifest that records what happened, a guard that decides whether
writing is allowed, and an installer that is honest about what it did.

- [x] **T3.1 The manifest store** `[activity: data-architecture]`

  1. Prime: Read the manifest format `[ref: SDD/Interface Specifications/Data model: the manifest]`.
     TOML, because `observability-sources.toml` and `startup.toml` already establish it here and the
     file is reviewed in a pull request.
  2. Test: six assertions. Three of them were **sharpened at this task's TDD gate on 2026-10-05**
     because as first written they were satisfiable by an implementation that does not do the
     thing; the sharpened shape is mandatory, not advisory.

     a. Round-trips a manifest without loss.
     b. **Adding a pattern leaves the other entries byte-identical** (F6's second criterion).
        *Not* a comparison of parsed structures: `tomllib` cannot write, so `upsert` regenerates
        the whole file rather than patching it `[ref: SDD/Data model: the manifest, "Writing the
        TOML is hand-serialised"]`, and a structure comparison passes against a re-serialiser that
        reorders keys or respaces the file. Assert instead that every pre-existing pattern's exact
        table block survives byte-for-byte — capture the block before, `assert block in
        after_bytes` after — **and** that the parsed entry still equals the old one, which catches
        a block that survived verbatim but was shadowed by a duplicate table. The gate first
        proposed `original_bytes == after_bytes`; that cannot hold, because the test adds a
        pattern and the file must differ, so it would fail a correct implementation.
     c. An absent manifest reads as empty rather than raising.
     d. An **unparseable** manifest raises `ManifestUnparseableError`
        `[ref: SDD/Data model: the manifest, "What C6 returns"]`.
     e. **An unparseable manifest is never overwritten.** "Assert it raises" is vacuous here: the
        raise is the only observable, so an implementation that catches the error internally and
        writes anyway is indistinguishable from one that refuses. Capture the file's bytes before,
        run the upsert inside `pytest.raises`, then assert the bytes are unchanged. **Mutate the
        implementation to catch-and-write and confirm this assertion fails** — three parse guards
        in `detect.py` went untested until 2026-10-05 and could all have been deleted with the
        corpus still green, which is the same defect one layer down.
     f. **Currency is determinable from the manifest alone**, without reading any *installed*
        pattern file (F6's third criterion, SDD/AC-17). Asserting the returned value proves
        nothing about which files were opened. Do **not** mock `open()` — that couples the test to
        the implementation's I/O calls and a mock missing one path reports a false pass, the same
        shape as the `PYTHONPATH` mutation trap `tests/test_patterns_detect.py` already documents.
        Instead: **delete the installed pattern directory entirely** and assert currency is still
        determinable — manifest says `version = "3"`, catalogue `VERSION` says `4`,
        `<repo>/.claude/skills/tcs-ddd/` absent, and the check must still report stale. A function
        that reads an installed pattern file cannot pass that, because the file is not there.
        Reading the **catalogue's** `VERSION` is permitted and necessary; reading the **installed**
        pattern's files is what AC-17 forbids.
  3. Implement: `plugins/tcs-patterns/skills/patterns-setup/lib/manifest.py` — read, write, upsert,
     compare. Writing is atomic: temp file in `.claude/skills/`, then `os.replace`.
  4. Validate: `python3 -m pytest tests/test_patterns_install.py -q`; `python3 -m pytest -q`.
  5. Success:
     - [x] A single record names every installed pattern with its version `[ref: PRD/F6 1st]`
     - [x] A later install leaves prior entries unchanged `[ref: PRD/F6 2nd]`
     - [x] Currency determinable without inspecting pattern files `[ref: PRD/F6 3rd; SDD/AC-17]`
     - [x] An unparseable manifest is never overwritten `[ref: SDD/Runtime View/Error Handling]`

  **Delivered 2026-10-05.** `e85b339` RED, `363a952` the implementation, `ae2d548` and `9386767`
  two rounds of test closure, `fb306b4` two spec clarifications. Both review gates PASS. The file
  carries **24 cases in 17 functions**; the suite went 1022 → 1052.

  **The coverage history is the part worth keeping, because the checkbox hides it.** Fourteen
  mutations were run against this module across three passes, and all fourteen are now caught —
  but the sequence matters more than the total:

  | pass | mutants run | survived |
  |---|---|---|
  | after the first GREEN | 6 | **3** |
  | after those three were closed | 8 | **7** |
  | after those seven were closed | 8 (re-run) | 0 |

  So a suite that was green *and* mutation-verified on six behaviours was still blind to seven
  more. The three that survived the first pass were all in the serialiser, and the reason they
  survived is recorded against assertion (b) above: the byte-identical test reads its before-image
  out of a file the serialiser wrote, so a uniform reformatting applies to both sides of the
  comparison and is invisible. The seven that survived the second pass were the atomic-write
  mechanics, `with_pattern`'s two documented-but-unchecked claims, `read()`'s eight hand-rolled
  schema branches, and the `is_file()` guard.

  **Two of the seven could not have been caught by any `tmp_path` test, and that is a lesson
  rather than an excuse.** The SDD requires the temp file in `.claude/skills/` and the rename via
  `os.replace`, because here `/Volumes/Moon` (`dev=16777245`) and `/tmp/claude-501`
  (`dev=16777234`) are different filesystems and an `os.replace` across them raises
  `OSError: [Errno 18] Cross-device link` — measured. But pytest's `tmp_path` lives under
  `$TMPDIR`, so a test there puts the temp file and the destination on ONE filesystem, where both
  mutants work perfectly. The fix was to assert the **mechanism** — `mkstemp`'s `dir=` argument,
  and that `os.replace` is the call — rather than the outcome, which is identical wherever a test
  can reach. Asserting an I/O call is normally the weaker choice and was rejected for AC-17's
  currency check on the same day; it is the right one here precisely because atomicity is not
  observable in the result. The tests say so in their docstrings, or someone will "simplify" them
  into result assertions that cannot fail.

- [x] **T3.2 The collision guard** `[activity: backend-api]`

  1. Prime: Read the guard's place in the flow `[ref: SDD/Runtime View/Primary Flow]` step 6 and
     ADR-1's consequence note `[ref: SDD/Architecture Decisions/ADR-1]` — with the prefix the guard
     rarely fires, and it is still the mechanism that keeps a partial install coherent.
  2. Test: A name taken in the repository's own skills is refused with both locations reported; the
     same for the user's global skill directory; the same for a plugin skill; a selection with one
     colliding and two free names **approves the two and refuses the third** (F5's fourth
     criterion); the guard itself writes nothing under any input.

     Two corrections to this step, 2026-10-05, before dispatch. It read "installs the two and
     writes nothing for the third" — but T3.2 builds C4, which installs nothing at all; installing
     is C5's job in T3.3. The observable here is the **partition** the guard returns, and an
     implementer reading "installs" could reasonably have gone looking for an installer that does
     not exist yet. It also read "a reachable plugin skill", and reachability was dropped from the
     guard deliberately `[ref: SDD/Interface Specifications/Data model: the three namespaces (C4)]`
     — the guard enumerates every plugin skill it can find, enabled or not, because a disabled
     plugin is a future collision and over-inclusion costs one declined proposal while
     under-inclusion writes a duplicate that goes live on a settings edit.

     **Four more cases, added the same day after measuring the real namespaces. None of them
     would be written from the task text above, and each covers a way the guard silently
     under-reports — which is the unsafe direction, because a name the guard cannot see is a name
     it approves.**

     - **A skill directory that is a symlink.** Measured: `~/.claude/skills/obsidian-eval` is a
       link into a shared config checkout, and `rglob`/`glob("**")` find 18 of the 19 skills in
       that namespace while `os.walk(followlinks=True)` finds all 19. The fixture is a `SKILL.md`
       in a directory *outside* the namespace root with a symlink to it inside. Without this case,
       the enumeration the SDD originally specified passes every other test.
     - **A skill nested deeper than one level.** The user namespace holds 13 real skills at
       `synced/<uuid>/<name>/SKILL.md`. A bounded `*/SKILL.md` finds 6 of 19. The walk must be
       unbounded in depth.
     - **A directory under a skills root with no `SKILL.md`.** It is not a skill and must not
       occupy its name — `synced/` itself is the live instance.
     - **A `SKILL.md` whose frontmatter `name:` differs from its directory name.** Exactly one of
       259 real files does this (`writing-rules` registering as `writing-hookify-rules`), and it is
       the whole reason enumeration reads files rather than listing directories. The guard must
       refuse against the **registered** name and not against the directory's.

     The signature also changed: `check(repo_dir, intended_names, *, home_dir) -> GuardReport`.
     Two of the three namespaces live outside the repository, so `home_dir` has to be a parameter
     or the test can only ever drive one of them — this repository's own skill-tree walker settled
     that convention twice
     `[ref: scripts/observability/report.py:686; scripts/observability/sources.py:349]`. There is
     also a concrete reason beyond purity: the cached `tcs-patterns` is still **1.4.4** and still
     ships all 21 patterns as skills, so **21 of 21** bare catalogue names collide against the live
     plugin namespace today and **0 of 21** prefixed ones do — and all 21 stop colliding the moment
     this spec ships. A test that read the real `$HOME` would assert one thing today and the
     opposite after release: it would break *because the feature succeeded*.

     **T3.2's TDD gate returned BLOCK on 2026-10-05.** The contract gap it found is fixed in the
     SDD — `check` now returns a `GuardReport` with a third channel, `skipped`, because the rule
     "skipped **and reported**" had nowhere to report through and its test could only have asserted
     "does not raise" `[ref: SDD/Interface Specifications/Data model: the three namespaces (C4)]`.
     Seven further additions are required before the implementer is dispatched, and they are
     requirements of this task, not suggestions:

     1. **All three namespaces in ONE `check()` call.** Items testing one namespace at a time, each
        with one name, are all passed by an implementation that short-circuits after the first
        namespace yields a collision and never walks the others for the remaining names. Success
        criterion 1 is a property of a single call across the whole selection. Four names, one
        colliding in each namespace plus one free, all four outcomes asserted from one call.
     2. **The two plugin roots exercised independently, each with its own per-level semantics.**
        Both are three wildcards deep — `cache/<marketplace>/<plugin>/<version>/skills/` and
        `marketplaces/<marketplace>/<segment>/<plugin>/skills/` — so building them at the same
        depth is correct and unavoidable. (An earlier revision of this requirement said "DIFFERENT
        depths" and spelled out two patterns that are both three levels; it was written in the same
        commit that widened the marketplace glob from `*/plugins/*/` to `*/*/*/` and never
        reconciled with it. Corrected after T3.2's second gate pass caught the contradiction.)

        What differs is what each middle level *means*, and that is what the fixtures must carry:

        - **cache** — the third level is a **version**, and several coexist. Build **two versions of
          one plugin** with a skill name present in only the older one, and assert that name is
          still refused. That is the union-across-versions rule, and it has a live instance:
          `tcs-team` holds `testing` in cached `3.4.2` and `test-practices` in `3.4.4`, and
          `testing` is one of the 21 catalogue names.
        - **marketplace** — the second level is a **segment** and the third is the plugin, one per
          plugin, no versions. Build **both segment names**, `plugins/` and `external_plugins/`,
          and assert a name under each is refused.

        The dangerous direction is measured: the marketplace pattern applied to the cache root
        finds **zero** roots, so a guard that enumerated no plugin skills at all would pass every
        repo-and-user test. That is what makes exercising both roots load-bearing rather than
        tidy.
     3. **A plugin skill under `external_plugins/`** rather than `plugins/`, which is a real layout
        on this machine and the reason the marketplace glob was widened to three wildcards. Its
        name must still be refused.
     4. **`enabledPlugins` is ignored entirely.** A plugin skill colliding with an intended name,
        with `enabledPlugins` carrying `false` for that plugin in the home and/or repository
        `settings.json`, is still refused. The SDD names this as one of two things an implementer
        working from the old phrasing would get wrong; the other is the frontmatter-name case, which
        already has its test.
     5. **The `(st_dev, st_ino)` dedup — asserted through `skipped`, because that is the only
        channel where it shows.** The obvious form of this test is vacuous and was specified that
        way first: "two symlinks to one real skill directory, the name refused **once**, not
        twice" cannot fail, because `refused` is keyed by name and visiting one directory twice
        writes the same key twice. Caught by T3.2's second gate pass.

        It does **not** follow that the dedup is mechanism-only like T3.1's `os.replace` case.
        `skipped` is a **sequence** of `(path, reason)`, and two symlinks are two distinct paths,
        so a malformed file reached twice is reported twice. Both fixtures hold a `SKILL.md` with
        no frontmatter, and both counts are measured:

        | fixture | `len(skipped)` with the dedup | without, as measured on macOS |
        |---|---|---|
        | two sibling symlinks to one malformed skill directory | 1 | 2 |
        | a self-referential symlink inside a malformed skill directory | **1** | 33 |

        **Assert the left column only.** `len(skipped) == 1` is a property of the dedup and holds on
        any platform. The right column is what the mutant produced *here* and is not a portable
        number: measured, macOS raises `ELOOP` at symlink nesting depth **32**, which is what makes
        the cycle figure 33 rather than anything about this fixture. Linux's `MAXSYMLINKS` is
        conventionally 40, so the same fixture yields a different count there, and this repository
        supports both `[ref: SDD/Constraints]`. A mutation check asserts `len(skipped) > 1`, never a
        specific number. (`os.pathconf("/", "PC_SYMLINK_MAX")` reports 255 here and is a different
        quantity entirely — do not compute the bound from it, just avoid depending on it.) Noted
        because the paragraph immediately below forbids exactly this class of assumption for the
        recorded path, and the first draft of this table introduced one for the count.

        The second fixture is also the **cycle** case, which nothing else covers and which is the
        entire justification for not writing a timeout test — so without it that justification
        guards nothing. It must assert both that `len(skipped) == 1` and that the call returns
        normally: no unhandled `OSError`, a well-formed `GuardReport`. `timeout` is not the
        instrument and would not work anyway: it does not exist on macOS, and measured,
        `os.walk(followlinks=True)` on a cycle does not hang — macOS stops it with `ELOOP` after 66
        redundant directory visits, which the dedup reduces to 3.

        **Do not assert the recorded path of a deduplicated name.** Which of several symlinks to
        one directory gets recorded is `os.scandir` order: measured stable across repeated trials
        on this filesystem (`link-b` with the dedup, `link-a` without) and guaranteed by nothing.
        Assert the **count**, never which path won.
     6. **All four namespace roots absent, not just the repository's.** Each goes through a
        different glob or walk call. Parametrise the four.
     7. **Precedence across more than one pairing.** "Repo before user before plugin" is a 3-way
        order; a test of repo-vs-user alone is passed by a mutant that swaps user and plugin. Test
        at least two pairings, or all three colliding at once with exactly one refusal reported per
        name.

     The four malformed-input cases need a **pairwise-distinct** assertion on their reasons —
     `len({reason for _, reason in report.skipped}) == 4` or equivalent — not four separate checks
     that each reason is non-empty. The SDD requires "its own distinguishable reason"
     `[ref: SDD/Interface Specifications/Data model: the three namespaces (C4)]`, and a mutation
     that collapses two of the four into one generic string survives every isolated non-empty
     check while failing only a comparison of the reasons against each other.

     The write-nothing digest (step 4) must also run across **more than one scenario** — at
     minimum the symlink case, a malformed-input case, and the multi-namespace collision case. One
     nominal call does not support a claim of "under any input".

     **Fix round, 2026-10-05 — recorded after BOTH review gates returned PASS.** The first
     implementation passed 4f spec-compliance and 4g code-quality, 25 tests green, and 12
     independent mutations across namespace order, both plugin roots, the glob forms, precedence,
     `followlinks`, the skip reasons and the partition were all caught. Everything below was found
     *after* that, by mutation and probing rather than by reading. Two careful reviewers over the
     same 862 lines classified two of these as non-blocking observations and did not reach the other
     two. That is the lesson to carry into T3.3: **a green suite plus two PASS reviews plus a
     mutation round is still not coverage.**

     1. **[must fix] An unreadable directory makes the guard approve a name it could not check.**
        `os.walk`'s default `onerror=None` swallows directory-listing failures, so a `chmod 000`
        directory holding a `SKILL.md` yields no entries and no error — the name is **approved** and
        `skipped` is **empty**. An unreadable namespace root loses a whole namespace the same way,
        and `root.is_dir()` returns `True` on such a directory so the missing-root clause does not
        help. Measured. Pass `onerror=` and route the failure into `skipped`; verified to catch both
        the intermediate directory and the root. The contract now carries the rule
        `[ref: SDD/.../"A directory the guard cannot list is skipped and reported too"]`.

     2. **[must fix] The hand-rolled `name:` parser disagrees with YAML on 9 of 14 inputs, and 4 of
        those make the guard approve a taken name.** A skill registers under what YAML yields, not
        what a regex captures. `name: ddd # comment` captures `ddd # comment`, so `ddd` is approved
        while the harness registers `ddd` — a live duplicate, which is the one failure C4 exists to
        prevent `[ref: SDD/Constraints/CON-3]`. Same for a block scalar (`>-`, `|`), a tag
        (`!!str`), an anchor (`&a`), and duplicate `name:` keys where YAML takes the last and the
        regex takes the first. **The parser must recognise a plain scalar, optionally quoted, and
        skip-and-report anything else** — never return a value it is not confident of, because a
        garbage name silently frees the real one whereas a skip is reported. Rule and full table:
        `[ref: SDD/.../"Its frontmatter `name:` means what a YAML parser makes of it"]`.

        Pin it with a **differential test against PyYAML**. `guard.py` stays stdlib-only on the 3.11
        floor, but the test suite may use PyYAML and already does
        (`tests/test_tcs_patterns_catalogue_relocation.py`; `requirements-dev.txt:18`), for this
        exact class of bug. A differential test is also the strongest shape available, because the
        expectation enters from a source with no shared ancestry with the code under test.

     3. **[must fix] The write-nothing digest cannot see a `mkdir`.** `_digest_tree` hashes
        `filenames` and never `dirnames`, so a directory created inside an already-existing tree
        leaves the hash unchanged. Verified: injecting a nested-empty-directory `mkdir` into
        `check()` **survived all 25 tests**, while injecting a file write was caught. The line that
        would cause it — `path.parent.mkdir(parents=True, exist_ok=True)` — exists legitimately in
        `manifest.py`, the sibling module, so it is a plausible paste. Hash the directory shape too;
        verified to close the gap while leaving the no-change, file-added and symlink-cycle cases
        behaving identically.

     4. **[must fix] An unterminated frontmatter block is a second, untested path.** A `SKILL.md`
        opening with `---` and never closing it reaches the same skip as a file with no block at
        all. Mutating that branch to parse to EOF instead survived all 25 tests. Add the fixture —
        and note it shares the "no usable frontmatter block" reason with the missing-block case, so
        the assertion becomes `len(skipped) == 5` with `len(reasons) == 4`, not five distinct
        reasons.

     5. **[must fix] Delete the two defensive `OSError` guards around the dedup's `stat()`.** Three
        mutations of them survived all 25 tests, and **no constructible fixture reaches them**:
        `os.walk` classifies a dangling symlink as a *file*, so the dedup never stats it, and a
        symlink behind a `chmod 000` intermediate is never discovered because the walk cannot list
        the intermediate — both verified empirically, both proposed as fixtures and both disproved.
        What stays reachable is a genuine race, and letting it surface is better than swallowing it:
        this component's stance is that a name it could not check must be reported, and an exception
        is the loudest report available. Marcus's call, 2026-10-05.

     6. **[observation, no action]** The `chmod 0o000` fixture does not block reads when the suite
        runs as root, which would drop `skipped` from 5 to 4 and fail the count. This repository's
        CI runs on non-root GitHub-hosted runners on both macOS and Linux, so CI is safe; a
        root-owned local Docker session is the exposure. It fails loudly rather than silently, which
        is why this is recorded and not fixed.
  3. Implement: `lib/guard.py` — the three namespace checks, returning a **`GuardReport`** with
     three named channels: `approved`, `refused` (name → namespace plus the colliding `SKILL.md`
     path), and `skipped` (`(path, reason)` for every `SKILL.md` that could not be read). The third
     channel is not optional: the contract's rule is "skipped **and reported**", and without a
     channel that half is unfalsifiable. **Read the namespace contract first**
     `[ref: SDD/Interface Specifications/Data model: the three namespaces (C4)]`: a directory is a
     skill iff it holds a `SKILL.md` and its name is that file's frontmatter `name:`, not the
     directory's — measured, **one of 259** installed `SKILL.md` files diverges, carrying 127
     distinct registered names — enumeration is `os.walk(followlinks=True)` with an
     `(st_dev, st_ino)` dedup rather than `rglob` or `glob("**")`, which cannot see a symlinked
     skill directory, and rather than `glob(recurse_symlinks=True)`, which is 3.13+ and below
     ADR-2's 3.11 floor; and the plugin cache holds several versions of the same plugin, whose
     names are **unioned** and never compared, while the marketplace tree holds one directory per
     plugin under either of two segment names.
  4. Validate: `python3 -m pytest tests/test_patterns_guard.py -q`; prove the guard writes nothing
     with a **sha256 digest over every namespace tree before and after**, not only a read-only
     temporary directory. A read-only directory catches a write *into that directory* and says
     nothing about a write anywhere else, which is the whole claim being made. The digest form is
     the one T2.7 used to prove `detect()` writes nothing, over 101 catalogue and 84 fixture files.
     Both figures verified 2026-10-05 after the gate reported it could find no such test on disk:
     **84 is a walk of the fixture tree** (82 git-tracked files plus the two gitignored `venv/` and
     `.venv/` artefacts inside `trap-07-venv-and-dot-venv/`), which is the right population for a
     digest proof since it hashes what is on disk rather than what git tracks, and T2.7's recorded
     **81** is that same walk when the corpus held 26 fixtures rather than 27. The gate was right
     about the substance, though: T2.7's proof was an **ad-hoc harness whose result was recorded in
     the plan** `[ref: plan/phase-2.md, T2.7 "discharged by digest rather than by reading"]`, and
     no committed test performs it. T3.2's digest check is therefore a committed test, which is an
     improvement on T2.7 rather than a repeat of it — and it is the reason the claim is worth
     re-proving here instead of citing.
  5. Success:
     - [x] All three namespaces checked before any write `[ref: PRD/F5 1st-3rd]`
     - [x] Non-colliding patterns still install, no rescan `[ref: PRD/F5 4th; SDD/AC-10]`

  **Delivered 2026-10-05.** `d5868bb` RED (25 cases, no implementation), `c81d3bc` the guard,
  `a94afc4` the five fix-round items, `05c3736` the truncation test. Both review gates PASS.
  `tests/test_patterns_guard.py` carries **46 tests**; the suite went 1052 → **1098**, bats
  unchanged at **1187 ok / 0 not ok** across four legs.

  **The coverage history is the part worth keeping, because the checkbox hides it — and T3.2's
  history is sharper than T3.1's.** T3.1 at least failed its early mutation rounds. T3.2 *passed
  everything* and was still wrong:

  | stage | result |
  |---|---|
  | TDD gate | **four passes**, 13 specification defects fixed before any code |
  | first implementation | 25 tests, green |
  | 4f spec-compliance | **PASS** — all seven requirements verified against the control flow |
  | 4g code quality | **PASS** — no must-fix correctness bug in `guard.py` |
  | mutation round 1 (12 mutants) | **12 caught, 0 survived** |
  | then: probing the instruments | **5 defects found** |
  | after the fix round | 46 tests; 29 mutants total, 5 genuine survivors, all closed |

  **What the five post-PASS defects were, and why none of the four gates saw them.** Every one was
  found by *running something*, not by reading:

  1. **`os.walk`'s default `onerror=None` swallows directory-listing failures.** A `chmod 000`
     directory holding a `SKILL.md` made the guard **approve** that name with `skipped` empty, and
     an unreadable namespace root lost a whole namespace the same way. This is the one failure C4
     exists to prevent `[ref: SDD/Constraints/CON-3]`, and it sat behind a green suite and two PASS
     reviews. `root.is_dir()` returns `True` on such a directory, so the missing-root clause did not
     catch it either. An unreadable *file* was reported; an unreadable *directory* was invisible —
     same hazard, opposite handling, and only the tested one was handled.
  2. **The hand-rolled `name:` parser disagreed with YAML on 9 of 14 inputs**, 4 of which returned a
     garbage name and thereby *freed the real one*. Now verified over **22 cases**: 11 agree with
     PyYAML exactly, 11 skip-and-report, **0 return a name YAML disagrees with**.
  3. **The write-nothing digest could not see a `mkdir`** — it hashed `filenames` and never
     `dirnames`, so a nested empty directory left the hash unchanged. The line that would cause it
     exists legitimately in `manifest.py` next door.
  4. **An unterminated frontmatter block** was a second, untested path to the same skip.
  5. **Two defensive `OSError` guards were unreachable dead code** — three mutations of them
     survived all 25 tests.

  **Two lessons about the instruments, not the code.** First, three times in this task a measuring
  harness of mine was the faulty part: a mutation that injected an unused variable and dutifully
  reported SURVIVED, and a divergence script whose predicate ("do the outcomes differ?") was wrong
  for a parser now *specified* to skip rather than agree. Both produced alarming numbers that were
  artefacts. Verify the instrument before believing the measurement.

  Second, **a fixture that looks like it tests a gap may not reach it.** Two candidate fixtures for
  the dead branch were proposed, constructed, and both disproved: CPython's `os.walk` wraps its
  `entry.is_dir()` categorisation in `except OSError: is_dir = False`, so any stat failure
  reclassifies the entry as a *file* before the dedup ever stats it. And the multi-unreadable-
  directory fixture **I specified** would not have caught the truncation it was written for, because
  `unreadable_dirs` is scoped per `_walk_skills()` call — one call per root — so one unreadable
  directory per root leaves a single-element list where slicing is a no-op. The implementer found
  that by running my design against the mutant instead of trusting my description, which is exactly
  the right move and is why the committed fixture puts two of them under the *same* root.

- [ ] **T3.3 The installer** `[activity: backend-api]`

  1. Prime: Read the rename example and its refusal
     `[ref: SDD/Implementation Examples]`, the write-safety patterns
     `[ref: SDD/Cross-Cutting Concepts/System-Wide Patterns]`, and the gotchas
     `[ref: SDD/Risks and Technical Debt/Implementation Gotchas]`. `install_files.sh` is the
     structural template in spirit — plugin-root resolution that does not rely on
     `CLAUDE_PLUGIN_ROOT` being set, atomic marker write, no auto-commit — but the subshell sentinel
     has no Python equivalent and its purpose does not apply.
  2. Test: Each chosen pattern lands at `.claude/skills/tcs-<name>/` with its full subtree; the
     installed `SKILL.md` frontmatter reads `name: tcs-<name>`; a `SKILL.md` with no frontmatter
     `name:` line raises and writes nothing for that pattern; nothing unchosen is written; the
     manifest records version, installed name and hash for each; a second identical install writes
     no change (idempotency); a write failing mid-selection leaves earlier patterns in place with
     the manifest recording exactly what succeeded; the final report lists every write and states
     that nothing was committed.
  3. Implement: `lib/install.py` — copy, frontmatter rename, hash of the installed `SKILL.md`,
     manifest upsert, report. Temp files in the destination directory.
  4. Validate: `python3 -m pytest -q`; run an install into a throwaway git repository fixture and
     inspect the tree and the manifest by hand once — the suite checks the contract, a human
     checks that the result is what a user would want to find.
  5. Success:
     - [ ] Exactly the chosen patterns, each named `tcs-<name>` in its frontmatter `[ref: PRD/F4 1st; SDD/AC-7]`
     - [ ] A missing frontmatter `name:` raises rather than installing unprefixed `[ref: SDD/ADR-1; SDD/Error Handling]`
     - [ ] Report lists writes and states no commit was made `[ref: PRD/F4 3rd]`
     - [ ] A second identical install is a no-op `[ref: SDD/Quality Requirements]`

- [ ] **T3.4 The update path, with divergence handling** `[activity: backend-api]`

  1. Prime: Read ADR-4 `[ref: SDD/Architecture Decisions/ADR-4]` including its stated limit — the
     hash covers `SKILL.md` only, so a locally edited reference file is replaced without a prompt,
     and that is deliberate rather than an oversight to fix here.
  2. Test: `update` refreshes only patterns whose version is behind and asks nothing about the
     selection — no scan, no questions (F8's first criterion); a pattern whose file no longer
     matches its recorded hash prompts per pattern with a unified diff available, defaulting to
     skip; after a refresh, each pattern's manifest version equals its catalogue `VERSION` (F8's
     third criterion and SDD/AC-17); declining leaves the local file untouched and the manifest
     entry unchanged, so the advisory keeps reporting it.
  3. Implement: the `update` verb in `lib/install.py`, divergence detection against the manifest
     hash, and the `difflib` unified diff.
  4. Validate: `python3 -m pytest -q`; exercise both answers — overwrite and skip — and assert the
     resulting manifest in each case.
  5. Success:
     - [ ] Only drifted patterns refreshed, selection untouched `[ref: PRD/F8 1st]`
     - [ ] Divergence asks before replacing, skip is the default `[ref: PRD/F8 2nd; SDD/ADR-4]`
     - [ ] Post-refresh versions match the catalogue `[ref: PRD/F8 3rd; SDD/AC-12]`

- [ ] **T3.5 Phase validation** `[activity: validate]`

  Both legs, per leg. Confirm the ordering property explicitly: with a selection containing a
  collision, assert that **no file was created at all** before the guard completed — the property
  is "nothing is written before every check has passed", and a test that only checks the end state
  would pass even if the installer wrote and then rolled back.

  - Success: install, guard, manifest and update suites green; no-write-before-guard asserted
    `[ref: SDD/AC-7, AC-9, AC-10, AC-12, AC-17]`
