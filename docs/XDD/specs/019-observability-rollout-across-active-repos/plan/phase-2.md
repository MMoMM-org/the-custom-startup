---
title: "Phase 2: The registration editor"
status: in_progress
version: "1.0"
phase: 2
---

# Phase 2: The registration editor

# The riskiest phase in the spec

This phase writes into configuration files the maintainer did not author and cannot recover from
version control, because the file it writes to is deliberately untracked (ADR-1). Every other phase
can be redone by re-running it. This one can destroy something.

Read `modules/satori/scripts/install-hooks.sh` before starting — and read it knowing that its merge
is the model and its **write is the anti-model**. It opens the real file with `'w'` at `:97-99`,
truncating before rewriting. An interruption between those two lines leaves the user with nothing.

---

## Phase Context

**GATE**: Read all referenced files before starting this phase.

**Specification References**:
- `[ref: SDD/ADR-1]` — write to the untracked local settings layer, never the shared one
- `[ref: SDD/ADR-4]` — merge like satori, write unlike it; seven of the precedent's nine gaps closed, two named as accepted costs
- `[ref: SDD/ADR-5]` — ownership is the path namespace
- `[ref: SDD/Runtime View — Primary Flow]` and `[ref: SDD/Runtime View — Error Handling]`
- `[ref: PRD/F1]`, `[ref: PRD/F2]`

**Key Decisions**:
- **The write target is `.claude/settings.local.json`.** In three of the four intended targets the
  shared `settings.json` is version-controlled, so a registration written there could be committed
  and would then start recording for anyone who cloned the repository. This is checked at runtime
  per target, not assumed from those four.
- **Ownership is the path namespace** `$HOME/.claude/observability/`, because JSON has nowhere to
  put a version banner. Satori's alternative — exact command-string equality — silently produces a
  duplicate group whenever the command changes, with no way to recognise or remove the old one.
- **Foreign content is a stop condition, not a failure**: report, change nothing, exit 0. Copied
  deliberately from `plugins/tcs-git-helpers/skills/git-setup/lib/with_gha.sh:60-69`.

**Dependencies**: Phase 1 (the bundle path must exist as a concept; the editor writes a command
string pointing into it).

---

## Tasks

Delivers the ability to add and remove the registration in a target repository without damaging
anything the maintainer owns.

