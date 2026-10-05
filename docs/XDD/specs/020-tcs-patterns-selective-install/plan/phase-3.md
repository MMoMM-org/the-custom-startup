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

- [x] **T3.2b The guard must not refuse our own install** `[activity: backend-api]`

  Added 2026-10-05, after T3.2 closed. **T3.2 is not reopened** — it shipped what it was specified
  to do, and the specification was wrong `[ref: SDD/Interface Specifications/Data model: the three
  namespaces (C4), "own_installed is required"]`. Marcus's call on both the fix and the bookkeeping.

  1. Prime: Read the `own_installed` rule in the C4 contract and the three boundaries on it — repo
     namespace only, required with no default, empty set when the manifest cannot be read. Read
     `lib/manifest.py`'s `Manifest` to see where `installed_as` comes from, and
     `tests/test_patterns_guard.py` for the conventions to extend.
  2. Test: With a pattern installed as `tcs-ddd` in the repository namespace and the manifest
     recording it, `check(..., own_installed={"tcs-ddd"})` **approves** `tcs-ddd` rather than
     refusing it — the test that would have caught the defect, and it must fail before the change.
     Then: the same name found in the **user** namespace is still refused even when it is in
     `own_installed`; the same for a **plugin** namespace hit; a name in `own_installed` that is not
     installed anywhere is simply approved; omitting `own_installed` entirely raises `TypeError`
     rather than defaulting; and an empty `own_installed` reproduces the old behaviour exactly, which
     is the safe direction when a caller cannot read the manifest.
     **The RED phase here cannot prove what a RED phase usually proves, and that needs saying.**
     `own_installed` is a *required* parameter, so every test written against the new signature
     fails with `TypeError: check() got an unexpected keyword argument 'own_installed'` before the
     change — measured. That is RED, but it proves the **parameter is absent**, not that the old
     **behaviour was wrong**. Those are different claims and only the second one is the defect.

     So the RED commit needs two shapes, and only one of them can exist before the signature
     changes:

     - **(a) The defect, asserted against the CURRENT signature.**
       `check(repo, {"tcs-ddd"}, home_dir=home)` with `tcs-ddd` installed returns
       `approved=[]`, `refused={'tcs-ddd': 'repo'}` — measured. A test asserting `tcs-ddd` *is*
       approved fails **on the assertion**, which is the only form that demonstrates the behaviour
       is wrong rather than the signature being old.
     - **(b) The fix, asserted against the NEW signature.** Fails on `TypeError` until the
       parameter lands, then pins the three boundaries.

     (a) must be **rewritten** to the new signature once the parameter exists, since the old call
     will no longer be legal — so it is deliberately a two-step test, and the RED commit should say
     so in its message. Recorded because the cheap path is to write only (b), see a red suite, and
     believe a `TypeError` validated the behaviour. It did not.

  3. Implement: the `own_installed` keyword on `check()`, suppressing a **repo-namespace** match
     only. Nothing else in C4 changes; the enumeration, the dedup and the skip channel are untouched.
  4. Validate: `python3 -m pytest tests/test_patterns_guard.py -q` then the whole suite; report per
     leg. Mutate at minimum: suppressing user-namespace or plugin-namespace matches too (must fail
     the two boundary tests), and giving `own_installed` a `frozenset()` default (must fail the
     `TypeError` test).
  5. Success:
     - [x] A pattern this tool installed is not refused on a second run `[ref: SDD/Quality Requirements; PRD/F4]`
     - [x] A `tcs-` name owned by another namespace is still refused `[ref: PRD/F5 1st-3rd]`
     - [x] `own_installed` cannot be forgotten silently `[ref: SDD/.../"Required, with no default"]`

  **Delivered 2026-10-05.** `12932f6` RED (two shapes: the pre-fix-signature defect test failing
  on `AssertionError`, everything else on the new signature's `TypeError`; all 25 pre-existing
  calls mechanically given `own_installed=frozenset()`), `e51d9d4` the fix (the `own_installed`
  keyword, repo-namespace-only, and the defect test rewritten to the new signature). Guard suite
  53 passed (46 + 7); whole suite 1105 passed, 1 skipped, 1 deselected (was 1098/1/1 before this
  task). Four mutations run, all caught: suppressing user- or plugin-namespace matches too, keying
  the suppression on the repo namespace label alone rather than `own_installed` membership (the
  load-bearing one — caught by 7 tests including the one built for exactly this), and a
  `frozenset()` default on the parameter.

  **Gate found a fifth, 2026-10-05.** `name.lower() in {o.lower() for o in own_installed}` passed
  all 53 — a real hazard, not cosmetic: `own_installed` is lowercase by construction
  (`manifest.py`'s `_INSTALLED_AS_RE`) while a registered name comes from a third party's
  frontmatter and can be any case, so a case-insensitive match would exempt a genuinely-taken
  `TCS-OURS` as if it were our own `tcs-ours`. `guard.py`'s exact `in` comparison was already
  correct; only the test was missing. `f50ca9d` adds it, no production change. Guard suite 54
  passed (53 + 1); whole suite 1106 passed, 1 skipped, 1 deselected.

- [x] **T3.3 The installer** `[activity: backend-api]`

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
     **Six clarifications, 2026-10-05, settled before dispatch.** Four interfaces this step
     depends on were undefined, and the SDD's own rename sample was wrong in three ways. All of it
     is now in `[ref: SDD/Interface Specifications/Data model: the install plan and report (C5)]`,
     which is what to brief from — read it before the task text above, because it changes what two
     of these test clauses mean.

     1. **`install()` takes names, not a `GuardReport`.** C4 and C5 are separate precisely so a
        refusal is testable without a write, and importing the guard into the installer defeats
        that. C3 runs `check()` and passes `GuardReport.approved` here, so `install()` assumes its
        names are already cleared and never rescans — the second half of AC-10. **AC-10 is satisfied
        by C4 and C5 together and by neither alone**: T3.2 owned the partition, T3.3 owns "the
        others still install".
     2. **"A second identical install writes no change" means CONTENT, proven by a digest.** Not
        mtimes: re-copying an identical file changes an mtime while leaving content identical, so an
        mtime assertion fails a correct implementation and a content assertion passes a wrong one.
        Assert that every installed file *and the manifest* are byte-identical after the second run.
        The implementation that earns it: skip a pattern entirely — no copy, no rename, no manifest
        rewrite — when the manifest's `version` matches the catalogue `VERSION` **and** its `sha256`
        matches the hash of the `SKILL.md` currently installed. Hashing the *installed* file, not
        the catalogue's, is what detects a local edit and is the seam T3.4 plugs into.
     3. **The manifest is upserted per pattern, after that pattern's directory lands.** Per-run
        would record nothing when the run fails midway, which is the opposite of the requirement.
        Directory-then-manifest, not the reverse: files with no manifest entry are recoverable and
        a re-install just rewrites them, while a manifest entry with no files makes C7 report a
        pattern that is not there.
     4. **Each pattern appears atomically**: copy into `<repo>/.claude/skills/.tcs-<name>.tmp/`,
        rewrite the frontmatter there, then `os.rename` into place. A half-copied `tcs-<name>/` is a
        state the mid-selection requirement does not allow for. The temp directory must be *inside
        the destination* because a consumer repository need not share a filesystem with the
        catalogue — measured, the catalogue is `dev=16777245` here and `$TMPDIR` is `dev=16777234` —
        and a rename across filesystems raises `Cross-device link`. A copy may cross freely; a
        rename may not.
     5. **C5 reports, C3 offers.** `install.py` is a library with no interactive surface; ADR-8's
        offer needs `AskUserQuestion`, which only a skill can raise. `InstallReport` carries every
        write plus `committed=False`, and that *is* the success criterion — **no test here should
        look for a prompt, and no `AskUserQuestion` belongs in `install.py`**.
     6. **`catalogue_dir` is a parameter defaulting to `Path(__file__).resolve().parents[3] /
        "templates" / "patterns"`.** Measured: `CLAUDE_PLUGIN_ROOT` is `None` in a Bash-tool
        subprocess, and the skill runs this module by invoking `python3`, so the variable that
        exists for harness-spawned plugin code is absent exactly where this runs. It is a parameter
        for the same reason `home_dir` is one on C4: a test that cannot point it at a fixture cannot
        test it.

     **Two more tests this task owns, neither obvious from the clauses above.**

     - **All 21 catalogue `name:` values are plain scalars.** The rename refuses a block scalar,
       tag or anchor rather than rewriting its first line and orphaning the rest — but that refusal
       is only harmless while the catalogue contains none.
       `test_all_21_frontmatter_blocks_still_parse_as_yaml` proves they *parse*, which a block
       scalar also does `[ref: tests/test_tcs_patterns_catalogue_relocation.py:141]`. The
       precondition the installer depends on is narrower than parseability and needs its own
       assertion.
     - **The rename leaves everything below the frontmatter byte-identical**, including a
       `name:`-shaped line in the body. The SDD's sample was corrected on 2026-10-05 and the
       corrected version is verified against 15 inputs — the six it previously mishandled now raise
       `InstallError`: an unterminated block (which used to raise a bare `ValueError`), a CRLF file
       (refused with a message asserting the opposite of the truth), and a block-scalar, tag or
       anchor `name:` (which used to "succeed" while producing broken YAML in an installed skill).

     **T3.3's TDD gate returned BLOCK on 2026-10-05.** One finding was a contract defect of mine:
     the signature carried `report_only=False` with semantics defined nowhere, and the gate was
     right that no test can be written against it. **It is removed**, not defined — nothing in F4
     asks for a dry run `[ref: SDD/Interface Specifications/Data model: the install plan and report
     (C5), "No report_only parameter"]`. Six corrections to the test list follow, and they are
     requirements of this task:

     a. **A per-pattern fault does not escape `install()`.** The rewrite raises `InstallError`;
        `install()` catches it, records `failed[name]`, and continues. So the malformed-pattern
        tests call `install(repo, [good, bad], ...)` **once**, assert it **returns normally**, then
        assert `report.failed[bad]` carries a reason, `report.installed[good]` is populated, and
        **nothing exists on disk** for `bad`. A test wrapping the call in
        `pytest.raises(InstallError)` tests the opposite of the contract and cannot observe the
        other patterns installing — and a mutation letting the exception propagate would still pass
        a loosely written version.
     b. **"Full subtree" needs a multi-file fixture and content equality.** The fixture pattern must
        hold at least one non-`SKILL.md` file (a `reference/*.md`), and the test must assert its
        **bytes** match the catalogue's. A mutation copying only `SKILL.md` survives any test that
        merely checks the `tcs-<name>/` directory exists.
     c. **The expected sha256 is computed by the test, from the installed file.** The test runs
        `hashlib.sha256(installed_skill_md.read_bytes()).hexdigest()` itself and compares that to
        the manifest entry — it never calls `install.py`'s hashing. The fixture's catalogue `name:`
        necessarily differs from the installed `tcs-<name>`, so the two files' bytes differ, and a
        mutation hashing the catalogue's original bytes is caught **only** if the comparison's
        byte-source is read independently.
     d. **Mid-selection failure reuses the malformed fixture, not mocking.** One well-formed pattern
        and one with a malformed `name:`, requested in **one** call with the good name **first** in
        `names`, so "earlier patterns stay" is actually exercised by order. A content-driven failure
        rather than a heavy I/O mock, and it reuses a fixture this task needs anyway.
     e. **A positive CRLF test.** The corrected rename sample fixed a *false rejection*: the old
        `startswith("---\n")` refused a CRLF file, and `re.match(r"^---\r?\n", text)` accepts it.
        Every other frontmatter test covers a *raise* path; this is the one *accept* path the
        correction changed, and it had no coverage. A fixture whose `SKILL.md` uses CRLF endings
        must install successfully.
     f. **The default-`catalogue_dir` test derives its own expected path.** It must build
        `REPO_ROOT / "plugins" / "tcs-patterns" / "templates" / "patterns"` independently, not read
        `install.py`'s own `parents[3]` expression back at it — otherwise the assertion is a
        snapshot of the code under test, which is the failure that got past T3.1's gate. Also assert
        `report.committed is False`, identity not falsiness, since the field is typed as always
        `False`.

     g. **`install()` is purely additive — it never removes or overwrites anything under
        `tcs-<name>/`.** Settled 2026-10-05 after the gate asked, in effect, when the delete I had
        assumed necessary would hurt. The answer was: whenever the user had edited the pattern. ADR-4
        puts divergence detection, the diff **and** the asking all on `update`, and every F8
        criterion reads "When the update runs" / "When the update would overwrite it" — nothing
        anywhere puts an overwrite in `install`
        `[ref: SDD/Interface Specifications/.../"install() is purely additive"]`. The three cases:
        absent → write; present and current → `unchanged`; present and anything else → `failed`
        with a reason naming `update`. **None of them deletes.**

        Three consequences for this task's tests. **"`install()` never removes a file" is a
        **required** assertion, not an available one** — proved by a digest over the installed tree
        before and after, the same shape as C4's write-nothing proof and one step weaker. The
        earlier wording here said "an invariant every test *can* carry", which the third gate pass
        correctly called out: a safety invariant stated permissively is not an invariant, and a
        mutation that reports `failed` correctly **while still overwriting the file on disk** passes
        any test that only checks the report channel. Every test that calls `install()` against a
        pre-existing installed pattern carries the digest. The `os.rename`-onto-a-non-empty-directory case
        **disappears**, because the only state that reaches the rename has an absent target, so
        there is no removal step to test. And a test asserting that a re-install *replaces* a stale
        directory would now be asserting the opposite of the contract — if you were about to write
        one, write the refusal instead.

        The single delete `install()` may perform is of **its own** leftover `.tcs-<name>.tmp/` from
        a crashed run. Test that distinction explicitly: a leftover temp directory is cleaned, a
        user's installed pattern never is.

     h. **The "present, and anything else" row needs two fixtures of its own.** Found by T3.3's
        third gate pass, and it is the gap that made the contradiction in (g) dangerous rather than
        merely untidy: **nothing else in this list puts a pattern through `install()` a second time
        in a present-but-not-current state.** Every other test is either absent→write or, in (i) below, the
        ordering of a *fresh* write. Two mutations therefore survive the whole list:

        - one that silently overwrites a **version-stale but unedited** pattern — which is the stale
          "anything else is a write" text implemented literally — because no test bumps only the
          catalogue's `VERSION` between two runs and re-installs;
        - one that reports `failed` correctly **and still overwrites the file on disk** before
          returning, which any report-channel-only assertion passes.

        Two separate fixture states are required, because "not current" has two distinct triggers
        and a test of one does not cover the other:

        | fixture | version | installed `SKILL.md` hash |
        |---|---|---|
        | locally edited | matches the catalogue | **differs** from the manifest |
        | stale, not edited | **behind** the catalogue | matches the manifest |

        Each asserts three things: **(1)** a digest over that pattern's entire installed subtree is
        **identical** before and after the call — the invariant, now required rather than offered;
        **(2)** the name lands in `report.failed` with a reason naming `update`; **(3)** the name is
        in neither `installed` nor `unchanged`. Assertion (1) is the one that kills the second
        mutation, and no amount of report-channel checking substitutes for it.

     i. **The directory-then-manifest ORDER needs its own test, with a narrow monkeypatch.**
        Found by T3.3's gate on its second pass, and it is a mutation nothing else catches: every
        failure path otherwise tested fails during the **frontmatter rewrite**, which happens
        *before* the final `os.rename`, so neither the directory nor the manifest entry is ever
        written and the order between them is invisible. A mutation calling `manifest.upsert()`
        *before* renaming the pattern into place would pass every other test in this task —
        success-path tests cannot see the order because both artefacts end up present either way.

        The test: monkeypatch `manifest.upsert` to raise for one target name, call `install()` for
        it, then assert **(1)** `tcs-<name>/` exists on disk with its full correct content,
        **(2)** the name is **not** in the manifest, and **(3)** the name lands in `report.failed`.
        A monkeypatch is required and is appropriate here — a fixture alone cannot reach the seam
        between two successful steps, the directory-write path still runs for real, and T3.1 set the
        precedent for exactly this shape `[ref: tests/test_patterns_install.py,
        test_write_creates_its_temp_file_beside_the_manifest]`. That is a targeted patch of one
        collaborator, not the kind of over-mocking that proves nothing.

     **Why the temp-directory assertion is a mechanism assertion, and why the outcome route was
     rejected.** The requirement is that a rename never crosses filesystems, and `tmp_path` puts the
     temp directory and the destination on one filesystem by construction — the same situation T3.1
     settled for `manifest.py`'s atomic write, with the same resolution. The tempting alternative is
     to make it observable by putting the fixture *repository* inside this worktree (`dev=16777245`)
     while `$TMPDIR` is `dev=16777234`, so a mutant writing its temp directory to `$TMPDIR` would
     genuinely raise `Cross-device link`. **Rejected on two grounds**: CI runs on a single-filesystem
     runner, so such a test would pass there whether or not the code were correct — a test that only
     works on one developer's machine is worse than a mechanism assertion that works everywhere —
     and a fixture written inside the worktree inherits this repository's `.gitignore`, which has
     already broken directory-enumeration tests here. So: assert that `mkstemp`/`mkdtemp` received a
     `dir=` inside `<repo>/.claude/skills/`, and that `os.rename` is the call that puts the pattern
     in place, and say in the docstring why — or someone will "simplify" it into a result assertion
     that cannot fail.

  3. Implement: `lib/install.py` — copy, frontmatter rename, hash of the installed `SKILL.md`,
     manifest upsert, report. Temp files in the destination directory.
  4. Validate: `python3 -m pytest -q`; run an install into a throwaway git repository fixture and
     inspect the tree and the manifest by hand once — the suite checks the contract, a human
     checks that the result is what a user would want to find.
  5. Success:
     - [x] Exactly the chosen patterns, each named `tcs-<name>` in its frontmatter `[ref: PRD/F4 1st; SDD/AC-7]`
     - [x] A missing frontmatter `name:` raises rather than installing unprefixed `[ref: SDD/ADR-1; SDD/Error Handling]`
     - [x] Report lists writes and states no commit was made `[ref: PRD/F4 3rd]`
     - [x] A second identical install is a no-op `[ref: SDD/Quality Requirements]`

  **Delivered 2026-10-05.** `b49f463` RED (18 cases in a new file,
  `tests/test_patterns_installer.py` — deliberately not merged into T3.1's
  `test_patterns_install.py`), `e19bc5f` the implementation (`lib/install.py`,
  C5). `installer` suite 18 passed; whole suite 1106 → **1124** passed (1
  skipped, 1 deselected unchanged). Manual validate step done: a throwaway
  git repo, `install(repo, ["ddd", "hexagonal"])` against the real catalogue
  — tree, manifest and frontmatter all inspected by hand, nothing committed
  (`git log` unchanged, `.claude/` sits untracked).

  **Both review gates found two more defects, 2026-10-05, after the suite
  was green** — both in `solution.md`'s own contract, not in the
  implementation, and both surfaced by this task's implementer flagging a
  gap rather than coding around it:

  1. **`install()`'s signature omitted `bundle`**, while `manifest.upsert()`
     requires it with no default — there was no legal call from C5 into C6
     as specified. The implementer derived it internally from this plugin's
     own `plugin.json`, flagged the gap, and the resolution was kept as the
     **default** but promoted to a **parameter**: it would otherwise be the
     one input to `install()` no test could drive (`catalogue_dir`, C4's
     `home_dir` and `own_installed` are parameters for exactly that reason),
     and CI bumps `plugin.json` on every merge, which would make a test
     asserting the manifest's `bundle` field against the real file break on
     a version bump rather than a regression `[ref: solution.md, point 7]`.
  2. **The fourth defect in the rename sample `solution.md` corrected and
     verified against 15 inputs the day before.** `(?m)^name:.*$` — `.`
     does not match `\n` but DOES match `\r`, so the replacement silently
     dropped the trailing `\r` of the one line it rewrote on a CRLF file:
     measured, a 5-line CRLF input came out as 4 CRLF lines and 1 bare LF
     line. The implementer's own CRLF test caught the discrepancy, but
     first drew the wrong conclusion — judged the behaviour correct and
     weakened the assertion to match, rather than fixing the regex.
     Flagging it is what made it findable; `[^\r\n]*` is the fix, re-verified
     against all 15 original inputs plus the per-ending counts (5 CRLF in, 5
     CRLF out).

  `f3b168c` RED for both (two new cases plus a restored strict CRLF
  assertion and its LF counterpart), `444d21c` the fix. `installer` suite
  18 → **21** passed; whole suite 1124 → **1127** passed (1 skipped, 1
  deselected unchanged).

  **Mutations: nine total, all caught, none survived.** The six required,
  run against the first implementation, each verified individually then
  reverted (confirmed via `git diff --stat` against HEAD):

  | mutation | caught by |
  |---|---|
  | swap the directory-write and manifest-upsert order | `test_directory_lands_even_when_the_manifest_upsert_fails` (asserts the directory exists even when the upsert fails) |
  | let `InstallError` propagate out of `install()` | 5 tests fail with an uncaught `install.InstallError` |
  | copy only `SKILL.md`, not the full subtree | `test_chosen_pattern_lands_with_tcs_prefix_and_full_subtree` (`FileNotFoundError` on the `reference/` file) |
  | hash the catalogue's pre-rename bytes, not the installed file's | `test_sha256_in_report_matches_independently_computed_hash_of_installed_file`, built for exactly this |
  | treat a version-stale-but-unedited pattern as eligible for a write | `test_present_stale_but_unedited_pattern_is_failed_and_untouched`'s digest |
  | report `failed` correctly while still overwriting the file on disk | both present-and-anything-else tests' digests, not their report-channel assertions |

  Three more, run after the bundle/CRLF fix round to confirm it holds and
  introduced no regression — reproducing already-known defects rather than
  finding new ones, which is the point of re-running them:

  | mutation | caught by |
  |---|---|
  | revert the rename regex to `.*$` (reintroduce the \r-eating defect) | the restored strict CRLF assertion |
  | make `install()` ignore its `bundle` argument, always use the default | `test_explicit_bundle_reaches_the_manifest` |
  | revert the frontmatter-open check to `startswith("---\n")` | the CRLF test (whole pattern lands in `failed`, not `installed`) |

  **The lesson this task leaves behind, worth carrying into T3.4**: a
  reviewer's own corrected-and-verified sample can still carry a defect
  invisible to its own verification method — `yaml.safe_load` tolerates
  mixed line endings, and a body-byte-identical assertion does not look at
  the one line being intentionally rewritten. Both checks were real; neither
  could see this. What found it was an implementer running the real
  behaviour against a concrete fixture and reporting the discrepancy instead
  of assuming the spec was right — but the first instinct on finding it was
  still wrong (weaken the test to match), which is exactly why flagging it
  rather than silently "fixing" the test mattered.

  **A third round, 2026-10-05, found by a reviewer's mutation harness
  rather than by any test here.** `11e0adf` fixes it: a module-level
  `DEFAULT_BUNDLE_VERSION = _bundle_version()` read `plugin.json` at IMPORT
  time, which made `install.py` the first module in this component set
  that could not be loaded from a copy via
  `importlib.util.spec_from_file_location` — `manifest.py`, `guard.py` and
  `detect.py` all support it, and T3.1/T3.2 found genuine survivors that
  way. No test in this file caught it, because every test here imports the
  REAL module from its REAL location; the defect is invisible from inside
  this repository and only surfaces to a harness that relocates the file.
  `bundle`'s default is now resolved lazily, `if bundle is None`, inside
  `install()` itself — `DEFAULT_CATALOGUE_DIR` stays a module-level
  constant because a path expression has no I/O and is never fatal to
  import, even wrong. No test changed; the resolved value is identical.
  Whole suite unchanged at 1127/1/1.

  **The first re-verification of this fix was invalid, and it is worth
  recording why rather than quietly replacing it.** The implementer's first
  pass patched `mod._PLUGIN_JSON`, `mod._PLUGIN_ROOT` and
  `mod.DEFAULT_CATALOGUE_DIR` on the loaded copy, AFTER `exec_module`,
  before running the suite against it — which papers over exactly the
  problem being measured. `bundle`'s derivation still reads `plugin.json`
  relative to whatever `__file__` the copy has, and 20 of 21 tests omitted
  `bundle` entirely, so an HONEST bare copy (no mirror, no post-load
  patching) still produced **16 failed, 5 passed**, every failure the same
  `FileNotFoundError` — the fix had moved the failure from import time to
  call time, one layer down, and the "all six caught" report was an
  artefact of a harness that silently removed the very thing under test. A
  reviewer's own independently-run harness caught the discrepancy; the
  implementer's patched harness did not, because it never saw the failure
  in the first place.

  **The real fix, `fb33573`: an explicit `bundle=TEST_BUNDLE` threaded
  through 17 of the file's 20 `install()` call sites** (one more,
  `test_explicit_bundle_reaches_the_manifest`, already passed its own
  explicit value) — the same
  mechanical shape as T3.2b's `own_installed=frozenset()` through the
  guard's 25 call sites, and audited the same way (grep the diff, confirm
  every site got the explicit value except the two that must not). The two
  left alone, deliberately, both omit `bundle` on purpose because each
  exists to probe the REAL derivation:
  `test_default_catalogue_dir_resolves_to_the_real_templates_patterns_dir`
  (the real `catalogue_dir` default) and
  `test_bundle_defaults_to_the_installed_plugins_own_version` (the real
  `bundle` default). Both are deselected for every copy-based run below —
  not an unexplained exclusion, but the direct consequence of a fact the
  implementer verified: Python fixes a function's default-parameter VALUE
  at definition time, so even `DEFAULT_CATALOGUE_DIR`'s path expression
  (never fatal, unlike the `plugin.json` read) is already bound to whatever
  `__file__` the copy had when `exec_module` ran, and no post-load
  attribute patch can retroactively change it. That binding is real and
  permanent for a relocated copy; it is not a defect, and these two tests
  are the ones that would legitimately fail from one regardless of any
  mutation.

  **Re-verified properly: the baseline first, then all six mutations
  against that SAME baseline, same harness, no patching.** A bare copy
  (`spec_from_file_location`, `sys.modules["install"]` injection, no
  mirrored `plugin.json`/`templates/`, nothing patched after load) now
  runs the baseline at **19 passed, 2 deselected** — confirmed before
  running anything else. Each of the six, applied to a fresh copy of the
  real file and run against that identical harness:

  | mutation | result | caught by |
  |---|---|---|
  | swap directory-write and manifest-upsert order | 1 failed, 18 passed, 2 deselected | `test_directory_lands_even_when_the_manifest_upsert_fails` |
  | let `InstallError` propagate out of `install()` | 5 failed, 14 passed, 2 deselected | uncaught `install.InstallError` |
  | copy only `SKILL.md`, not the full subtree | 1 failed, 18 passed, 2 deselected | `test_chosen_pattern_lands_with_tcs_prefix_and_full_subtree` |
  | hash the catalogue's pre-rename bytes, not the installed file's | 3 failed, 16 passed, 2 deselected | `test_sha256_in_report_matches_independently_computed_hash_of_installed_file` |
  | treat a version-stale-but-unedited pattern as eligible for a write | 1 failed, 18 passed, 2 deselected | `test_present_stale_but_unedited_pattern_is_failed_and_untouched`'s digest |
  | report `failed` correctly while still overwriting the file on disk | 2 failed, 17 passed, 2 deselected | both present-and-anything-else digests |

  Every row's pass/fail/deselected count is against the SAME 19/0/2
  baseline, in the SAME harness, so each verdict is actually comparable to
  it — the thing the first attempt's patched harness could not provide,
  because its own baseline was never honestly established. `install.py` is
  now mutation-testable from a relocated copy the same way `manifest.py`,
  `guard.py` and `detect.py` are, with no mirror and no patching.

