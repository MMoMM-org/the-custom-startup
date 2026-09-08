---
title: "Phase 2: The registration editor"
status: pending
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
- `[ref: SDD/ADR-4]` — merge like satori, write unlike it; the nine gaps
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
  deliberately from `with_gha.sh:60-70`.

**Dependencies**: Phase 1 (the bundle path must exist as a concept; the editor writes a command
string pointing into it).

---

## Tasks

Delivers the ability to add and remove the registration in a target repository without damaging
anything the maintainer owns.

- [ ] **T2.1 Detection: classify a target before touching it** `[activity: backend-api]`

  1. Prime: read `plugins/tcs-git-helpers/scripts/lib/detect_conflicts.sh:60-67` for the severity
     exit-code convention — 0 clean / 2 abort / 3 conflict / 4 warn, never a boolean
     `[ref: SDD/Runtime View — Primary Flow]`.
  2. Test: a target that is not a repository is reported and nothing else runs; an absent settings
     file is `clean`; a file holding only foreign entries is `conflict` and names them; a file
     holding our namespace at the current version is `ours-current`; at an older version is
     `ours-old`; an unparseable file is `abort`; **a target whose write path is NOT ignored by
     version control is `abort`** — this is the check that protects a third party, so it is tested
     first and independently; and detection writes nothing at all, asserted against a
     write-protected target.
  3. Implement: `plugins/tcs-helper/skills/observability-setup/lib/detect.sh`
  4. Validate: `bats` green over the scenario fixtures from T2.5.
  5. Success: `[ref: SDD/SDD-AC-4]`; `[ref: SDD/SDD-AC-6]`

- [ ] **T2.2 The merge: add the registration without disturbing anything else**
      `[activity: backend-api]`

  1. Prime: read `modules/satori/scripts/install-hooks.sh:70-99` in full. Take `:70-87` — read the
     whole document, `setdefault` the block, append only when absent, reassign. Reject `:97-99`
     `[ref: SDD/ADR-4]`.
  2. Test: unrelated top-level keys survive byte-identically; a foreign hooks block survives,
     including foreign entries under the *same* event name; non-ASCII values in foreign content are
     unchanged (`ensure_ascii=False` — this repository has already been bitten by the default once);
     an unparseable file causes no write and a diagnosis rather than a traceback; an absent file is
     created containing only our entries; the three hook entries and the `env` switch are all
     present after a successful merge; running twice changes nothing.
  3. Implement: `plugins/tcs-helper/skills/observability-setup/lib/registration.py`, with a
     `--settings <path>` override so tests never touch a real file. *(`install-hooks.sh:22-42` ships
     such an override and nothing tests it; do not repeat that.)*
  4. Validate: `pytest -q` green; every assertion compares the file's full content, not just our
     keys, because the risk being tested is what happens to everything else.
  5. Success: `[ref: SDD/SDD-AC-1, SDD-AC-2, SDD-AC-3, SDD-AC-5]`; `[ref: PRD/F1]`

- [ ] **T2.3 Removal, and the update path ownership makes possible** `[activity: backend-api]`

  1. Prime: read ADR-5 and be clear why exact-string matching cannot support removal after a version
     change `[ref: SDD/ADR-5]`.
  2. Test: removal deletes only entries whose command points inside our namespace; foreign entries
     under the same event names survive; removal on a never-configured target changes nothing and
     exits 0; **removal never deletes records** — asserted by counting record files before and
     after; an entry written by an older bundle version is recognised and removed, not orphaned;
     re-running setup after a version change updates in place rather than appending a duplicate.
  3. Implement: extend `registration.py` with removal and update.
  4. Validate: `pytest -q` green; a round-trip test asserts install → remove leaves the file
     byte-identical to its pre-install content.
  5. Success: `[ref: SDD/SDD-AC-7, SDD-AC-12, SDD-AC-13, SDD-AC-14]`; `[ref: PRD/F2]`

- [ ] **T2.4 Durability: backup, atomic replace, and the lock** `[activity: backend-api]`

  1. Prime: read `install.sh:744-745` and `configure-statusline.sh:181-186` for `mktemp` → `mv`;
     read `plugins/tcs-git-helpers/scripts/lib/lock.sh:45-76` for a bash 3.2 lock via `set -C`, and
     `:108-118` for why release must accept a dead owner — the skill acquires and releases in
     separate processes, so a `pid == $$` check alone leaks the lock after every run
     `[ref: SDD/ADR-4]`.
  2. Test: the real file is never opened for truncation — asserted by checking that the written path
     differs from the final path until the rename; a backup exists after a write and matches the
     pre-write content; an interrupted write leaves the original intact; two concurrent runs
     serialize and neither sees a partial file; a live foreign lock is never force-removed; a stale
     lock (dead PID, or older than the TTL) is reclaimed.
  3. Implement: wrap the merge in backup → temp-write → rename, under the lock.
  4. Validate: `pytest -q` and `bats` green.
  5. Success: `[ref: SDD/SDD-AC-9, SDD-AC-10, SDD-AC-11]`; `[ref: SDD/Quality Requirements]`

- [ ] **T2.5 Phase Validation and the fixture matrix** `[activity: validate]`

  - Build the named-scenario fixtures following `plugins/tcs-git-helpers/tests/fixtures/repos/build.sh:245-386`:
    settings file **absent / empty object / foreign-only / foreign plus ours-current / foreign plus
    ours-older / malformed / non-ASCII / same event names already populated / write path not
    gitignored**. One sanity test per fixture, as `skill_git_setup.bats:251-299` does, so a broken
    fixture fails loudly instead of silently weakening every test that uses it.
  - Run `pytest -q` and `bats plugins/*/tests/bats`.
  - Confirm the suite never writes outside its temp directories: run it with the real home
    write-protected and assert it still passes.

---

## Phase Acceptance Criteria

- Setup and removal are correct across every fixture in the matrix.
- No test touches a real settings file, and the suite passes with the real home write-protected.
- An interrupted write is survivable, demonstrated rather than argued.
