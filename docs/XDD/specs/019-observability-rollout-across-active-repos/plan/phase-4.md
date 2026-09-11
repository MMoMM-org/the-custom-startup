---
title: "Phase 4: The command, the rollout, and the gates"
status: in_progress
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

**Migration of THIS repository — added 2026-09-08 by maintainer ruling.** Before the collection
period starts, this repository's hand-made registration must be migrated to the standard mechanism.
Its current state, measured rather than assumed:

    file:   .claude/settings.json          (NOT settings.local.json, which holds no hooks here)
    env:    CLAUDE_OBSERVABILITY_ENABLED=1
    hooks:  InstructionsLoaded -> $CLAUDE_PROJECT_DIR/plugins/tcs-helper/scripts/observability/log_instructions.sh
            PreToolUse         -> $CLAUDE_PROJECT_DIR/plugins/tcs-helper/scripts/observability/log_skill.sh
            SubagentStart      -> $CLAUDE_PROJECT_DIR/plugins/tcs-helper/scripts/observability/log_agent.sh

Neither the file nor the command namespace matches what ADR-1 and ADR-5 expect, so the old entries
must come out as the new ones go in — otherwise this repository records twice, and it is the one
repository whose data the collection period depends on. Sequence it so recording is never
simultaneously double and never silently off: remove the legacy entries and install the standard
registration in the same operation, then confirm with the `status` verb before trusting the records.
Phase 2's detection classifies this legacy shape distinctly for exactly this reason.

- [ ] **T4.1 The setup command** `[activity: backend-api]`

  **Note added 2026-09-08 while phase 1 shipped, so this is not rediscovered here.** The drift
  comparator T1.3 delivered is
  `_drift_check_observability_bundle <expected_version> [<marker_path>]` — it does NOT fetch the
  expected version itself. The `status` verb must obtain it first, using the same two-line pattern
  `bundle_install.sh:167` already uses:

      expected="$(_read_observability_bundle_version 2>/dev/null)" || expected=""

  This follows existing precedent rather than inventing boilerplate. Note also that the comparator
  drops the mirrored signature's `repo_path` argument (this bundle lives at
  `$HOME/.claude/observability/`, not at a repo-relative `.githooks/`), so do not expect the
  argument order of `drift_check_hook_bundle`. It exits 0 in every case and signals via stdout —
  `OK`, `MISSING`, or `DRIFT:<installed>` — so the `status` verb, not the comparator, decides what
  each state means to the user.

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
     - **A target that is not a repository is refused with the reason named, and exits 0.** The
       exit status is the sibling of the foreign-entry case above and was missing for the same
       reason: both are *normal* outcomes that must not read as failures to anything checking
       status codes. This is the command-level half of a criterion whose detection half is T2.2.
     - **`status` distinguishes three states, not two**: configured and recording, configured but
       silent, and *not configured at all*. The third needs reading the target's settings, which
       no reporting task does — the report sees records, not registrations, so a target where
       setup never ran looks identical to one that ran and recorded nothing.
  3. Implement: `plugins/tcs-helper/skills/observability-setup/SKILL.md` plus the wiring of the
     phase-1 and phase-2 libraries. Install, remove and status are one command with three verbs, not
     three commands.
  4. Validate: `bats` green; the command is exercised through its real entry point, not by calling
     its libraries directly.
  5. Success: `[ref: PRD/F1]`, `[ref: PRD/F2]`, `[ref: PRD/User Journey Maps]`;
     `[ref: SDD/SDD-AC-1]` (command-level refusal), `[ref: SDD/SDD-AC-4]` (exit 0 on foreign
     entries), `[ref: SDD/SDD-AC-15]` (drift reaches `status`), `[ref: SDD/SDD-AC-26]` (three-state liveness)

  **Rulings, 2026-09-11, before T4.1's gate.** Two spec-internal contradictions, resolved by the
  maintainer rather than left to an implementer's guess.

  **(r) The command ships a verb dispatcher at `lib/setup.sh`; `SKILL.md` is a thin wrapper.** The
  SDD's Directory Map (`solution.md:222-227`) lists only `SKILL.md` and `lib/`, following
  `git-setup`, where markdown orchestrates the libraries in prose. Step 4 of this task requires the
  command be "exercised through its real entry point, not by calling its libraries directly", and
  bats cannot exercise a Markdown file. Both statements hold only if a dispatcher exists, so one is
  added: `lib/setup.sh install|remove|status`, taking a target path and a non-interactive `--yes`.
  `SKILL.md` keeps what a script cannot own -- the confirmation at Runtime View step 5 and the
  summary at step 8 -- and calls the dispatcher for everything mechanical. This extends the
  Directory Map rather than contradicting it, and makes "one command with three verbs, not three
  commands" literally true rather than an arrangement of prose. `git-setup` is not a
  counter-precedent: it has no test asserting its own entry point either, which is the gap this
  ruling closes rather than copies.

  **(s) T4.1 implements the legacy migration; T4.2 runs it against this repository.**
  `detect.sh:365` tells the user "setup will migrate this to $HOME/.claude/observability/". Nothing
  performs it. Measured: `registration.py:71` sets `NAMESPACE` to the `$HOME` bundle path and
  `entry_is_ours()` gates removal on it, so `--remove` steps over the legacy entries, whose commands
  point at `$CLAUDE_PROJECT_DIR/plugins/tcs-helper/scripts/observability/`. The migration is also
  cross-file -- legacy lives in `.claude/settings.json`, the standard registration in
  `settings.local.json` -- while `registration.py main()` accepts a single `--settings`. So
  `install`, on a `LEGACY` classification, must remove the legacy entries from the shared file and
  add the standard registration to the local one as one operation, covered by bats against fixtures
  and never against a real repository. Running it against this repository belongs to T4.2, under the
  per-target confirmation this phase adopted. Until then
  `plugins/tcs-helper/tests/bats/observability-registration-matrix.bats` keeps pinning the double
  registration deliberately: when T4.1 lands, that test is meant to change, and a green run there is
  the defect rather than the proof.