- [x] **T2.1 The fixture matrix** `[activity: test-strategy]`

  **This comes first because three later tasks validate against it.** In the first draft of this
  plan it was numbered last, which made T2.2, T2.3 and T2.5 depend on a task that had not run — the
  only backwards dependency in the spec, and it sat in the phase that can destroy something.

  1. Prime: read `plugins/tcs-git-helpers/tests/fixtures/repos/build.sh:245-386` for the
     named-scenario builder, and `plugins/tcs-git-helpers/tests/bats/install-files.bats:39-80` for
     the throwaway-repo-per-test shape — `BATS_TEST_TMPDIR`, `GIT_CONFIG_GLOBAL=/dev/null`, pinned
     identity, `git -C` everywhere.
  2. Test: one sanity test per fixture, as `skill_git_setup.bats:251-299` does. Without these a
     broken fixture weakens every test that uses it silently, rather than failing loudly.
  3. Implement: the scenario set the rest of the phase needs — settings file **absent / empty
     object / foreign-only / foreign plus ours-current / foreign plus ours-older / malformed /
     non-ASCII / same event names already populated / write path not gitignored / **the shipping
     repository itself**, whose recording was configured by hand before this command existed and
     which must be recognised as already configured rather than duplicated — a PRD edge case that
     had no fixture and no criterion until an audit found it.

     **Pinned 2026-09-08 after a TDD gate blocked this task. Three corrections.**

     - **The shipping-repository fixture must be built from this repository's ACTUAL state, which
       was measured rather than assumed, and which the design as written does not recognise.**
       Verified today:

           file:   .claude/settings.json          (NOT settings.local.json; untracked here)
           env:    CLAUDE_OBSERVABILITY_ENABLED=1
           hooks:  InstructionsLoaded -> $CLAUDE_PROJECT_DIR/plugins/tcs-helper/scripts/observability/log_instructions.sh
                   PreToolUse         -> $CLAUDE_PROJECT_DIR/plugins/tcs-helper/scripts/observability/log_skill.sh
                   SubagentStart      -> $CLAUDE_PROJECT_DIR/plugins/tcs-helper/scripts/observability/log_agent.sh

       This collides with two ADRs at once. ADR-1 has the command write to
       `settings.local.json`, and this repository's `settings.local.json` holds no hooks at all.
       ADR-5 proves ownership by the `$HOME/.claude/observability/` path namespace, and these
       commands point at `$CLAUDE_PROJECT_DIR/plugins/...`. So detection reading only
       `settings.local.json` calls this repository **clean** and would add a second registration
       beside a live one — double recording in the very repository the collection period depends
       on — while detection that reads `settings.json` calls our own entries **foreign**.

     - **Maintainer ruling: this repository migrates to the standard mechanism.** The hand-made
       entries come out and setup installs the normal registration against the `$HOME` bundle.
       The migration itself runs in phase 4, since it needs the setup command to exist.
       **That does not make this fixture optional — it makes it the state the migration passes
       through.** Setup will meet a repository in the legacy shape, so detection must handle it
       safely or the migration is exactly where the duplicate gets created.

     - **A third missing fixture: valid JSON of the wrong shape.** The list's `malformed` case means
       *unparseable* — T2.3 pairs it with "an unparseable file causes no write". A file that parses
       cleanly and is then the wrong TYPE (`hooks` a string rather than an object, or an event's
       value a scalar rather than a list) is a different state entirely: it survives
       `json.load` and breaks the merge, which is where an unhandled `TypeError`/`KeyError` becomes
       a traceback instead of the diagnosis T2.3 requires. Add `valid-json-wrong-shape`.

     - Two further fixtures are missing from the list above and must be added:
       **not-a-repository** (a plain directory with no `.git/` — T2.2's first requirement, and
       distinct from a repository whose settings file is absent), and **ignored-file-but-not-backup**
       (a target whose `.gitignore` names `settings.local.json` explicitly rather than ignoring
       `.claude/` wholesale, so the `.bak` path is NOT ignored). T2.5 names that hazard precisely and
       the matrix had no fixture in which it can occur, so the assertion it calls for could not have
       been written.

     - **The sanity-test pass criterion is too loose as referenced.** `skill_git_setup.bats:251-299`
       passes on directory existence alone, which is exactly the silent weakening this step's own
       wording warns against. Each sanity test must assert the fixture's *observable characteristic*
       — e.g. `foreign-only` has at least one foreign entry AND zero entries in our namespace;
       repository fixtures additionally prove `git -C <repo> log` succeeds, so a `git init` that
       failed and leaked to the parent is caught here rather than downstream. Every fixture holding a settings
       file additionally asserts `json.load` succeeds on it (or, for the deliberately-unparseable
       one, that it raises) — a structural check only, never a call into `detect.sh` or the merge.
       **The sanity tests must not call T2.2's detection script** to validate a fixture: T2.1 runs
       first precisely so nothing in it depends on a later task, and reaching for `detect.sh` here
       would reintroduce the backwards dependency this ordering exists to remove. Assert the file
       contents directly.
  4. Validate: each fixture builds and its sanity test passes.
  5. Success: every later task in this phase has the target states it needs `[ref: SDD/Quality Requirements]`

