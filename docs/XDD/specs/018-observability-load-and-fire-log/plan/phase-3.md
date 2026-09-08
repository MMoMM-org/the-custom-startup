---
title: "Phase 3: Report, self-check and end-to-end validation"
status: in_progress
version: "1.0"
phase: 3
---

# Phase 3: Report, self-check and end-to-end validation

## Phase Context

**GATE**: Read all referenced files before starting this phase.

**Specification References**:
- `[ref: PRD/F4]` — the report that answers the question
- `[ref: PRD/F8]` — usage against the inventory
- `[ref: SDD/Integration Points]` — why the harness-ingest route is dropped, and what `batch`
  survives as
- `[ref: SDD/Architecture Decisions — ADR-6]` — Python, pytest-covered, offline
- `[ref: SDD/Quality Requirements]` — the honesty requirement

**Key Decisions**:
- The report is offline, so the hook-path budget does not apply. Clarity and test coverage win over
  cleverness here `[ref: SDD/Solution Strategy]`.
- **Superseded 2026-09-06 (T1.4 finding, see README and ADR-7), resolved 2026-09-07:** this bullet
  once described ingesting a **batch** figure from the harness's own telemetry. That route is
  dropped — it would require a locally running OTLP receiver, which collides with CON-6 and the
  Won't-Have "no server component". Hook durations now come only from `timed-wrapper.sh`, always
  `scope_note: single`; see `solution.md`'s Integration Points. The rule the dropped bullet carried
  still holds in its new form: **the report may never present a duration as per-hook attribution
  unless the record says `scope_note: single`** — that is the misreading the whole ADR-7 question
  exists to prevent. T3.4 has been repurposed as the report-side half of SDD-AC-17 and is no longer
  an open question.
