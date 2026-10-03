---
title: "Phase 1: The catalogue and its maintainer contract"
status: in_progress
version: "1.0"
phase: 1
---

# Phase 1: The catalogue and its maintainer contract

## Phase Context

**GATE**: Read all referenced files before starting this phase.

**Specification References**:
- `[ref: SDD/Building Block View/Directory Map]` — exactly where the 21 directories go
- `[ref: SDD/Interface Specifications/Data model: catalogue entry]` — the `VERSION` file contract
- `[ref: SDD/Architecture Decisions/ADR-3]` — per-pattern integer versions, no central file
- `[ref: SDD/Architecture Decisions/ADR-9]` — the per-pattern CI rule
- `[ref: SDD/Implementation Examples]` — the CI rule's sed extraction and membership test
- `[ref: PRD/F1]` — four acceptance criteria for the relocation
- `[ref: PRD/F9]` — three acceptance criteria for the gate

**Key Decisions**:
- The relocation is a **rename**, not a rewrite. Content does not change in this phase; the only
  edits are the four broken outward references (T1.3), and they are a separate task so the rename
  commit stays clean and reviewable as R100. Three of the four were already broken before this spec
  existed and the relocation neither causes nor fixes them; they are repaired here because this is
  the task that reads every one of these files.
- `VERSION` is a bare integer, not semver. A prose body has no API for "breaking" to describe, and
  the only question asked of it is whether two numbers differ.
- The gate is **per directory**, not per bundle. The existing bundle table would pass when the
  wrong pattern's marker was bumped, which is the exact failure it exists to prevent.

**Dependencies**:
- None. This phase is the foundation; every later phase reads the catalogue.

---

## Tasks

Establishes the catalogue as the single source of truth for the 21 patterns, and the maintainer
contract that keeps a distributed copy detectably stale rather than silently stale.

- [x] **T1.1 The 21 patterns relocated as pure renames** `[activity: refactor]`

  1. Prime: Read the directory map `[ref: SDD/Building Block View/Directory Map]` and confirm the
     current layout with `ls plugins/tcs-patterns/skills/`. It holds 21 directories and 80 tracked
     files and nothing else — in particular there is **no** `skills/REFERENCES.md`. Three citations
     point at one; it has never existed in this repository (`git log --diff-filter=ADR --all --
     '*REFERENCES.md'` returns nothing), so there is nothing to move and T1.3 owns the repair.
  2. Test: Assert the numbers that actually move. The pre-move baseline, measured 2026-10-03, is
     **98 inventory entries (80 skills, 18 agents)**, of which exactly 21 are `tcs-patterns` skills,
     and **810 passed / 1 skipped / 1 deselected** on the pytest leg. After the move the inventory
     must read **77 entries (59 skills, 18 agents)** with no `tcs-patterns:` skill left in the list,
     and the pytest leg must be unchanged. Assert directly against the tree that
     `templates/patterns/` holds 21 `SKILL.md` files and 80 tracked files in total, because
     `report.py` globs `plugins/*/skills/*/SKILL.md` one level deep and cannot see a catalogue at
     all. Assert `git diff -M --summary` reports a rename for every one of the 80 files. Assert all
     21 frontmatter blocks still parse with a YAML parser — not paranoia: ten skill descriptions in
     this repository once stopped parsing while `claude plugin validate` passed over all ten.

     The report's "Unreachable skill files" section is **already empty** today, so treat it as a
     regression guard and never as evidence the move worked. A criterion whose value is identical
     before and after the change cannot distinguish success from doing nothing.
  3. Implement: `git mv plugins/tcs-patterns/skills/<name> plugins/tcs-patterns/templates/patterns/<name>`
     for all 21. That is the whole move; there is no loose file beside the 21 directories. Move
     **directories**, not files, so each subtree travels in one rename and `git log --follow`
     survives. Confirm no `.gitkeep` or hidden file is left behind before relying on git not
     tracking empty directories — verified none on 2026-10-03, so a hit means something changed.
  4. Validate: `python3 scripts/observability/report.py` and read the `entries found` line;
     `git diff --name-status -M <parent> HEAD | grep -c '^R100'` for the rename count; `python3 -m
     pytest -q` against the baseline above. Do not use `claude plugin details` — it resolves the
     installed cache copy and cannot see this change.

     Two command-level traps, both hit for real on 2026-10-03. `git diff -M --summary` renders a
     rename as ` rename a/b (100%)`; the literal token `R100` exists only in `--name-status`
     output, so `--summary | grep -c R100` returns 0 on a flawless rename and reads as total
     failure. And **run every assertion against the committed tree, never the working tree**: a
     check written as `git diff … HEAD` compares the working tree to HEAD, so it is green while the
     move is pending and 0 the instant it is committed. Asserted that way it passes exactly once,
     at a moment when the task is unfinished, and is red forever after.
  5. Success:
     - [ ] All 80 files reported as renames at 100% similarity `[ref: PRD/F1 4th]`
     - [ ] Inventory walk falls from 98 entries to 77, with no `tcs-patterns:` skill remaining, and
           `templates/patterns/` holds 21 `SKILL.md` and 80 tracked files `[ref: PRD/F1 2nd]`
     - [ ] The report's unreachable list stays empty — a guard, not evidence, since it was already
           empty `[ref: SDD/Quality Requirements]`
     - [ ] No test moves. If one does, the premise that nothing reads the real tree was wrong —
           stop and investigate rather than updating the test `[ref: SDD/Quality Requirements]`