- [x] **T2.2 Detection: classify a target before touching it** `[activity: backend-api]`

  1. Prime: read `plugins/tcs-git-helpers/skills/git-setup/lib/detect_conflicts.sh:60-67` for the severity
     exit-code convention — 0 clean / 2 abort / 3 conflict / 4 warn, never a boolean
     `[ref: SDD/Runtime View — Primary Flow]`.
  2. Test: a target that is not a repository is reported and nothing else runs; an absent settings
     file is `clean`; a file holding only foreign entries is `conflict` and names them; a file
     holding our namespace at the current version is `ours-current`; at an older version is
     `ours-old`; an unparseable file is `abort`; **a target whose write path is NOT ignored by
     version control is `abort`** — this is the check that protects a third party, so it is tested
     first and independently; and detection writes nothing at all, asserted against a
     write-protected target.
     **Pinned 2026-09-08:** detection must also classify the **legacy in-repository shape** — our
     scripts registered under `<repo>/plugins/tcs-helper/scripts/observability/` rather than the
     `$HOME/.claude/observability/` namespace, in `settings.json` rather than `settings.local.json`.
     That is this repository's real, hand-made state (see T2.1). It must be reported distinctly:
     **never `clean`**, because that would let setup add a duplicate registration beside a live one,
     and never a bare `conflict` naming our own scripts as a third party's. This is the state the
     maintainer-approved migration passes through, so getting it wrong is how the migration creates
     the double-recording it is meant to avoid.

     **Coupling flagged by T2.1 when it built the fixtures — read before designing detect.sh's
     interface.** `ours-current` versus `ours-old` is **not observable from the settings file at
     all.** ADR-5 makes the registration command version-opaque on purpose (a namespace prefix
     survives a version change), so both states carry byte-identical JSON — T2.1's fixtures 4 and 5
     assert that identity with `diff -q`. The version lives only in the bundle marker at
     `$HOME/.claude/observability/`. Each of those two fixtures therefore ships a paired
     `<scenario>.home/` directory standing in for `$HOME`, and `detect.sh` needs a way to be pointed
     at an overridden home so those two cases are testable at all. Phase 1 already provides the
     mechanism: `_bundle_install_target_dir()` resolves at CALL time and honours a
     `_BUNDLE_INSTALL_TARGET_DIR` override, so read the installed marker through it rather than
     composing `$HOME/.claude/observability` a second time.

     **Also worth knowing when classifying `write-path-not-ignored`:** on this machine the ignore
     that covers `.claude/settings.local.json` comes from the user's *global* excludes file
     (`~/.config/git/ignore`), not from any repository's own `.gitignore`. Production detection
     should keep using real `git check-ignore` semantics, which include global rules — but be aware
     a target relying on a personal global ignore is more fragile than one carrying its own rule,
     and say which it found when reporting.

     **Pinned 2026-09-08 after a second TDD gate blocked this task. Five gaps closed.**

     - **State and severity are separate channels, and the mapping is now fixed (maintainer
       ruling).** Eight states do not fit four exit codes, and they were never meant to: the
       precedent at `detect_conflicts.sh` emits a labelled line per finding (`_emit "ABORT" "..."`)
       and keeps only the highest severity as the exit code (`_bump 2`). Do the same — the state
       name goes to stdout as a labelled line, the exit code carries severity alone. T4.1 reads the
       label for its message and branches on the code for control flow.

           state                    label          exit
           --------------------------------------------
           clean (absent/empty)     CLEAN            0
           ours-current             OURS-CURRENT     0
           ours-old                 OURS-OLD         4
           legacy in-repo           LEGACY           4
           foreign-only             CONFLICT         3
           not-a-repository         ABORT            2
           unparseable              ABORT            2
           valid-json-wrong-shape   ABORT            2
           write-path-not-ignored   ABORT            2

       `legacy` and `ours-old` are **warn, not abort**, deliberately: both mean "action available,
       nothing broken", and the maintainer-approved migration of this repository runs THROUGH setup.
       An abort there would force the migration to be a manual two-step on the one repository most
       needing a clean one.

     - **One labelled line per target, and the write-path check is a GATE that short-circuits.**
       If the write path is not ignored by version control, emit `ABORT`, exit 2, and stop —
       **without reading the settings content at all**. Only a target that passes that gate is
       classified. This is what the plan's "tested first and independently" means operationally, and
       it removes the ambiguity a multi-line report would create: a target can never come back as
       both `ABORT` and `OURS-OLD`, so T4.1 never has to decide which of two findings to show a user
       about a repository they do not own.

     - **Every fixture gets a classification, so none is left to an implementer's guess:**
       `absent` and `empty-object` -> CLEAN; `foreign-only` and `same-event-names-populated` ->
       CONFLICT (the latter is foreign content that merely happens to sit under our event names —
       whether the merge preserves it is T2.3's problem, not detection's);
       `foreign-plus-ours-current` -> OURS-CURRENT; `foreign-plus-ours-older` -> OURS-OLD;
       `malformed` and `valid-json-wrong-shape` -> ABORT; `write-path-not-ignored` -> ABORT;
       `not-a-repository` -> ABORT; `already-configured-observability` -> LEGACY.
       `non-ascii` classifies by its hooks content like any other file — it exists to prove T2.3
       does not mangle foreign non-ASCII values, and detection must simply not corrupt or choke on
       it. `ignored-file-but-not-backup` is CLEAN to detection; the `.bak` ignore status it exists
       for is T2.5's assertion.

     - **`valid-json-wrong-shape` is ABORT, not a traceback.** The plan said an *unparseable* file
       aborts; a file that parses and whose `hooks` is a string is a different state and had no
       ruling. Detection must recognise it and abort with a diagnosis — an unhandled
       `TypeError`/`KeyError` reaching the user is the failure mode this closes.

     - **The read-only assertion must exercise the read paths.** Phase 1 shipped exactly this
       defect: a write-protected assertion covering only the branch that opens no file. Detection
       reads up to three things — `settings.local.json`, `settings.json` (for the legacy shape), and
       the bundle marker under the resolved home — so the write-protected case must be a target
       where all three are present and readable, asserting a real classification comes back. Guard
       it with a **write canary**, not an `EUID` check: attempt a write, skip if it succeeds. This
       repository lives on a mounted volume, where `chmod 555` may not bite.

     - **Test isolation for `git check-ignore` needs no production divergence — verified 2026-09-08.**
       Detection must call plain `git check-ignore`, because global ignores are real for users and
       suppressing them would make detection lie. Tests neutralise the developer's personal
       `~/.config/git/ignore` (which on this machine contains `**/.claude/settings.local.json`, and
       would otherwise make the `write-path-not-ignored` fixture read as ignored) purely from the
       environment:

           GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=core.excludesFile GIT_CONFIG_VALUE_0=/dev/null

       Measured: plain `check-ignore` reports the path ignored; with those variables set it reports
       not-ignored. Production code is untouched.

  3. Implement: `plugins/tcs-helper/skills/observability-setup/lib/detect.sh`
  4. Validate: `bats` green over the scenario fixtures from T2.1.
  5. Success: `[ref: SDD/SDD-AC-1, SDD-AC-4, SDD-AC-6]` — AC-1's detection half; its command-level half is asserted in T4.1