- [ ] **T4.2 Rollout to the target repositories** `[activity: validate]`

  1. Prime: read the locations config format `[ref: SDD/ADR-6]`. **The real repository names and
     paths belong only in that gitignored file — never in a commit message, a test fixture, or any
     document in this spec.**
  2. Test: this task's verification is observational rather than unit-level.

     **Before running the command against a target**, confirm `git check-ignore` succeeds for
     **both** the settings path and the backup path, and skip any target where either fails. The
     ordering matters and an audit caught it: T2.5 asserts the backup's ignore status against
     *fixtures*, which are built to spec and always pass, while T4.4 asserts it against *real*
     targets — but by then this task has already written to them. A target that ignores
     `settings.local.json` by name rather than `.claude/` wholesale would receive a committable
     `.bak` and be told about it afterwards.

     After setup, for each target: the target's tracked files show no change (`git status`
     clean); a session in that target produces records; the record's `repo` field matches what
     the config labels.
  3. Implement: run the command against each target; add each to the locations config.
  4. Validate: `report.py` with no arguments reads every configured source and reports each
     separately. Before this step, **remove the three test-fixture record directories** identified
     in the SDD's Known Technical Issues, so they cannot be counted — they carry plausible-looking
     records under names a pytest fixture produced.
  5. Success: all intended targets recording, verifiable individually `[ref: PRD/Success Metrics]`

- [ ] **T4.3 The documentation the risk register already promised** `[activity: technical-writing]`

  The PRD mitigates the per-event-cost risk with "keep the measured cost visible in the
  documentation", and no other task in this plan writes or updates any documentation. A
  mitigation nothing owns is not a mitigation.

  1. Prime: read the scripts README's existing structure and the CON-5 measurement
     `[ref: SDD/Constraints — CON-5]`.
  2. Test: a reader who has not seen this spec can answer three questions from the docs alone —
     what recording costs per event, where the record for their repository lives, and how to turn
     it off.
  3. Implement: extend `plugins/tcs-helper/scripts/observability/README.md` with the 3-5 ms
     figure and its platform caveat, the two record location shapes, the setup and removal verbs,
     and the locations config's format.
  4. Validate: the three questions are answerable by reading, not by inference.
  5. Success: `[ref: PRD/Risks and Mitigations]` — the documentation mitigation has an owner

- [ ] **T4.4 End-to-end validation and the collection gate** `[activity: validate]`

  1. Run the full suites: `pytest -q` and `bats plugins/*/tests/bats`.
  2. Verify every SDD acceptance criterion has passing evidence, and that each one's evidence is a
     test rather than a prose claim. Where only prose exists, say so rather than marking it covered
     — spec-018's evidence map found four criteria in that state and naming them was more useful
     than quietly counting them.
  3. Confirm the safety property directly rather than by inference: in each target, assert that
     `git check-ignore` succeeds for every path this feature wrote, and that `git status` reports
     nothing.
  4. **Check the two constraints nothing else checks.** A self-audit found CON-1 and CON-3 stated in
     the SDD and enforced by no task — the kind of constraint that is honoured by intention until
     the day it is not.
     - **CON-1 (bash 3.2)**: the mechanism is the `macos-latest` leg of the bats matrix in
       `.github/workflows/tests.yml:82`, since macOS ships bash 3.2 as `/bin/bash`. Confirm the new
       suite actually runs on that leg — a suite that only runs on the Linux leg is tested under
       bash 5 and proves nothing about the constraint. There is no dedicated `BASH_VERSINFO` guard
       anywhere in this repository; the runner *is* the guard, which is worth knowing before relying
       on it.
     - **CON-3 (no new runtime dependency)**: assert that `requirements-dev.txt` is unchanged and
       that the new Python modules import nothing outside the standard library. `tomllib` is stdlib
       on the local interpreter, which is what makes the config format free — but that is a property
       of the interpreter version, so assert it rather than assume it.
  5. **Record the collection period's end date in the spec README.** This is the PRD's one carried
     open question. Without a date, "evaluate later" is the failure mode this spec exists to
     correct, and the mode spec-018 already fell into once.
  6. Success: every SDD acceptance criterion has passing evidence; the collection period has a start
     and a named end `[ref: PRD/Success Metrics]`

---

## Phase Acceptance Criteria

- The command performs all four PRD journeys through its real entry point.
- Every target records, and none shows a change to a tracked file.
- The test-fixture record directories are gone before collection begins.
- The collection period has a written end date, and a plan for what happens on that date.
