---
title: "Phase 5: The skills, the docs, end to end"
status: pending
version: "1.0"
phase: 5
---

# Phase 5: The skills, the docs, end to end

## Phase Context

**GATE**: Read all referenced files before starting this phase.

**Specification References**:
- `[ref: SDD/Interface Specifications/Process contract: the skills]` — the four verbs and the
  catalogue reader's argument
- `[ref: SDD/Runtime View/Primary Flow]` — all nine steps, which this phase finally joins up
- `[ref: SDD/Cross-Cutting Concepts/User Interface & UX]` — three screens at most, costs shown per
  entry at the moment of choosing
- `[ref: SDD/Runtime View/Error Handling]` — the rows owned by the interview: not a git repository,
  partially unreadable target
- `[ref: PRD/F2 4th, F3, F4 3rd-4th]` and `[ref: PRD/F10]`
- `[ref: SDD/Risks and Technical Debt/Known Technical Issues]` — the `principles.md:167` correction

**Key Decisions**:
- **The interview asks only what the gates opened** and presents costs per entry. The UX bar is
  `claude init`, not an interview; the gates are what enforce it.
- **The catalogue reader is one skill serving 21 bodies.** It is justified against the granularity
  rules in `docs/about/skill-and-agent-design.md` because the alternative is 21 descriptions in
  every session's listing, which is the problem this spec exists to remove.
- **Both changelogs or the push fails.** `docs-sync` requires a root `CHANGELOG.md` entry for
  user-facing change; a previous spec lost a push to exactly this. Run `check-docs-sync.sh`
  locally before pushing, not after CI complains.

**Dependencies**:
- Phases 1-4 all complete. The interview needs detection and installation; the end-to-end test
  needs the advisory too.

---

## Tasks

Delivers the user-facing surface and the proof that the nine steps work as one flow rather than as
four passing test suites.

- [ ] **T5.1 The patterns-setup skill** `[activity: frontend-ui]`

  1. Prime: Read the skill contract
     `[ref: SDD/Interface Specifications/Process contract: the skills]`, the full flow
     `[ref: SDD/Runtime View/Primary Flow]`, and the UX section
     `[ref: SDD/Cross-Cutting Concepts/User Interface & UX]`. Read
     `plugins/tcs-helper/skills/observability-setup/SKILL.md` for the verb-and-abort shape; note
     that its stance on committability is the opposite of ours and why.
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
     `argument-hint: "<install|update|remove|status> [path]"`.
  4. Validate: `python3 -m pytest -q`; `claude plugin validate plugins/tcs-patterns` as a smoke
     test; walk the skill by hand against a fixture repository — green tests over skill Markdown
     have missed defects here before that a walkthrough found at step one.
  5. Success:
     - [ ] Frontmatter parses; description is a routing contract `[ref: SDD/Quality Requirements]`
     - [ ] Proposal shows per-entry listing cost; baseline listed separately from recommendations `[ref: PRD/F2 4th, 5th; SDD/AC-16]`
     - [ ] Commit is offered and never performed unasked `[ref: PRD/F4 3rd, 4th; SDD/ADR-8]`
     - [ ] A walkthrough from a clean fixture reaches an installed selection `[ref: SDD/Runtime View/Primary Flow]`

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