- [ ] **T2.3 The merge: add the registration without disturbing anything else**
      `[activity: backend-api]`

  1. Prime: read `modules/satori/scripts/install-hooks.sh:70-99` in full. Take `:70-87` — read the
     whole document, `setdefault` the block, append only when absent, reassign. Reject `:97-99`
     `[ref: SDD/ADR-4]`.
  2. Test: unrelated top-level keys survive byte-identically; a foreign hooks block survives,
     including foreign entries under the *same* event name; non-ASCII values in foreign content are
     unchanged (`ensure_ascii=False` — this repository has already been bitten by the default once);
     an unparseable file causes no write, **exits non-zero**, and produces a diagnosis rather than a
     traceback — the exit status is asserted, not just the absence of a write; an absent file is
     created containing only our entries; the three hook entries and the `env` switch are all
     present after a successful merge; running twice changes nothing.
  3. Implement: `plugins/tcs-helper/skills/observability-setup/lib/registration.py`, tested from
     `tests/tcs-helper/test_observability_registration.py` — **named here deliberately**: with no
     stated home an implementer might extend `tests/test_observability_report.py`, which phase 3
     also edits, and the file-disjointness that makes the two phases independent would hold only
     by luck. With a
     `--settings <path>` override so tests never touch a real file. *(`install-hooks.sh:22-42` ships
     such an override and nothing tests it; do not repeat that.)*
  4. Validate: `pytest -q` green; every assertion compares the file's full content, not just our
     keys, because the risk being tested is what happens to everything else.
  5. Success: `[ref: SDD/SDD-AC-2, SDD-AC-3, SDD-AC-5, SDD-AC-10]`; `[ref: PRD/F1]`