- [x] **T1.2 A `VERSION` file per pattern** `[activity: data-architecture]`

  1. Prime: Read the catalogue entry contract `[ref: SDD/Interface Specifications/Data model: catalogue entry]`
     and ADR-3's rationale `[ref: SDD/Architecture Decisions/ADR-3]`.
  2. Test: Every one of the 21 directories contains a `VERSION`; each holds exactly one line; each
     parses as a positive integer; a pattern without one is reported as unknown rather than
     drifted (the consuming assertion lands in Phase 4, the file-shape assertion lands here).
  3. Implement: Write `templates/patterns/<name>/VERSION` containing `1` for all 21. Add the
     test that enumerates the directories and asserts the file's presence and shape, so a pattern
     added later without a version fails the suite rather than the user.
  4. Validate: `python3 -m pytest -q`; confirm the count of `VERSION` files equals the count of
     `SKILL.md` files under `templates/patterns/`.
  5. Success:
     - [ ] 21 `VERSION` files, each a single positive integer `[ref: SDD/Interface Specifications]`
     - [ ] A new pattern directory without a `VERSION` fails the suite `[ref: SDD/Risks/Technical Debt]`

- [ ] **T1.3 The four broken outward references repaired** `[activity: refactor]`

  1. Prime: Read all **four** sites. The first three cite a `REFERENCES.md` that has never
     existed in this repository, verified 2026-10-03 against the working tree and against
     `git log --diff-filter=ADR --all -- '*REFERENCES.md'`, which returns nothing. They have always
     resolved to nothing, and the relocation neither causes nor fixes that.

     | Site | Citation | Resolves to |
     | --- | --- | --- |
     | `hexagonal/reference/testing-hex-arch.md:3` | `../../REFERENCES.md` | catalogue root — absent |
     | `hexagonal/reference/hexagonal-layers.md:17` | `../REFERENCES.md` | pattern root — absent |
     | `ddd/reference/testing-by-layer.md:5` | `../../REFERENCES.md` | catalogue root — absent |
     | `obsidian-plugin/SKILL.md:220` | `../../../../docs/guides/tcs-patterns.md` | repo root — exists |

     The obsidian target does exist and resolves from the working tree; it resolves to nothing from
     the installed plugin cache, which is issue #163's second instance.

     A catalogue-level `REFERENCES.md` is **not** the repair. C5 copies one pattern directory
     `[ref: SDD/Runtime View]`, so anything a pattern cites above its own directory is unreachable
     the moment it is installed — the same defect with a version number attached. Two patterns
     (`event-sourcing`, `observability`) already own a per-pattern `reference/references.md`, which
     is the shape that survives installation.
  2. Test: Two rules, and they are **not** the same rule. For every file under
     `templates/patterns/<name>/`: no relative path may resolve **above its own pattern directory**
     — per pattern, not per catalogue, because the pattern directory is the unit C5 copies and a
     catalogue-relative link is dead in a consumer repository — and every remaining relative path
     must resolve to a file that exists.

     The two rules land on different sites, so both are genuinely exercised. `../../REFERENCES.md`
     from `hexagonal/reference/` resolves to `templates/patterns/REFERENCES.md` and **escapes**;
     `../REFERENCES.md` from the same directory resolves to `templates/patterns/hexagonal/
     REFERENCES.md`, which stays **inside** the pattern and is merely unresolvable. "Contains
     `../`" is therefore necessary but not sufficient for the escape rule — resolve the path and
     compare against the pattern root.

     **Two checks are needed, because the four sites are caught by different code.** Only site 4 is
     a markdown link. Sites 1-3 are bare relative paths inside inline code spans, with no link
     syntax at all:
     - extend `tests/test_docs_links.py`'s surfaces to the catalogue for the markdown-link form.
       Its `DOC_FILES` is `docs/**/*.md` minus `docs/XDD/` plus the two root files, which is why
       none of the four was ever caught.
     - add a check for bare paths in code spans. Note that `test_docs_links.py` **blanks inline
       code spans deliberately** (`_linkable_lines`), because `docs/reference/xdd.md` quotes the
       plan checklist format literally and would false-positive. So the new check must inspect
       exactly what that one discards, without reintroducing its false positives.

     Both checks must fail together in one suite run, so partial coverage cannot read as a pass.

     Four controls, and the fourth is the one that proves the check is not a blunt instrument:
     - **A** an escaping path in a code span → the code-span check FAILS
     - **B** a non-escaping path in a code span naming a file that does not exist → the resolve
       check FAILS
     - **C** an escaping markdown link → the link check FAILS
     - **D** a path containing `../` that resolves **inside** the pattern and exists → both checks
       PASS. Without D, a check that rejects every `../` passes A, B and C and is still wrong.
  3. Implement: Keep the attribution, drop the dead pointer. In `testing-hex-arch.md:3` and
     `testing-by-layer.md:5` the clause offering sources at `../../REFERENCES.md` goes and the
     attribution to Valentina Jemuović's Use Case Driven Design stays; in `hexagonal-layers.md:17`
     the pointer is the entire sentence, so the line goes. **Add no source citations at all** — the
     sources were never in this repository, and a guessed citation inside a sources list is worse
     than no list. If a reader needs UCDD sources later, that is a per-pattern
     `reference/references.md` written from material somebody actually has, and it is a separate
     piece of work. Today exactly two patterns carry one, `observability` and `event-sourcing`;
     that set must be the same when this task ends. Replace the obsidian citation with an inline statement of what the
     guide says about the hook's scope gate and the `CLAUDE_ALLOW_ESLINT_DISABLE=1` escape hatch, so
     the pattern is self-contained once copied into a consumer repository.
  4. Validate: `python3 -m pytest -q`; the new link test fails if any escaping path is reintroduced.
  5. Success:
     - [ ] No markdown link, and no code-span path beginning `../`, escapes its own pattern
           directory `[ref: PRD/F1 3rd]`
     - [ ] Every markdown link, and every code-span path beginning `../`, resolves to a file that
           exists `[ref: PRD/F1 3rd]`
     - [ ] A bare code-span path is **not** treated as a link, and the reason is recorded in the
           test module — measured over the catalogue, 188 file-like paths appear in code spans:
           80 resolve from the containing file, 39 from the pattern root, 69 from neither, and the
           69 include MIME types, URL schemes, GitHub slugs and illustrative consumer paths. One
           syntax carries six meanings and no mechanical rule separates them `[ref: SDD/Risks]`
     - [ ] The set of patterns carrying a `reference/references.md` is unchanged — exactly
           `observability` and `event-sourcing`, none under `hexagonal/` or `ddd/` — and no
           existing `references.md` gained a line `[ref: SDD/Risks]`
     - [ ] The obsidian pattern is self-contained for a consumer repository `[ref: SDD/Risks/Known Technical Issues]`

