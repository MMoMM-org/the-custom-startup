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

  > **Partly superseded — steps 1 and 4 were closed here; steps 2 and 3 were closed in the
  > 2026-09-08 block at the end of this task, which is the recording session this paragraph asks
  > for. Read this block for the overhead and suite evidence, that one for everything after.**
  >
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

  > **2026-09-08 — the recording session. Steps 2 and 3 closed; step 5 and two criteria remain.**
  > Run under `CLAUDE_OBSERVABILITY_ENABLED=1`, `DETAIL=0`, in this repo, on branch
  > `spec/153-observability-log`. Fourteen records across four kinds.
  >
  > **Step 2 — the report against real data: passes.** `report.py` exits 0 and answers PRD F4 from
  > eleven `instruction` records: five files loaded (`CLAUDE.md` four times, `docs/CLAUDE.md` once by
  > `nested_traversal`, three more by `include`), ten configured files that never loaded, and the
  > always-loaded layer separated from conditional loads at 7038 vs 16193 bytes.
  >
  > Two things the run settled that a fixture could not:
  >
  > - **The join's name form is the qualified one.** The report's matching rule accepts a qualified
  >   *or* a bare name and says so in its own output, "confirmed at T3.6 against a live session".
  >   Now confirmed: `kind: skill` carried `tcs-workflow:verify`, `kind: agent` carried
  >   `tcs-workflow:code-quality-reviewer`. Both qualified. The bare-name tolerance is now known to
  >   be unnecessary rather than merely unproven — tightening it changes report output and the
  >   pytest cases that assert on it, so it is recorded here as a decision, not applied as a cleanup.
  > - **An ad-hoc named subagent is reported honestly.** An `Agent` call carrying a caller-supplied
  >   name recorded `agent_type: ac-evidence-mapper`, matching no shipped inventory entry. The report
  >   named it under "1 record(s) named a skill/agent not found in this inventory" rather than
  >   dropping it silently or counting it toward coverage. That branch had never run on real data.
  >
  > **Step 3 — the privacy gate: passes, five of five.** All three greps returned nothing: no
  > `$HOME`, no `transcript_path`, no `/Users/`. The emitted key set, read by hand against
  > SDD/Quality Requirements/Privacy rather than trusted to a pattern, is exactly: `agent_id`,
  > `agent_type`, `bytes`, `detail`, `enabled`, `kind`, `note`, `parent`, `path`, `reason`, `repo`,
  > `scope`, `session`, `skill`, `ts`. Every entry is a name, a reason, a size or a switch position.
  > Two redactions were confirmed against real input: a User-scope import at
  > `~/Kouzou/standards/general.md` recorded as the bare `general.md`, and every in-repo path
  > recorded repo-relative. **Caveat on the gate's own completeness:** the `matcher` scan was
  > vacuous, because no `kind: hook` record existed yet. It has not really run, and is repeated in
  > the relaunch commands below.
  >
  > **One documentation defect, found and fixed.** The `kind: hook` record carries a nine-field
  > enumeration in the scripts' README. The four adapter kinds had none — `agent_id`, `agent_type`,
  > `scope`, `note`, `enabled`, `parent` and `bytes` appeared nowhere in that file, not even as
  > prose. The prose said what was *kept*, never which fields carry it, so the privacy claim could
  > not be checked field by field the way the wrapper's can. Same class of defect the T3.5 reviewer
  > caught in the wrapper's own privacy statement, in the other half of the document. Fixed by
  > adding a per-kind field table, every entry verified against both the adapter source and a real
  > record.
  >
  > **Step 1 corroborated by an independent review.** `tcs-workflow:code-quality-reviewer` over
  > `f3e49a0..HEAD`, scoped to the six shell scripts: **PASS**, no critical and no warning findings,
  > verified by running the code under bash 3.2.57 rather than by reading it. It independently
  > exercised the rotation chain, the 256-byte multibyte-boundary heal, invalid-UTF-8 rejection, the
  > unwritable-directory fail-open path, and T3.5's missing-final-flag-value branch. One suggestion,
  > not a defect: `log_instructions.sh:56` forks `cat` to read stdin where both sibling adapters use
  > the fork-free `read -r -d ''` form and carry comments justifying it on CON-7 grounds — and this
  > is the adapter that fires most often. Recorded, not fixed; it is a CON-7 question, not a
  > correctness one.
  >
  > **Step 4 corroborated incidentally.** The wrapped adapter measured 43 ms end-to-end on this
  > machine against the ~41 ms the 2026-09-07 gate measured. The macOS finding reproduces.
  >
  > **`session` caveat — second half confirmed, first half still open.** The caveat asks two things:
  > whether `CLAUDE_CODE_SESSION_ID` reaches a harness-spawned hook, and whether its value equals
  > the payload's `session_id`. Running `timed-wrapper.sh` directly in this session wrote
  > `session: 058f9767-67c9-4619-b718-d6a78cbefc11` — byte-identical to what all three adapters
  > extracted from their own payloads in the same session. **The values agree.** What that run
  > cannot show is the first half: it was spawned by the Bash tool, not by the harness as a hook.
  >
  > **The wrapper is now wired, and must be unwired again.** `.claude/settings.json` (gitignored,
  > local only, so this change is invisible to git by design) had its `InstructionsLoaded` command
  > replaced with:
  >
  > ```
  > "$CLAUDE_PROJECT_DIR/…/timed-wrapper.sh" --event InstructionsLoaded --matcher "" -- "$CLAUDE_PROJECT_DIR/…/log_instructions.sh"
  > ```
  >
  > `InstructionsLoaded` was chosen because it fires once per instruction file at session start, so
  > the relaunch produces the `kind: hook` records and that same session's payload-sourced
  > `instruction` records at the same moment — exactly the side-by-side the caveat's first half
  > needs, with no further action asked of the operator.
  >
  > Three things were verified before wiring, so that a relaunch cannot silently lose instruction
  > records: the empty `--matcher ""` parses as a present-but-empty argument and does not trip
  > T3.5's missing-final-value branch; stdin passes through untouched (a wrapped `/bin/cat` echoed
  > its payload byte for byte, which is HAZARD 1 verified live rather than by reading); and the
  > exact wired command line, run against a realistic payload, wrote **both** records — the
  > adapter's `instruction` and the wrapper's `hook`.
  >
  > **To remove it**, once the gate below is recorded: put the original command back —
  > `"$CLAUDE_PROJECT_DIR/plugins/tcs-helper/scripts/observability/log_instructions.sh"`, no flags,
  > no wrapper. That is the whole procedure.
  >
  > **What the next session runs.** Relaunch as `CLAUDE_OBSERVABILITY_ENABLED=1 claude`, then:
  >
  > ```bash
  > REC="$HOME/.claude/plugins/data/observability-the-custom-startup/observability/events.jsonl"
  >
  > # SDD-AC-17 -- a hook record from the real harness path, labelled scope_note single.
  > jq -c 'select(.kind=="hook")' "$REC"
  > python3 scripts/observability/report.py | grep -A 6 "Hook durations"
  >
  > # SDD-AC-5's caveat, first half. These two must print the SAME session id.
  > jq -r 'select(.kind=="hook")        | .session' "$REC" | sort -u | tail -3
  > jq -r 'select(.kind=="instruction") | .session' "$REC" | sort -u | tail -3
  >
  > # The privacy gate's matcher scan, which was vacuous the first time round.
  > jq -r 'select(.kind=="hook") | .matcher' "$REC" | sort -u
  > ```
  >
  > An empty `session` on the hook records answers the caveat too, in the other direction: it would
  > mean the variable does not reach a harness-spawned hook, and that the field's documented
  > empty-rather-than-guess behaviour is what kept it from joining to the wrong session. Record
  > whichever way it lands; both are results.
  >
  > **Two traps for whoever runs the above.** `report.py` takes the data directory as `--data-dir`,
  > **not** from `$CLAUDE_OBSERVABILITY_DATA` — ADR-6 keeps it free of environment dependence so it
  > stays unit-testable, and pointing the env var at it silently reports on the wrong log. And
  > `selfcheck.sh` reports `cannot record` when run through Claude's Bash tool, because the sandbox
  > denies writes under `~/.claude/plugins`; the hooks themselves are harness-spawned and unaffected.
  > Run it with the sandbox disabled before believing it.

  > **Step 5 — the acceptance-criteria evidence map (2026-09-08).** Built by a read-only subagent
  > across `solution.md`, the three phase files, all six bats suites and the pytest file, then
  > spot-verified by hand wherever a claim carried a consequence. **All twenty SDD acceptance
  > criteria carry evidence; none is wholly missing.** Six carried a specific unevidenced or
  > vacuous clause. Two of those were closed by this same session, one is wired and waiting on a
  > relaunch, one is now answered as un-closeable and recorded as such, and two are open decisions.
  >
  > | Clause | State after this session |
  > |---|---|
  > | AC-13, AC-14, AC-15, AC-18 — pytest-over-fixtures only; `report.py` had never run against a real record | **CLOSED.** It has now: exit 0 over fourteen live records from this repo and session. |
  > | AC-9 and the privacy gate — never run against a real record | **CLOSED.** Five of five deny-list items clean, and the key set read by hand against the Privacy row, which is what the gate asks for rather than a pattern match. |
  > | AC-5's exception clause — the wrapper tests set `CLAUDE_CODE_SESSION_ID` themselves, so they prove the wrapper *reads* it, never that the harness *supplies* it | **WIRED, pending relaunch.** The value half is already confirmed (see the block above); the reach half needs the wired hook. |
  > | AC-20 — the six-arrangement numbers are recorded, but the reproduction artifacts sat in a scratchpad | **CLOSED as un-reproducible, deliberately.** See below. |
  > | AC-8 — vacuous in production | **DECIDED 2026-09-08 (maintainer): scope the criterion to the writer.** Applied in three places, because one was not enough — the SDD's AC-8 row, the PRD's Feature 3 criterion, and a new PRD Won't-Have bullet. See below. |
  > | AC-3 — the live half of `path_glob_match` | **DECIDED 2026-09-08 (maintainer): accept the fixture evidence.** No glob rule is added to this repo; the adapter path stays proved by I:192 and the live half stays deliberately unobserved. See below. |
  >
  > **AC-20 is closed the only honest way left: the artifacts are gone for good.** README line 141
  > points at `/tmp/claude-1001/…/scratchpad/t14/`. That path does not exist — and neither does
  > `/tmp/claude-1001`, the entire uid namespace. T1.4 ran inside the Docker container (uid 1001);
  > this repo's host sessions run under uid 501, so the spike's settings, collector, run script and
  > raw OTLP capture were never on this filesystem and cannot be recovered by anyone. **The
  > arrangement table at README:144-152 is therefore not a summary of the evidence — it IS the
  > evidence, and the only surviving copy.** AC-20 asks that the negative finding be written down
  > rather than quietly dropped, and it was, so the criterion itself is met. What is not available,
  > and never will be, is independent reproduction. Recorded here so that a future reader learns
  > this from the spec rather than by following a dead path.
  >
  > **AC-8 is vacuous in production, and the PRD does not admit it.** The writer's reduce helper
  > keeps a Bash call's program name and drops its arguments — proved at W:1271 and W:1291. But no
  > shipped adapter records Bash calls at all: there is no `log_bash.sh`, and this repo's hook
  > registration carries `PreToolUse` under matcher `Skill` only. The criterion is written
  > conditionally ("*when* a Bash tool call is recorded"), so in production it is vacuously
  > satisfied. The problem is that PRD Feature 3 carries the same criterion and the Won't-Have list
  > never mentions Bash recording, so the spec neither ships this nor declares it out of scope. A
  > reader reasonably concludes their Bash command lines are recorded with arguments stripped.
  > Nothing records them at all. This wants a decision rather than a fix: scope the criterion to
  > the writer in both documents, or register a Bash adapter if it was meant literally.
  >
  > **AC-3's live half has never been observed.** `reason: path_glob_match` and its `trigger` field
  > come only from a fixture payload (I:192). The live log's reasons are `include` ×6,
  > `session_start` ×4 and `nested_traversal` ×1 — no glob match, because this repo has no
  > `.claude/rules/` entry carrying `globs:` for one to fire from. That is an unexercised path, not
  > a defect in the adapter. Closing it means adding such a rule, reading a matching file in an
  > enabled session, and confirming a record with `reason: path_glob_match` and a populated
  > `trigger` — a configuration change to this repo, so it is a decision rather than a task step.

  > **Step 1, re-run 2026-09-08 — one real defect found in this suite's own timing bound.**
  > pytest stayed at 675 passed / 1 skipped. The wrapper suite did not: "a near-zero duration
  > records ms as 0" failed four runs in five on a developer machine, while every other case
  > passed. The wrapper was not at fault — measured directly, it records a flat 5 ms.
  >
  > **The cause is macOS's first-exec cost, measured rather than assumed.** A newly written
  > executable pays a code-signature validation on its FIRST exec, cached thereafter. Across three
  > fresh files: exec 1 cost 286, 151 and 154 ms; execs 2 through 5 of the same file cost 5 ms
  > each. A 30-57x penalty, once per file. `setup()` writes the fixtures fresh for every test, and
  > this test execs one exactly once — so it measured the penalty, never the wrapper. The 150 ms
  > bound sits inside that 151-286 ms spread, which is why it failed most runs rather than all.
  >
  > **The more useful half of the finding is why CI never saw it.**
  > `.github/workflows/tests.yml:142` sets `TCS_PERF_SLACK=4`, lifting the bound to 600 ms. The
  > penalty fits under that comfortably, so the suite is green in CI and red on the maintainer's
  > machine. A multiplier that exists to absorb CPU contention was also absorbing a deterministic
  > platform constant — and in doing so, hiding it. This is the second time this one suite's timing
  > bounds have needed correcting (see the 2026-09-07 block above, where the same suite ignored the
  > `TCS_PERF_SLACK` convention its three siblings follow); both times the bound was treated as the
  > thing to adjust. It was not, either time.
  >
  > **Fixed by warming the fixtures in `setup()`**, not by widening the bound — a throwaway exec of
  > each fixture, with stdin from `/dev/null` because `cat_and_exit.sh` reads stdin and would
  > otherwise block `setup()` rather than fail it. The assertion now measures what it claims and
  > holds with or without slack. Verified across eight consecutive suite runs: zero failures,
  > against four-in-five before. One green run would not have been evidence for an intermittent
  > failure, so it was not accepted as such.