- An empty record is a statement about recording, not about loading.
- **Added after phase 2 (T2.1, T2.2), three cases `report.py` did not previously have to handle**
  `[ref: solution.md/Application Data Models]`: (1) `reason` may be an empty string — T2.1 dropped
  a fabricated `session_start` default for a payload missing `load_reason`, so an empty `reason`
  must be counted as unknown, never folded into any named reason's count; (2) `bytes` may be
  absent — a file that could not be stat'ed is written with no `bytes` field at all, never `0`, so
  it must be excluded from a byte-cost total rather than counted as zero cost; (3) a payload with no
  usable `path` produces no `kind: instruction` record at all (T2.1's guard against a phantom entry
  inflating PRD F4's denominator) — `report.py` does not need to filter for this itself, but must
  not assume every record it reads once existed unfiltered upstream.

**Dependencies**: Phase 2 (records must exist to report on). T1.4 has run (see `plan/phase-1.md`):
configuration-only attribution is impossible, so T3.5 is not skipped — it builds the wrapper as
designed. T3.4 no longer depends on the harness-ingest route (repurposed 2026-09-07) and now
depends on T3.5 instead: the wrapper writes the `kind: hook` records the report reads, so **T3.5
runs before T3.4** even though it is numbered after it. T3.1–T3.3 all extend the same
`report.py` and are strictly sequential.

---

## Tasks

Turns the record into the answers #147 needs, and proves the whole path end to end.

- [x] **T3.1 Load report — what loaded, how often, and what never did** `[activity: backend-api]`

  1. Prime: read the record schema and PRD Feature 4 `[ref: SDD/Application Data Models]`
  2. Test: over a fixture log, lists each instruction file with its load count and the reasons
     observed; names configured instruction files that never appear, enumerated from the instruction
     inventory `[ref: SDD/The two inventories]`; distinguishes always-loaded
     from conditionally loaded entries; handles a rotated chain (`.jsonl` plus `.1`–`.3`) as one
     logical record without double-counting; **a record with an empty `reason` is counted as
     unknown, never folded into any named reason's count** (T2.1 dropped the fabricated
     `session_start` default — see this phase's Key Decisions)
  3. Implement: `scripts/observability/report.py`
  4. Validate: `pytest -q` green; the module is importable and unit-testable without a live session
  5. Success: `[ref: SDD/SDD-AC-13]`; `[ref: PRD/F4]`

- [x] **T3.2 Byte accounting and the honesty rule** `[activity: backend-api]`

  1. Prime: read the honesty requirement `[ref: SDD/Quality Requirements]`
  2. Test: reports the measured byte cost of the always-loaded layer separately from conditional
     loads; **given an empty record, reports the recording state rather than "nothing loaded"**;
     given a record whose newest entry is older than the current session, says so; **a record with
     no `bytes` field (T2.1: the file could not be stat'ed) is excluded from the byte-cost total,
     never counted as zero**, and the report states how many records had no measurable size
  3. Implement: extend `report.py`; read the `kind: state` record written by `selfcheck`
  4. Validate: `pytest -q` green, including the empty-input and stale-input cases
  5. Success: `[ref: SDD/SDD-AC-14, SDD-AC-15]`; `[ref: PRD/F4]`

- [x] **T3.3 Inventory join — what never fired** `[activity: backend-api]`

  1. Prime: read PRD F8, the note that a hook supplies only the numerator, and the two inventory
     definitions `[ref: PRD/F8]` `[ref: SDD/The two inventories]`
  2. Test: given the shipped skill and agent inventory and a record, reports coverage as a fraction
     and names the entries that never fired; a skill present in the inventory but absent from the
     record appears as **unused**, not as missing
  3. Implement: extend `report.py` with the inventory scan
  4. Validate: `pytest -q` green
  5. Success: `[ref: SDD/SDD-AC-18]`; `[ref: PRD/F8]`

- [x] **T3.4 Wrapper-sourced hook durations in the report** `[activity: backend-api]`

  > **Repurposed 2026-09-07**, maintainer decision (see the Decisions Log). This task previously
  > ingested the harness's own `hook_execution_complete` output. T1.4 found that route needs a
  > locally running OTLP receiver, which collides with CON-6 and the Won't-Have "no server
  > component", so it is dropped. `solution.md` has already moved on — SDD-AC-17 and the
  > `kind = hook` record shape both read against `timed-wrapper.sh` with `scope_note: single`.
  > This task is now the **report-side half** of SDD-AC-17; T3.5 remains the wrapper itself.

  **Order**: run this task *after* T3.5, so the report is written against records the wrapper
  actually produces rather than against a shape read only from the SDD.

  1. Prime: read the `kind = hook` record shape and the single-scope rule
     `[ref: SDD/Application Data Models]` `[ref: SDD/Integration Points]`
  2. Test: given `kind: hook` records written by `timed-wrapper.sh`, the report shows each duration
     against the one hook invocation that produced it, labelled `scope_note: single`; a record
     carrying `scope_note: batch` — or no `scope_note` at all — is **never** rendered as a single
     hook's duration, which is the misreading ADR-7 exists to prevent; a record with no `kind: hook`
     entries reports that hook timing is not installed, rather than reporting zero hooks
  3. Implement: the hook-duration section of `scripts/observability/report.py`
  4. Validate: `pytest -q` green
  5. Success: `[ref: SDD/SDD-AC-17]`; `[ref: PRD/F6]`

  > **Done — and it exposed the phase's most consequential defect, in T3.5's wrapper rather than
  > here.** `TIMEFORMAT='%3R'` emits SECONDS; the value was written to a field named `ms` and read as
  > milliseconds by both the report and the README, so every duration was 1000x too small. A hook
  > 500x over CON-7's 1 ms budget reported as comfortably under it. Fixed in the writer, so the
  > record itself is honest; the SDD now states the unit instead of leaving it to the field's name.
  >
  > Two blind spots made it invisible, both now closed: every test wrapped a trivially fast command,
  > so nothing asserted a KNOWN duration; and once a known duration was pinned, every test still used
  > a sub-second one, under which dropping the `* 1000` is indistinguishable from correct arithmetic.
  > A `sleep 1.3` case now exercises the integer-seconds term, mutation-verified.

- [x] **T3.5 Per-hook attribution — scope decided by T1.4** `[activity: infrastructure]`

  1. Prime: read T1.4's recorded finding and the updated ADR-7
  2. Test: **only if T1.4 found configuration insufficient** — a wrapped hook's exit status, stdout
     and stderr are byte-identical to the unwrapped hook's, including the exit-2 blocking case; the
     wrapper adds under 1 ms; timing is absent from the record when the wrapper is not installed
  3. Implement: `plugins/tcs-helper/scripts/observability/timed-wrapper.sh` (tracked, alongside
     `logwrite.sh` and the adapters — relocated 2026-09-06, see `solution.md`'s Directory Map and
     the README's Decisions Log; `.claude/observability/` no longer exists as a path), built around
     the three protocol
     constraints — the benchmarked candidate from the research pass discards stdout and stderr and
     loses the exit code, so it is a cost measurement, **not** a template
  4. Validate: bats green; install, reproduce, read, uninstall — and confirm nothing remains in the
     hook path afterwards
  4b. Document the wrapper in `plugins/tcs-helper/scripts/observability/README.md`: how to install it
     for an investigation, what it records and where the record goes, an explicit statement that
     everything is local and nothing is transmitted anywhere, and how to remove it so nothing remains
     in the hook path `[ref: PRD/F6 AC3]` `[ref: PRD/F7 AC3]`

     > **Added 2026-09-07.** These two criteria previously sat in T3.4's step 3, as part of the
     > "documented recipe for the diagnostic run". When T3.4 was repurposed away from the dropped
     > harness-ingest route, that step went with it and no task was left owning F6 AC3 or F7 AC3 —
     > an error in the repurposing, found by the T3.5 spec-compliance reviewer. The duty belongs
     > with the wrapper, so it lands here rather than back in T3.4.
  5. Success: `[ref: SDD/SDD-AC-20]`; `[ref: PRD/F7]`
  6. **Skip condition**: if T1.4 found that per-command matchers do produce separate measurement
     groups, this task is replaced by a configuration change and a note in the SDD. Record which
     path was taken.

  > **Done. Wrapper path taken** — T1.4's finding stands, so the skip condition did not apply.
  > `timed-wrapper.sh` (204 lines) plus 30 bats cases; bats 942 → 972. Three defects were found
  > after the implementation reported green, none of them by its own tests:
  >
  > - **`session` was empty on every record.** The wrapper must never read stdin (a hook's payload
  >   arrives there), so it cannot extract `session_id` the way the three adapters do — silently
  >   breaking the cross-kind join that field exists for. Now taken from `$CLAUDE_CODE_SESSION_ID`,
  >   labelled UNVERIFIED, confirmed at T3.6. Found by running the wrapper and reading its record.
  > - **The privacy statement overclaimed.** It said the only non-measurement strings were the
  >   operator-typed ones, omitting `repo` and `session`. A privacy claim that invites verification
  >   has to survive it. Corrected against a real record.
  > - **CRITICAL: the argument parser could hang the hook path.** `shift 2` with one argument left
  >   is a no-op returning non-zero, so `--event` or `--matcher` as the final argument spun the loop
  >   forever — not fail-open, not fail-closed, but blocking the tool call indefinitely. `${2:-}`
  >   masked the missing value, so the source read as correct. Found by the code-quality reviewer,
  >   in a branch none of the original 23 tests touched.
  >
  > Overhead measured at ~0.9 ms marginal on Linux/aarch64 against CON-7's 1 ms. The absolute
  > end-to-end cost (~13 ms) is the pre-existing writer path every adapter already pays, already
  > recorded in the SDD's Quality Requirements. **The macOS measurement is still outstanding — it
  > is T3.6's overhead gate.**

- [ ] **T3.6 End-to-end validation and the privacy gate** `[activity: validate]`

  1. Run the full suites: `pytest -q` and `bats tests/bats/`, plus the `tcs-git-helpers` bats suite.
  2. Work a normal session with recording enabled, then run the report and check that it answers the
     four questions in PRD Feature 4 against real data rather than fixtures.
  3. **Privacy gate**: scan a record produced by a real session against the deny-list — no file
     contents, no Bash arguments, no hook command strings, no `transcript_path`, no absolute home
     paths `[ref: SDD/Quality Requirements — Privacy]` `[ref: PRD/F3]`.
  4. **Overhead gate**: measure per-hook overhead on macOS and confirm the CON-7 budget holds. The
     research figures came from a Linux container and were explicitly flagged as non-transferable.
  5. Success: every SDD acceptance criterion has passing evidence, and #147 can be answered from the
     report `[ref: PRD/Success Metrics]`.

  > **In progress — steps 1 and 4 are closed, steps 2, 3 and 5 need a recording session.**
  > Recording is read from the environment Claude Code launched in, so it cannot be switched on
  > mid-session; the remaining gates are blocked on a relaunch with `CLAUDE_OBSERVABILITY_ENABLED=1`
  > and a few turns of ordinary work. Confirmed with Marcus 2026-09-07; the fixture route was
  > offered and rejected, because step 3 asks for a real record on purpose.
  >
  > **Step 1 — full suites: green.** pytest 675 passed / 1 skipped; bats 975/975 across
  > `plugins/*/tests/bats` (the `tcs-git-helpers` suite included, it is part of that glob).
  >
  > Two failures were found first and both were real, in T3.5's own suite, not in the wrapper:
  >
  > - **Seven tests never ran on macOS.** They bound a hang guard with `timeout`, which is GNU
  >   coreutils and ships on neither macOS nor a `macos-latest` runner, so they exited 127 instead of
  >   exercising the wrapper. The bats CI matrix includes `macos-latest`, so this was red in CI too.
  >   Replaced with a `_timeout` helper that keeps coreutils' contract and falls back to perl —
  >   forking rather than exec'ing, since an alarm timer survives exec but its handler does not.
  > - **The suite ignored this repo's `TCS_PERF_SLACK` convention** that its three sibling
  >   observability suites all use. Its near-zero bound failed under ordinary CPU contention on a
  >   developer machine, which is what a shared CI runner is. Upper bounds now scale; the lower
  >   bounds do not, because those are what catch the 1000x unit regression.
  >
  > **Step 4 — overhead gate: the budget does NOT hold, and cannot.** Darwin arm64, bash 3.2.57,
  > N=200-300 per configuration, two interleaved passes. Hook run directly ~1.5 ms; wrapped with
  > recording off ~4.5 ms; wrapped with recording on ~41 ms — a marginal ~3.0 ms and ~39.5 ms against
  > CON-7's 1 ms, where Linux measured 0.24 ms and 12.2 ms.
  >
  > Two candidate causes were measured and **refuted**, which is what makes this a platform fact
  > rather than a defect to fix: script size (15019 bytes stripped to 1965 changed nothing —
  > 4477 → 4354 us, inside noise) and early-exit position (hoisting the `ENABLED` check to line 2
  > made it *worse*, 5299 → 6050 us). The cost is spawning a shell interpreter at all: a script whose
  > entire body is `exec "$@"` costs ~4.0 ms. macOS runs a code-signature check per exec and Linux
  > does not, which is the whole gap. Full numbers in the README's Decisions Log, 2026-09-07.
  >
  > One lever was found and deliberately **not** applied: `#!/usr/bin/env bash` → `#!/bin/bash` saves
  > ~1.1 ms per invocation by dropping one exec. It trades PATH portability across every script in
  > the repo, so it wants a decision under the Deviation Protocol, not a quiet edit inside a
  > validation task.
  >
  > **Partial evidence toward the `session` caveat (step 2 closes it).** `CLAUDE_CODE_SESSION_ID` is
  > present in a harness-spawned subprocess and is a 36-character UUID — the same shape as a hook
  > payload's `session_id`. That answers neither half of the caveat on its own: whether it reaches a
  > hook the harness spawns, and whether its value equals the payload's. Both need one wrapped hook
  > in a live session, read side by side with that session's adapter records.
  >
  > **What the next session runs.** Relaunch as `CLAUDE_OBSERVABILITY_ENABLED=1 claude`, confirm with
  > `plugins/tcs-helper/scripts/observability/selfcheck.sh`, work normally for a few turns (load a
  > skill, dispatch a subagent, edit a file), then:
  >
  > ```bash
  > REC="$HOME/.claude/plugins/data/observability-the-custom-startup/observability/events.jsonl"
  >
  > # Step 2 -- the report against real data, not fixtures.
  > python3 scripts/observability/report.py
  >
  > # Step 3 -- the privacy deny-list. Every one of these must print nothing.
  > grep -n "$HOME" "$REC"                    # absolute home paths
  > grep -n 'transcript_path' "$REC"          # transcript path
  > grep -n '/Users/' "$REC"                  # absolute paths by any other route
  > jq -r 'select(.kind=="hook") | .matcher' "$REC" | sort -u   # eyeball: no command strings
  > jq -r 'keys[]' "$REC" | sort -u           # the full field set actually emitted, read once by hand
  > ```
  >
  > The last two are deliberately not `grep`-only: the gate is "no Bash arguments and no hook command
  > strings", and the way that leaks is a field nobody thought to look at. Read the emitted key set
  > against the SDD's Privacy row rather than trusting a pattern to catch it.