- [ ] **T3.4 The update path, with divergence handling** `[activity: backend-api]`

  **All three pre-dispatch gaps are CLOSED, 2026-10-05**, in
  `[ref: SDD/Interface Specifications/Data model: the update path (C5's second verb)]` — read that
  section before the steps below; it is what to brief from. Two were settled by evidence once T3.3
  landed and one was Marcus's call:

  - **The signature existed nowhere.** Now
    `update(repo_dir, *, catalogue_dir, bundle, decide=_decline) -> UpdateReport`, with four
    channels mirroring `InstallReport` — `refreshed`, `declined`, `current`, `failed`. **No `names`
    parameter**: F8's first criterion forbids re-deriving a selection, so the manifest is the only
    input about what to act on. `bundle` was promoted to a parameter during T3.3, so this task
    inherits it rather than repeating the derivation.
  - **Who prompts: a `decide` callback, defaulting to decline.** `update()` lives in `install.py`,
    which has no interactive surface, so C3 supplies a callback that prompts and a test supplies a
    stub. Because the **default declines**, ADR-4's "an unanswered prompt cannot destroy local work"
    is held by this module and is mutation-testable, rather than living in C3's prose where nothing
    can check it. A two-phase report-then-apply API was rejected as the shape of the `report_only`
    parameter deleted from `install()`.
  - **Which population: both triggers, and only one of them asks.** The contradiction in step 2
    below is resolved by the three-state table in the contract. Version behind with a **matching**
    hash refreshes **without asking**, because nothing local can be lost — ADR-4's own rationale is
    that "overwriting is safe precisely when it is uninteresting". A hash that **differs** is
    diverged and always asks. `install()` routes every present-but-not-current pattern to `failed`
    naming `update`, so whatever `update()` declined to own would have had no owner at all.

  **T3.4's TDD gate returned BLOCK on 2026-10-05**, with one contract hole and one test that a
  named mutation survives. Both are closed; four further tightenings are folded in, and all of it
  is a requirement of this task.

  - **The contract hole: a pattern the catalogue no longer carries.** The three states are defined
    by two comparisons that *both* presuppose the catalogue still has the pattern, so an upstream
    removal had no row. Settled as `failed` with nothing touched, following the convention
    `install()` already uses for an unreadable catalogue `VERSION`
    `[ref: SDD/Interface Specifications/Data model: the update path (C5's second verb), decision 7]`.
    **Add a test**: seed a manifest entry for a name absent from `catalogue_dir`, assert it lands in
    `failed` and in none of `refreshed`, `current` or `declined`, and that a digest over its
    installed directory is unchanged. This is **not** the missing-*installed*-directory case —
    that is the installed side, this is the catalogue side, and neither covers the other.

  - **The diff assertion as first written survives the mutation it was aimed at.** "The diff
    contains the user's edit" passes even when the diff is computed against the catalogue's
    **pre-rename** bytes, because that diff contains the edit *too* — just additionally polluted
    with a `-name: <bare>` / `+name: tcs-<bare>` hunk. Verified by construction. So it must **also**
    assert the diff contains **no `name:` hunk** — no line matching `^[-+]name:`. And build the
    expected catalogue-as-installed bytes as a **hand-written literal** with the `tcs-` prefix
    already applied, never by calling the same rename helper `update()` uses: a shared bug in that
    helper would otherwise pass both sides.

  - **Pin the diff the REPORT carries, not only the one `decide` received.** Found on the gate's
    second pass and it survives everything else: the diff assertion above checks what is passed
    **into** `decide(name, diff)`, and nothing checks what lands in `UpdateReport.declined[name]`'s
    own `unified_diff` field. A mutation that computes the diff correctly for the callback and then
    stores something else in the report — an empty string, a stale value, the pre-rename diff —
    passes every test in this plan. That value is what a later advisory shows the user
    `[ref: SDD/Runtime View/Primary Flow, step 9]`, so a wrong one is an externally visible bug, not
    an internal detail. Assert `report.declined[name][1]` equals the diff the recording callback
    actually received, **or** re-derive it the same hand-written-literal way.

  - **The catalogue-removal fixture's installed directory must EXIST, with real content.** Otherwise
    it collapses into the missing-installed-directory case and reports `failed` for the wrong reason,
    with no test able to tell the difference — and the "digest over its installed directory is
    unchanged" assertion is vacuous when there is no directory to digest. The two fixtures are exact
    inverses and must be built as such: **catalogue-removal** is installed present + catalogue
    absent; **missing-directory** is installed absent + catalogue present. Never both absent.

  - **The hand-crafted "user's edit" must not itself contain a line starting with `name:`**, or the
    `^[-+]name:` assertion is checking something other than what it was written for.

  - **"`decide` was not called" must assert an empty call list, not an absent name.** Use a callback
    that records every invocation and assert the list is `[]`, with **one pattern per call** so there
    is no ambiguity about which pattern would have triggered it.

  - **F8's third criterion applies to the no-prompt refresh too**: assert `version_after` equals the
    catalogue `VERSION` on the version-behind-hash-matches path, not only where `decide` returned
    `True`.

  - **"Unchanged" must be a literal comparison, twice over.** For a declined pattern, digest the
    **manifest file's bytes** before and after, or deep-compare the `PatternEntry` fields — not an
    unspecified "entry unchanged". That is what catches a mutation reporting `declined` correctly
    and writing the manifest anyway. The default-`decide` test must pass **no callback argument at
    all** rather than an explicit decliner, and carry the same digest.

  - **Recompute the expected hash independently** on the refresh path, mirroring
    `test_sha256_in_report_matches_independently_computed_hash_of_installed_file`, rather than
    trusting a value `update()` produced.

  **The byte-identical guarantee and the `reference/` limit are not in conflict, and the test
  module's docstring must say why.** They are different rows. The byte-identical guarantee is the
  **hash-differs** row, where `decide` returned `False` and the whole directory is left alone,
  `reference/` included. "Replaced without a prompt" is the **version-behind, hash-matches** row,
  where the refresh is unconditional and overwrites the full directory including a locally edited
  `reference/` file. Both hold because **the hash never covered `reference/`**, so a
  `reference/`-only edit cannot put the pattern into the hash-differs row at all. That fixture is
  therefore: version stale, `SKILL.md` hash **matching** the manifest, a `reference/` file
  hand-edited — then assert the refresh overwrites it. ADR-4's accepted limit made visible rather
  than discovered `[ref: SDD/Architecture Decisions/ADR-4, "Trade-offs accepted"]`.

  1. Prime: Read ADR-4 `[ref: SDD/Architecture Decisions/ADR-4]` including its stated limit — the
     hash covers `SKILL.md` only, so a locally edited reference file is replaced without a prompt,
     and that is deliberate rather than an oversight to fix here.
  2. Test: `update` acts on **every** pattern the manifest records and asks nothing about the
     selection — no scan, no questions (F8's first criterion), and **no `names` argument exists** to
     pass one. Then, per the contract's three-state table: a pattern whose version is behind **and
     whose hash still matches** is refreshed **without any call to `decide`** — assert `decide` was
     not called at all for it, which is the only way to pin that an uninteresting overwrite does not
     interrupt the user; a pattern whose installed hash **differs** calls `decide(name, diff)` with
     a unified diff whose body shows the user's edit, and refreshes only on `True`; the **default**
     `decide` declines, so calling `update()` with no callback refreshes no diverged pattern and
     leaves every local file byte-identical — prove that with a digest, since this is ADR-4's
     guarantee and it now lives in the library; after a refresh, each pattern's manifest version
     equals its catalogue `VERSION` (F8's third criterion and SDD/AC-17); declining leaves the local
     file untouched **and** the manifest entry unchanged, so C7's advisory keeps reporting it; and a
     manifest entry whose directory is **missing** lands in `failed`, not `refreshed`.
  3. Implement: the `update` verb in `lib/install.py`, divergence detection against the manifest
     hash, and the `difflib` unified diff.
  4. Validate: `python3 -m pytest -q`; exercise both answers — overwrite and skip — and assert the
     resulting manifest in each case.
  5. Success:
     - [ ] Only drifted patterns refreshed, selection untouched `[ref: PRD/F8 1st]`
     - [ ] Divergence asks before replacing, skip is the default `[ref: PRD/F8 2nd; SDD/ADR-4]`
     - [ ] Post-refresh versions match the catalogue `[ref: PRD/F8 3rd; SDD/AC-17]`

- [ ] **T3.5 Phase validation** `[activity: validate]`

  **Audited 2026-10-05 before dispatch; four corrections.** Three of the five components this task
  validates were built after it was written, and the design moved under it.

  1. **Its central property was written against a design that no longer exists.** This task said to
     assert that "no file was created at all before the guard completed", because "a test that only
     checks the end state would pass even if the installer wrote and then rolled back". Measured
     against the delivered C5: `install()` takes **pre-approved names** and so never receives a
     colliding one; `install.py` **does not import `guard`**, so it cannot perform — or skip — a
     check it does not have; its only `shutil.rmtree` calls are on **its own** temp directory; and
     it never writes for a present-but-not-current pattern at all
     `[ref: SDD/Interface Specifications/.../"install() is purely additive"]`. **There is no
     rollback path to catch.** The failure mode this property guards against cannot occur.

     What remains, and what to assert instead:

     - **`install()` writes only for names it is given** — already covered by T3.3's
       `test_nothing_unchosen_is_written`; cite it rather than duplicating it.
     - **`install.py` does not import `guard`** — a one-line structural assertion, and it is what
       makes "the installer cannot write before a check" true *by construction* rather than by
       behaviour. That is a stronger guarantee than the original property and cheaper to hold.
     - **The sequence itself — `check()` completes before `install()` is called — belongs to C3 and
       cannot be validated in this phase**, because C3 does not exist until Phase 4. Say so here
       rather than asserting something weaker and calling the property discharged. Carry it to
       Phase 4's validation task.

  2. **AC-9 is not wholly a Phase 3 criterion and should not be cited as one.** It reads "the
     install reports its writes, states that it did not commit, **and commits only when the user
     accepts**". The first two halves are C5's and are covered. The third is C3's: `install()`
     reports `committed: False` always, and the offer is a skill's
     `[ref: SDD/Interface Specifications/Data model: the install plan and report (C5), decision 4]`.
     Validate the first two halves here and carry the third to Phase 4.

  3. **"install, guard, manifest and update suites" names four things that live in three files**,
     and the naming is a known trap — T3.3 had to be told explicitly not to put C5's tests in the
     manifest's file. Name them:
     - `tests/test_patterns_guard.py` — C4, the collision guard (54 tests)
     - `tests/test_patterns_install.py` — **C6, the manifest store**, despite the name (24 tests)
     - `tests/test_patterns_installer.py` — **C5, the installer *and* `update()`** (21 tests before
       T3.4)

  4. **"Both legs, per leg" means report pytest and bats separately, each with its own figure.** The
     bats total is **1187 across four suites** — `tcs-git-helpers` 835, `tcs-helper` 330,
     `tcs-issues` 7, `tcs-patterns` 15 — and `plugins/tcs-helper/tests/bats` alone is **not** the
     bats leg. State the four numbers, not a sum, so a regression in one suite cannot hide in the
     total.

  - Success: the three test files above green, reported per leg; `install()` proven to write only
    for names it is given and `install.py` proven not to import `guard`; the C3-owned sequence and
    commit-offer properties explicitly deferred to Phase 4 rather than silently dropped
    `[ref: SDD/AC-7, AC-10, AC-12, AC-17; AC-9 first two halves only]`