- [ ] **T1.4 The per-pattern CI gate rule** `[activity: platform-operations]` `[parallel: true]`

  1. Prime: Read the existing gate and its bundle table
     (`plugins/tcs-git-helpers/scripts/ci/check-hook-bundle-version.sh`), ADR-9
     `[ref: SDD/Architecture Decisions/ADR-9]`, and the rule sketch
     `[ref: SDD/Implementation Examples]`. The gate already runs on every pull request via
     `.github/workflows/hook-bundle-version-check.yml`; no workflow change is needed.
  2. Test: bats cases over a synthetic diff range — a changed pattern file **without** its
     `VERSION` fails; the same change **with** its `VERSION` passes; bumping a *different*
     pattern's `VERSION` still fails (this is the case the bundle table would have passed, and the
     reason the rule exists); a change touching no pattern leaves the gate silent; the three
     existing bundles keep behaving exactly as before. Remember a bare `[[ ]]` only fails a bats
     test as the body's last statement — assert substrings through a `grep -qF` helper.
  3. Implement: Add the per-directory rule to the existing script. bash 3.2, no associative arrays,
     shellcheck-clean.
  4. Validate: `bats` leg for the gate's suite; run the gate locally against this branch's own
     range; `shellcheck` on the changed script.
  5. Success:
     - [ ] Pattern changed without its own `VERSION` → non-zero exit naming the pattern and the marker `[ref: PRD/F9 1st]`
     - [ ] Pattern changed with its `VERSION` → passes `[ref: PRD/F9 2nd]`
     - [ ] Wrong pattern's `VERSION` bumped → still fails `[ref: SDD/Architecture Decisions/ADR-9]`
     - [ ] A change touching no pattern → gate silent `[ref: PRD/F9 3rd]`
     - [ ] The three pre-existing bundles unaffected `[ref: SDD/Architecture Decisions/ADR-9]`

- [ ] **T1.5 Phase validation** `[activity: validate]`

  Run both legs on a **clean, committed tree** — nothing staged, nothing dirty — because an
  assertion that reads `git diff` or the index answers differently before and after a commit, and
  the difference is invisible when a leg is run immediately after an edit. `python3 -m pytest -q`
  (baseline 810 passed, 1 skipped, 1 deselected; Phase 1 adds 6, so 816) and the bats suites,
  reporting each leg's numbers separately rather than an aggregate. Run `claude plugin validate plugins/tcs-patterns` as a smoke
  test only — it validated the broken layout cleanly in a previous spec and proves nothing about
  discovery. Verify the relocation with `python3 scripts/observability/report.py`, which reads the
  working tree; do **not** use `claude plugin details`, which resolves the installed cache copy and
  cannot see this change. If a live session check is wanted, it must be a **new** session: the
  plugin cache is stale within the session that updated it.

  - Success: both legs green per leg; inventory walk shows the catalogue; the gate passes on this
    branch `[ref: SDD/Acceptance Criteria/AC-1, AC-2, AC-13]`
