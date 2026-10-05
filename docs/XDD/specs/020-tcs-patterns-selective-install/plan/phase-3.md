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

- [ ] **T3.1 The manifest store** `[activity: data-architecture]`

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
     - [ ] A single record names every installed pattern with its version `[ref: PRD/F6 1st]`
     - [ ] A later install leaves prior entries unchanged `[ref: PRD/F6 2nd]`
     - [ ] Currency determinable without inspecting pattern files `[ref: PRD/F6 3rd; SDD/AC-17]`
     - [ ] An unparseable manifest is never overwritten `[ref: SDD/Runtime View/Error Handling]`

- [ ] **T3.2 The collision guard** `[activity: backend-api]`

  1. Prime: Read the guard's place in the flow `[ref: SDD/Runtime View/Primary Flow]` step 6 and
     ADR-1's consequence note `[ref: SDD/Architecture Decisions/ADR-1]` — with the prefix the guard
     rarely fires, and it is still the mechanism that keeps a partial install coherent.
  2. Test: A name taken in the repository's own skills is refused with both locations reported; the
     same for the user's global skill directory; the same for a reachable plugin skill; a selection
     with one colliding and two free names installs the two and writes nothing for the third, with
     no rescan (F5's fourth criterion); the guard itself writes nothing under any input.
  3. Implement: `lib/guard.py` — the three namespace checks, returning approved and refused sets
     with the reason and the colliding location for each refusal.
  4. Validate: `python3 -m pytest tests/test_patterns_guard.py -q`; assert via a read-only
     temporary directory that the guard performs no write.
  5. Success:
     - [ ] All three namespaces checked before any write `[ref: PRD/F5 1st-3rd]`
     - [ ] Non-colliding patterns still install, no rescan `[ref: PRD/F5 4th; SDD/AC-10]`

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
