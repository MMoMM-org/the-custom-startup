---
title: "Phase 1: The catalogue and its maintainer contract"
status: pending
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
  edits are the three broken outward references (T1.3), and they are a separate task so the rename
  commit stays clean and reviewable as R100.
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

- [ ] **T1.1 The 21 patterns relocated as pure renames** `[activity: refactor]`

  1. Prime: Read the directory map `[ref: SDD/Building Block View/Directory Map]` and confirm the
     current layout with `ls plugins/tcs-patterns/skills/`. Note that `skills/REFERENCES.md` moves
     too — two patterns cite it as `../../REFERENCES.md` and that relative path survives the move
     only if the file travels with them.
  2. Test: Assert the inventory walk reports 0 unreachable skill files under
     `plugins/tcs-patterns/` and 21 catalogue entries; assert `git diff -M --summary` reports a
     rename for every one of the 80 files; assert all 21 frontmatter blocks still parse with a YAML
     parser. The last one is not paranoia — ten skill descriptions in this repository once stopped
     parsing while `claude plugin validate` passed over all ten.
  3. Implement: `git mv plugins/tcs-patterns/skills/<name> plugins/tcs-patterns/templates/patterns/<name>`
     for all 21, and `git mv plugins/tcs-patterns/skills/REFERENCES.md plugins/tcs-patterns/templates/patterns/REFERENCES.md`.
     Move **directories**, not files, so each subtree travels in one rename and `git log --follow`
     survives. Confirm no `.gitkeep` or hidden file is left behind before relying on git not
     tracking empty directories.
  4. Validate: `python3 scripts/observability/report.py`; `git diff -M --summary | grep -c R100`;
     `python3 -m pytest -q` unchanged from baseline.
  5. Success:
     - [ ] All 80 files reported as renames at 100% similarity `[ref: PRD/F1 4th]`
     - [ ] Inventory walk shows 21 catalogue entries, 0 unreachable skill files `[ref: PRD/F1 2nd]`
     - [ ] No test moves. If one does, the premise that nothing reads the real tree was wrong —
           stop and investigate rather than updating the test `[ref: SDD/Quality Requirements]`

- [ ] **T1.2 A `VERSION` file per pattern** `[activity: data-architecture]`

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

- [ ] **T1.3 The three broken outward references repaired** `[activity: refactor]`

  1. Prime: Read all three sites. `templates/patterns/hexagonal/reference/testing-hex-arch.md:3`
     and `templates/patterns/ddd/reference/testing-by-layer.md:5` cite `../../REFERENCES.md`, which
     after T1.1 resolves again because the file moved with them — **verify this rather than assume
     it**. `templates/patterns/obsidian-plugin/SKILL.md:220` cites
     `../../../../docs/guides/tcs-patterns.md`, which already resolves to nothing from the installed
     plugin cache today — issue #163's second instance.
  2. Test: Assert that no file under `templates/patterns/` contains a relative path that escapes
     `templates/patterns/`; assert every intra-catalogue relative link resolves to an existing file.
     Write this as a repository-wide test, because it is the check that would have caught the
     obsidian reference years ago.
  3. Implement: Confirm the two `REFERENCES.md` citations resolve post-move and leave them. Replace
     the obsidian citation with an inline statement of what the guide says about the hook's scope
     gate and the `CLAUDE_ALLOW_ESLINT_DISABLE=1` escape hatch, so the pattern is self-contained
     once copied into a consumer repository.
  4. Validate: `python3 -m pytest -q`; the new link test fails if any escaping path is reintroduced.
  5. Success:
     - [ ] No reference escapes the pattern catalogue `[ref: PRD/F1 3rd]`
     - [ ] Every intra-catalogue relative link resolves `[ref: PRD/F1 3rd]`
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

  Run both legs: `python3 -m pytest -q` and the bats suites, reporting each leg's numbers
  separately rather than an aggregate. Run `claude plugin validate plugins/tcs-patterns` as a smoke
  test only — it validated the broken layout cleanly in a previous spec and proves nothing about
  discovery. Verify the relocation with `python3 scripts/observability/report.py`, which reads the
  working tree; do **not** use `claude plugin details`, which resolves the installed cache copy and
  cannot see this change. If a live session check is wanted, it must be a **new** session: the
  plugin cache is stale within the session that updated it.

  - Success: both legs green per leg; inventory walk shows the catalogue; the gate passes on this
    branch `[ref: SDD/Acceptance Criteria/AC-1, AC-2, AC-13]`
