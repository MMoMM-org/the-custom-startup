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

- [x] **T4.1 The setup command** `[activity: backend-api]`

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

  **Rulings, 2026-09-11, from T4.1's implementation review.** The implementer raised five
  decisions rather than taking them silently; four are recorded here, the fifth (the
  `${CLAUDE_PLUGIN_ROOT}` interpolation in another plugin's `git-setup/SKILL.md`) went to issue
  #163 as out of this spec's scope.

  **(t) The write-path ignore check belongs in `setup.sh`, and before the lock.** SDD-AC-6 was
  enforced by nothing at command level: `detect.sh` gates only the settings path, while
  `registration.written_paths()` declares four, and T4.2 assigned the backup path to an operator's
  memory with T4.4 checking it after the fact. `setup.sh` now refuses a target where any declared
  path is committable. It is hoisted **above** the lock because the lock file is itself one of those
  paths, so the check cannot follow the thing it guards. This is more than T4.1 literally asked for
  and is kept deliberately: the SDD calls this the one refusal that protects a third party, and a
  target that ignores `settings.local.json` by name rather than `.claude/` wholesale would otherwise
  receive a committable `.bak` and be told about it afterwards.

  **(u) `remove` takes legacy entries out too, extending (s) to the symmetric case.** Ruling (s)
  gave the migration to `install` alone. Measured consequence: `remove` against an un-migrated
  LEGACY target reported success while all three legacy hooks kept firing from the shared file --
  "off" to whoever asked, on in fact. That is the silent-failure shape this whole spec exists to
  catch, and PRD F2's premise is that removal makes turning recording on a reversible decision
  rather than a permanent one. `--remove-legacy` closes it.

  **(v) SUPERSEDED BY (aa) -- read that first.** This ruling diagnosed the over-broad
  classification correctly but filed it as an evidence-map matter and left the behaviour
  alone; (aa) fixes it. Kept for the audit trail.

  **(v) PRD F1's "foreign entries are still present and unmodified afterwards" is satisfied
  vacuously at command level, and T4.4 must say so rather than count it.** `detect.sh:336` collects
  every hook command outside our namespace, not only those under our three event names, so CONFLICT
  is broader than the SDD's and PRD's "under the same event" wording. Install therefore never runs
  against a target holding foreign content at all, and the merge never gets the opportunity to step
  around it. The preservation property is real at the library layer, where T2.x pins it; at the
  command layer nothing exercises it. T4.4's evidence map records this as prose-only coverage --
  spec-018's map found four criteria in that state and naming them proved more useful than quietly
  counting them.

  **(w) The registration-matrix suite gains cases beside its flagless assertion; it does not lose
  it.** Ruling (s) said a green run there is the defect rather than the proof, which can be read as
  expecting the old assertion to disappear when T4.1 lands. It does not: that assertion pins
  `registration.py` editing only the one `--settings` path it is handed, which stays correct and
  deliberate under ADR-1. What was stale was its forward-reference to T4.1, now removed, with new
  cases added alongside pinning the migration boundary.

  **Rulings, 2026-09-11, from T4.1's review gates.**

  **(x) A partial legacy shape classifies LEGACY, not CLEAN.** `is_legacy` required all three
  events to match (`detect.sh:313`, `matched_events == set(LEGACY_SCRIPTS.keys())`), so a target
  with two of three read as CLEAN -- and `install` then added a full registration beside the
  still-live legacy hooks, recording twice, while `remove` reported success as they kept firing.
  That is the exact outcome the migration exists to prevent, and it fails in the dangerous
  direction. One or more matching entries is now enough; `_strip_legacy` removes what it actually
  finds, so a half-migrated target converges to fully-migrated. `ABORT_WRONGSHAPE` was considered
  and rejected: phase 2 made LEGACY a WARN deliberately, on the grounds that it means "action
  available, nothing broken", and forcing a manual two-step is what that ruling was written to
  avoid. The severity stays exit 4; only the matching rule changed. Measured before ruling: four
  distinct shapes reached the same double registration -- a non-string command replacing one of the
  trio, one event simply absent, only one entry present, and the env flag removed by hand. Zero
  matching entries still classifies CLEAN, which is correct: a target the PARTIAL MIGRATION path
  has stripped has nothing left to migrate, and `install` on it takes the plain path.

  **(y) Legacy ownership is proven by the namespace, and the env flag is corroboration rather than
  a gate.** Found by the sweep ruling (x) asked for, and the more serious of the two by a distance.
  Matching was `command.endswith(<script name>)`, which **any** third party's script of that name
  satisfied. Reproduced on the branch as it then stood: a shared file holding two genuine legacy
  entries plus an unrelated `/opt/other-tool/log_skill.sh` classified `LEGACY`, and the migration
  would have **deleted a hook this project does not own**. At the old all-three threshold that
  needed a coincidence; at ruling (x)'s threshold of one it becomes a licence, so the tightening is
  not scope creep but the precondition that makes (x) safe to ship. Matching now requires the
  legacy namespace `plugins/tcs-helper/scripts/observability/` in both `detect.sh` and
  `registration.py` -- ADR-5's rule ("ownership is the path namespace") applied to the legacy shape,
  which it had never been. The env flag was a required gate and is now corroboration: with
  ownership proven by namespace it added nothing except a fourth way for a live legacy registration
  to read as CLEAN. The LEGACY line also now names the events it actually found, so a partial shape
  no longer reports as a full one.




- [x] **T4.2 Rollout to the target repositories** `[activity: validate]`

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

  **Ruling (z), 2026-09-12, from T4.2's rollout.** The first real rollout found a defect no test
  had reached: `_lock_acquire` discarded the creation attempt's stderr (`2>/dev/null`), so a lock
  that could not be **created** was reported as a lock that was **held** -- "another observability
  setup run holds the lock ... A lock held by a live process is never force-removed." No such run
  existed and no lock file existed; the real cause was a write restriction on the target's
  `.claude/` directory. The refusal itself was correct and nothing was written either way, so this
  was a diagnosis defect rather than a correctness one -- but it is the first message an operator
  sees when rolling out to a repository whose permissions differ from the shipping one, and it sent
  me looking for a concurrent process that was never there.

  Fixed by capturing the discarded stderr rather than adding a writability pre-check, which would
  have opened a TOCTOU gap between check and acquisition and paid for a diagnosis on the happy path
  too. `noclobber` already refuses with `EEXIST` when a lock is present and `EACCES`/`EPERM`/
  `ENOENT` when the file cannot be made, so whether the lock file exists at the moment the run gives
  up separates the two -- and that check is consulted *after* the decision to refuse, so a race
  there changes the wording and never the outcome. One shape stays deliberately unseparated and is
  named in a comment rather than left as a surprise: an unwritable directory that also holds a lock
  reports contention, which is true as far as it goes while the deeper cause is the permission.

  Verified against the original field scenario, not only the fixture: the same command that
  produced the phantom-contention message now names the directory restriction and the errno.

  **Ruling (aa), 2026-09-12, and it revises (v).** `detect.sh:403` built its foreign set as
  `{cmd for _, cmd in local_commands if OUR_NAMESPACE not in cmd}` -- the event name discarded, so
  **any** foreign hook under **any** event classified the target CONFLICT. SDD-AC-4 and PRD F1 both
  say "a foreign entry **under one of the three event names**". The test must honour the event.

  Found by the maintainer asking where a refused target's hooks actually came from. Measured: that
  target's only hooks were `PostToolUse` (matcher `Bash`) and `SessionStart`, while this feature
  registers `InstructionsLoaded`, `PreToolUse` (matcher `Skill`) and `SubagentStart`. Nothing
  overlapped, and the target was refused anyway. `setup.sh`'s stop message additionally asserted
  that foreign entries "occupy the event names this feature registers", which in that case was
  simply untrue -- the same failure class as the false `ADDED` and the phantom lock contention.

  What settles it: the settings schema is `hooks: { EVENT: [ {matcher, hooks: [...]}, ... ] }`, an
  array of groups each holding an array of hooks, so several hooks under one event is the designed
  shape rather than a collision. `add_registration`'s own docstring already states that every
  existing entry that is not ours -- *including a foreign entry under our own event name* -- stays
  exactly where it is. Coexistence is not merely possible; it is what the editor does.

  **(v) was too weak and is superseded here.** It recorded the same over-broad classification but
  filed it as an evidence-map matter -- "PRD F1's foreign-entry preservation is satisfied vacuously
  at command level" -- and left the behaviour alone. That was wrong: the consequence is not a thin
  evidence map, it is that targets which are genuinely clean get refused. With (aa) in place PRD F1's
  preservation promise is exercised for real rather than never reached, so T4.4's evidence map
  records it as tested rather than prose-only.

  One question is deliberately left open for the implementer to answer with evidence rather than
  for me to guess: we register `PreToolUse` with matcher `Skill`, and whether a foreign `PreToolUse`
  hook with a different matcher overlaps at all depends on how the harness treats the matcher as
  part of dispatch identity. Event-level is the floor; matcher-level may be correct on top of it.



- [x] **T4.3 The documentation the risk register already promised** `[activity: technical-writing]`

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
       `.github/workflows/tests.yml` (the `bats` job at `:87`, its matrix at `:95` -- the cited
       `:82` was stale, the third stale line reference this plan has carried), since macOS ships bash 3.2 as `/bin/bash`. Confirm the new
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

  **Ruling (ac), 2026-09-12, from T4.4's evidence map.** Three criteria -- SDD-AC-3 (unrelated
  top-level keys survive), SDD-AC-9 (an interrupted write leaves the original and a backup) and
  SDD-AC-11 (two concurrent runs serialize) -- were tested thoroughly but only against
  `registration.py` directly, never through `setup.sh`. All three are worded "when setup runs", and
  ruling (r) established that this command is exercised through its real entry point rather than by
  calling its libraries. Command-level tests are added for all three. The risk was low --
  `setup.sh` calls the same `main()` with no branch between -- so this closes the letter rather
  than a hazard, which is exactly what an evidence map is for: the criterion says "setup", so the
  evidence should say "setup".

  **The map's one real gap was SDD-AC-6**, on the criterion the SDD itself calls "the one refusal
  that protects a third party". `registration.written_paths()` declares four paths -- the settings
  file, its backup, its lock and its temp -- and `setup.sh` loops over all four with one uniform
  `git check-ignore`. Only the settings and backup paths had a refusal test; the lock and temp
  paths had none. Rated PARTIAL rather than a defect because the uniform loop leaves no per-path
  special-casing for a bug to hide in, but a criterion stated as "any declared path" deserves proof
  per path.

  **Recorded for the map, because the reviewer's reading corrects my question rather than answering
  it.** I left the matcher question open for evidence -- whether a foreign `PreToolUse` hook at
  matcher `Bash` collides with ours at `Skill`. Spec compliance answered that SDD-AC-4 never
  mentions the matcher at all, so event-level is not the coarser of two readings needing
  justification: it is the only one the criterion's text supports, and a matcher-level narrowing
  would be an implementer-added restriction the criterion does not ask for. The map therefore
  records SDD-AC-4 as **exactly satisfied**, with matcher-level examined and deliberately rejected
  with documented reasoning -- not as a compromise, and not as an open question.

  **The evidence map, 2026-09-12.** Every SDD acceptance criterion, and the test that exercises it.
  Built by reading each test body rather than by grepping for `SDD-AC-n` comments: a comment can
  name a criterion its test does not reach, so a reference is corroboration and never proof. The
  question applied to each was **would this test go red if the behaviour silently stopped working**
  -- an answer of "probably" was recorded as a gap, not as coverage.

  | AC | Evidence |
  |---|---|
  | 1 | `observability-setup.bats` -- non-repository reported, nothing written, exit 0 |
  | 2 | `observability-setup.bats` + `test_observability_registration.py` -- created file holds exactly `{env,hooks}` |
  | 3 | `test_observability_registration.py` (library) + `observability-setup.bats` (command, ruling (ac)) |
  | 4 | `observability-setup.bats` x3 -- stop under our events; install proceeds under others; different matcher still stops |
  | 5 | `observability-setup.bats` -- unparseable refused non-zero, and a sibling asserting no traceback |
  | 6 | `observability-setup.bats` x3 -- lock path, temp path, plus a sweep over `written_paths()` itself |
  | 7 | `test_observability_registration.py` + `observability-setup.bats` -- "already configured" |
  | 8 | `test_observability_registration.py` + `observability-bundle-install.bats` |
  | 9 | `test_observability_registration.py` (patched `os.replace`) + `observability-setup.bats` (`chflags uchg`, ruling (ac)) |
  | 10 | `test_observability_registration.py` + `observability-setup.bats` -- both layers |
  | 11 | `test_observability_registration.py` + `observability-setup.bats` -- two real processes, each observation JSON-parsed |
  | 12, 13, 14 | `test_observability_registration.py` + `observability-setup.bats` -- both layers each |
  | 15 | `observability-setup.bats` -- drift surfaces through `status`, not through the comparator |
  | 16 | `test_observability_report.py` (real CLI) + `test_observability_sources.py` |
  | 17, 18 | `test_observability_sources.py` -- `MISSING` asserted never to read as `NOT_YET_RECORDING` |
  | 19 | `test_observability_report.py` -- same filename counted separately per repo |
  | 20, 21, 22, 23 | `test_observability_report.py` -- per-source state, timing, firing detail, denominator |
  | 24 | `test_observability_report_t30_golden.py` -- real subprocess against a fixture frozen at `eb9b529` |
  | 25 | `test_observability_sources.py` + `test_observability_report.py` -- both clauses |
  | 26 | `observability-setup.bats` x5 -- each state cross-asserts the other two are absent |

  **26 tested, 0 prose-only.** spec-018's equivalent map found four criteria in the prose-only
  state; naming them there proved more useful than counting them, and the same standard was applied
  here. Two criteria needed work to reach it, both under ruling (ac): AC-6 had only two of the four
  paths `written_paths()` declares, on the criterion the SDD calls "the one refusal that protects a
  third party"; and AC-3, AC-9 and AC-11 were tested only against the library while worded "when
  setup runs".

  **What the map cost to build, recorded because it is the reusable part.** Four findings came out
  of it that no amount of counting would have produced:

  - **AC-4 is exactly satisfied, not a compromise.** The matcher question was left open for
    evidence; the criterion never mentions the matcher, so event-level is the only reading its text
    supports and a matcher-level narrowing would be an implementer-added restriction. The question
    was wrong, not the answer.
  - **The stale `SDD-AC-n` comments were not stale.** `test_observability_report.py` predates this
    spec and cites **spec-018's own** table, which numbers independently and collides on every N
    from 1 to 20. Six comments were correct for the spec they were written against; the instruction
    to "fix" them would have broken them. They are now prefixed by spec rather than renumbered.
  - **A fourth vacuous assertion.** `observability-setup.bats`'s ignore-refusal test asserted the
    substring `ignored`, which the real message (`does not ignore`) does not contain -- it was
    matching the fixture's own directory name, `not-ignored`. It would have stayed green with the
    refusal message deleted.
  - **AC-9 is reachable through the entry point without a seam.** `chflags uchg` on the destination
    lets the backup and the temp write succeed and fails only the final `os.replace`, which is
    exactly the window the criterion describes.



---

## Phase Acceptance Criteria

- The command performs all four PRD journeys through its real entry point.
- Every target records, and none shows a change to a tracked file.
- The test-fixture record directories are gone before collection begins.
- The collection period has a written end date, and a plan for what happens on that date.