- [ ] **T2.4 Removal, and the update path ownership makes possible** `[activity: backend-api]`

  1. Prime: read ADR-5 and be clear why exact-string matching cannot support removal after a version
     change `[ref: SDD/ADR-5]`.
  2. Test: removal deletes only entries whose command points inside our namespace; foreign entries
     under the same event names survive; removal on a never-configured target changes nothing and
     exits 0; **removal never deletes records** — asserted by counting record files before and
     after; an entry written by an older bundle version is recognised and removed, not orphaned;
     re-running setup after a version change updates in place rather than appending a duplicate.
     Two **reporting** clauses, which the mechanics alone do not satisfy and which an audit found
     untested: re-running setup at the *same* version reports "already configured" — the message,
     not merely the absence of a change; and re-running after a *version change* reports an update
     rather than an install. Both are the only externally visible difference between three
     outcomes that all leave a correct file behind, so a caller cannot tell them apart otherwise.
  3. Implement: extend `registration.py` with removal and update.
  4. Validate: `pytest -q` green; a round-trip test asserts install → remove leaves the file
     byte-identical to its pre-install content **and leaves no backup behind** — the round trip
     alone would pass with a stray `.bak` sitting beside it, which is the state T2.5's retention
     rule says must not persist.
  5. Success: `[ref: SDD/SDD-AC-7, SDD-AC-8, SDD-AC-12, SDD-AC-13, SDD-AC-14]`; `[ref: PRD/F2]`

- [ ] **T2.5 Durability: backup, atomic replace, and the lock** `[activity: backend-api]`

  1. Prime: read `install.sh:729-731` — `mktemp`, write, `mv` onto `SETTINGS_FILE`, which is this
     repository already atomically replacing a settings file and therefore the closest precedent
     there is — and `scripts/the-custom-startup-configure-statusline.sh:176-180` for the same
     shape;
     read `plugins/tcs-git-helpers/skills/git-setup/lib/lock.sh:45-76` for a bash 3.2 lock via `set -C`, and
     `:108-118` for why release must accept a dead owner — the skill acquires and releases in
     separate processes, so a `pid == $$` check alone leaks the lock after every run
     `[ref: SDD/ADR-4]`.
  2. Test — **each of these names its mechanism**, because an audit found the first draft stated
     properties with no observable way to check them, and three developers would have reached for
     three different techniques:
     **the backup lands at a named path** — `<settings file>.tcs-observability.bak`, beside
     the file it backs up — and that path's ignore status is asserted, not assumed. A target that
     ignores `settings.local.json` *by name* rather than ignoring `.claude/` wholesale would leave
     a `.bak` un-ignored, and T4.3 asserts every path this feature writes is ignored. Getting this
     wrong drops a committable file into a repository we do not own, which is the exact harm ADR-1
     exists to prevent. Retention: the backup is overwritten by the next write and removed by
     removal, so at most one exists per target.
     The real file is never opened for truncation — wrap `builtins.open`, assert the final path is
     never opened in a truncating mode, and assert the final path's `st_ino` changes across the
     write (a rename replaces the inode; an in-place rewrite does not); a backup exists after a write and matches the
     pre-write content; an interrupted write leaves the original intact — patch the rename to
     raise once the temporary file exists, then assert the original's and the backup's bytes;
     two concurrent runs serialize and neither sees a partial file; **a contended lock behaves as
     the SDD says** — the second run either waits and then succeeds, or reports and exits, within
     a bounded time, and the test asserts which of the two it is rather than accepting either;
     a live foreign lock is never force-removed; a stale lock (dead PID, or older than the TTL)
     is reclaimed.
  3. Implement: wrap the merge in backup → temp-write → rename, under the lock.
  4. Validate: `pytest -q` and `bats` green.
  5. Success: `[ref: SDD/SDD-AC-9, SDD-AC-11]`; `[ref: SDD/Quality Requirements]`

- [ ] **T2.6 Phase Validation** `[activity: validate]`

  - Run `pytest -q` and `bats plugins/*/tests/bats`.
  - Confirm the suite never writes outside its temp directories: run it with the real home
    write-protected and assert it still passes.
  - Confirm no test touches a real settings file, by asserting the `--settings` override is used
    everywhere the suite writes.

---

## Phase Acceptance Criteria

- Setup and removal are correct across every fixture in the matrix.
- No test touches a real settings file, and the suite passes with the real home write-protected.
- An interrupted write is survivable, demonstrated rather than argued.
