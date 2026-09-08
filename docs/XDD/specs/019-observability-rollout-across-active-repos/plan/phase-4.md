---
title: "Phase 4: The command, the rollout, and the gates"
status: pending
version: "1.0"
phase: 4
---

# Phase 4: The command, the rollout, and the gates

## Phase Context

**GATE**: Read all referenced files before starting this phase.

**Specification References**:
- `[ref: SDD/Runtime View — Primary Flow]` — the install sequence and its ordering
- `[ref: SDD/Runtime View — Error Handling]` — the full failure table
- `[ref: PRD/User Journey Maps]` — all four journeys, including removal and the foreign-entry path
- `[ref: PRD/Success Metrics]`

**Key Decisions**:
- The sequence is **lock → detect → confirm → write → summarize → release**, and the lock comes
  before *detection* rather than before writing, so two concurrent runs serialize across the whole
  sequence rather than racing between deciding and acting (`git-setup/SKILL.md:96` states the
  reasoning).
- The command exposes a **plan step**: it reports what it would change before changing anything.
  Satori writes first and reports after; `sync-docker` does it the right way round.
- **The command's own artifacts are excluded from its own conflict detection.** Without that, the
  first run reports itself as a pre-existing foreign install — a defect `git-setup` hit and fixed
  (`detect_conflicts.sh:143-158`), and one that is invisible until the very first real use.

**Dependencies**: Phases 1, 2 and 3 complete.

---

## Tasks

Turns the pieces into something a person invokes, puts it into the target repositories, and proves
the whole path end to end.

- [ ] **T4.1 The setup command** `[activity: backend-api]`

  1. Prime: read `plugins/tcs-git-helpers/skills/git-setup/SKILL.md:86-174` — the whole sequence,
     including why the lock is taken where it is `[ref: SDD/Runtime View — Primary Flow]`.
  2. Test: the four journeys from the PRD end to end — install, status, remove, and the
     foreign-entry stop; the plan step reports the intended change and makes none; declining at the
     confirmation leaves the target untouched; the summary names how to undo what was done; the
     first run against a clean target does **not** report itself as a foreign install; a target that
     is not a repository is refused before anything else runs.

     Three assertions an audit found missing everywhere, each about a *translation* the command
     performs rather than about a library's behaviour:
     - **The foreign-entry case exits 0.** Detection returns severity 3 for a conflict, but the
       command must exit 0 — foreign content is a stop condition, not a failure. Nothing else in
       the plan asserts that mapping from detect's 3 to the command's 0, and getting it wrong turns
       a normal outcome into a failed one for anything that checks status codes.
     - **Drift surfaces through `status`.** T1.3 proves the comparator is correct; it does not
       prove the comparator is wired into the verb a person actually runs. Assert that an installed
       bundle behind the marker shows drift in `status` output.
     - **A target that is not a repository is refused with the reason named**, which is the
       command-level half of a criterion whose detection half lives in T2.1.
  3. Implement: `plugins/tcs-helper/skills/observability-setup/SKILL.md` plus the wiring of the
     phase-1 and phase-2 libraries. Install, remove and status are one command with three verbs, not
     three commands.
  4. Validate: `bats` green; the command is exercised through its real entry point, not by calling
     its libraries directly.
  5. Success: `[ref: PRD/F1]`, `[ref: PRD/F2]`, `[ref: PRD/User Journey Maps]`;
     `[ref: SDD/SDD-AC-1]` (command-level refusal), `[ref: SDD/SDD-AC-4]` (exit 0 on foreign
     entries), `[ref: SDD/SDD-AC-15]` (drift reaches `status`)

- [ ] **T4.2 Rollout to the target repositories** `[activity: validate]`

  1. Prime: read the locations config format `[ref: SDD/ADR-6]`. **The real repository names and
     paths belong only in that gitignored file — never in a commit message, a test fixture, or any
     document in this spec.**
  2. Test: this task's verification is observational rather than unit-level. For each target, after
     setup: the write path is confirmed gitignored; the target's tracked files show no change
     (`git status` clean); a session in that target produces records; the record's `repo` field
     matches what the config labels.
  3. Implement: run the command against each target; add each to the locations config.
  4. Validate: `report.py` with no arguments reads every configured source and reports each
     separately. Before this step, **remove the three test-fixture record directories** identified
     in the SDD's Known Technical Issues, so they cannot be counted — they carry plausible-looking
     records under names a pytest fixture produced.
  5. Success: all intended targets recording, verifiable individually `[ref: PRD/Success Metrics]`

- [ ] **T4.3 End-to-end validation and the collection gate** `[activity: validate]`

  1. Run the full suites: `pytest -q` and `bats plugins/*/tests/bats`.
  2. Verify every SDD acceptance criterion has passing evidence, and that each one's evidence is a
     test rather than a prose claim. Where only prose exists, say so rather than marking it covered
     — spec-018's evidence map found four criteria in that state and naming them was more useful
     than quietly counting them.
  3. Confirm the safety property directly rather than by inference: in each target, assert that
     `git check-ignore` succeeds for every path this feature wrote, and that `git status` reports
     nothing.
  4. **Record the collection period's end date in the spec README.** This is the PRD's one carried
     open question. Without a date, "evaluate later" is the failure mode this spec exists to
     correct, and the mode spec-018 already fell into once.
  5. Success: every SDD acceptance criterion has passing evidence; the collection period has a start
     and a named end `[ref: PRD/Success Metrics]`

---

## Phase Acceptance Criteria

- The command performs all four PRD journeys through its real entry point.
- Every target records, and none shows a change to a tracked file.
- The test-fixture record directories are gone before collection begins.
- The collection period has a written end date, and a plan for what happens on that date.
