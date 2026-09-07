# Specification: 018-observability-load-and-fire-log

## Status

| Field | Value |
|-------|-------|
| **Created** | 2026-09-06 |
| **Current Phase** | Ready |
| **Decomposition tier** | Incremental |
| **Last Updated** | 2026-09-07 |

## Documents

| Document | Status | Notes |
|----------|--------|-------|
| requirements.md | completed | 8 features across all MoSCoW tiers, 32 acceptance criteria, 4 review decisions folded in |
| solution.md | completed | 7 components, 8 ADRs (4 user-confirmed), 20 acceptance criteria, full PRD traceability; revised after validation |
| plan/ | completed | 3 phases, 17 tasks, 69 spec references, 3 parallel |

**Status values**: `pending` | `in_progress` | `completed` | `skipped`

**Decomposition tier**: `Direct` (no plan) | `Incremental` (phase plan). Set by the classifier at the decomposition step and confirmed by the user; leave the placeholder until then. Read back by `spec.py --read`, which treats anything it does not recognise as absent.

## Decisions Log

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-09-06 | Spec opened for #153 | Instrumentation touches hook config, a wrapper, a log schema and reporting — more than two files, and the repo's standing rule is spec-first rather than ad-hoc implementation |
| 2026-09-06 | Native telemetry is evaluated before any custom instrumentation is written | Avoids reimplementing what the harness already emits |
| 2026-09-06 | Research mode: Standard, four parallel perspectives (Technical, Integration, Performance, Security) | User choice over the no-fan-out option; the measured findings below are what it bought |
| 2026-09-06 | Data protection is a first-class PRD requirement with an opt-out, not an SDD afterthought | User decision. The log would otherwise carry full Bash command lines and hook command strings by default |
| 2026-09-06 | Build our own; adopt no third-party observability project | None of the surveyed projects covers instruction loading, and all the dashboard-shaped ones require a standing server, DB and browser UI. See Research § Prior art |
| 2026-09-06 | Record lives per repo, outside the working tree | Follows spec 011 ADR-7. Keeps projects' records separate and makes exclusion from git structural rather than ignore-file discipline. Rejected: one cross-repo record, which answers "which skills do I ever use" better but mixes client contexts |
| 2026-09-06 | Repo-local configuration this phase; not shipped in a plugin | #147 needs the evidence here. Shipping would bind us to a schema and defaults before either has been used in anger, and make every later change breaking for people who never asked for the feature |
| 2026-09-06 | Harness hook timing only in deliberate diagnostic runs | Its no-infrastructure export writes to the terminal, which is unacceptable interactively. Rejected: filtering the noise, which adds a filter that floods the terminal when it breaks |
| 2026-09-06 | Start in reduced (non-detailed) mode | Widen only when the report proves thin — then we know which field was actually missing, instead of recording everything on the assumption some of it matters |
| 2026-09-06 | ADR-1: self-contained writer in the repo, not sourced from the plugin | `CLAUDE_PLUGIN_ROOT`/`CLAUDE_PLUGIN_DATA` never reach Bash-tool subprocesses and the plugin cache resolves stale in-session — both already documented here. Sourcing would make the hook silently write nowhere. A bats parity test holds the duplicated resolver honest |
| 2026-09-06 | ADR-3: phase 1 covers instructions, skills and agents | All three share one writer, so skills and agents cost one config entry each and deliver the "which skills ever fire" number immediately |
| 2026-09-06 | ADR-6: report in Python with pytest coverage | It runs offline where the hook-path budget does not apply, and the repo already runs pytest on both OSes — the analysis becomes testable rather than merely runnable |
| 2026-09-06 | ADR-7: per-hook attribution deferred behind a verification task | It is not established that one-matcher-per-command yields separate measurement groups; the harness groups by (event, matcher) and `tcs-helper` already puts two commands under one matcher. Specifying a mechanism now risks specifying something inexpressible |
| 2026-09-06 | Decomposition tier: **Incremental** (classifier recommended Incremental; user confirmed) | Rule 1 fired on breadth: 6 new components in the Building Block View and 4 Must-Have features, 32 acceptance criteria. `parallel_markers` was taken as false conservatively — the three adapters are independent but the SDD does not declare parallel streams. Direct was rejected because redaction and fail-open behaviour span several components, and those are the parts with safety consequences if one slips |
| 2026-09-06 | **Correction**: the `claude_code.hook` OTel span is NOT reachable and must not be designed around | Its guard is `gt() = Lb() \|\| vj()`, and `vj(){return!1}` is hard-coded false with a single definition in the binary. `Lb()` additionally needs the undocumented `ENABLE_BETA_TRACING_DETAILED` + `BETA_TRACING_ENDPOINT` **and** an Anthropic-side statsig gate. An earlier note in this file assumed the span was usable; it is not |
| 2026-09-06 | **Correction** (T1.4): `hook_name` is `${event}:${toolName}`, not `${event}:${matcher}`; `OTEL_LOGS_EXPORTER=console` is inert in Claude Code 2.1.252 | The verification spike measured all six arrangements directly against captured OTLP payloads. Both were previously stated as verified in this file's research findings; they were not — see the T1.4 section above |
| 2026-09-06 | Feature 7 (per-hook attribution) is routed to `timed-wrapper.sh`; no longer deferred | T1.4 found configuration-only attribution empirically impossible — arrangement B shows two entries with distinct matchers still collapsing into one measurement group |
| 2026-09-06 | Feature 6's mechanism changes to the same timing wrapper; the harness-telemetry ingest route is dropped | Reliable capture now needs a local OTLP receiver, which collides with CON-6 ("no collector, no daemon, no database") and the Won't-Have "no server component". F6's user story explicitly asked for durations "without installing anything into the hook path" — that promise is given up. F6 and F7 now collapse into one deliverable served by one component |
| 2026-09-06 | **Correction** (T1.3): the SDD's specified `_field` extractor is incomplete — it leaks on an empty key | Given `key = ""` against a payload carrying a legal empty-string key (`"":"value"`), the prefix-removal pattern matches, the absent-key guard never fires, and the extractor returns that value. The absent-key guard does not subsume an empty key. A second, independent guard (`[ -n "$key" ] || return`, checked before prefix removal) is required and is now part of the specified contract, pinned by a dedicated test. See `solution.md` Implementation Examples |
| 2026-09-06 | **Correction**: the SDD's Implementation Examples overstated the absent-key guard's consequence | It previously said that without the guard, the result is "a record containing the entire payload — including... the full command line." Measured: with the guard removed, `_field` returns `{` for any well-formed JSON payload — `${body%%\"*}` truncates at the first `"` byte, which sits right after the opening brace. The "entire payload" outcome needs a payload with zero quote characters, i.e. malformed input. The guard itself is still correct and kept; only its stated justification is corrected |
| 2026-09-06 | Accepted deviation from ADR-5: the `ts` field still forks `date` once per record | bash 3.2 has no fork-free wall clock (`printf '%()T'` needs 4.2, `EPOCHSECONDS` needs 5.0). Measured: `date` ≈ 370 µs, `git rev-parse` ≈ 567 µs — one record already costs ~937 µs of CON-7's 1 ms budget before script startup, and T2.1's `bytes` stat adds a fourth fork. The `bytes` stat is therefore no longer "the one deliberate fork in the hook path" as `solution.md` previously called it; corrected there |
| 2026-09-06 | **Correction**: the writer and its test suite are relocated from `.claude/observability/` and `tests/bats/` to `plugins/tcs-helper/scripts/observability/` and `plugins/tcs-helper/tests/bats/`; T1.5's CI-glob widening is reverted | The SDD's Directory Map placed `logwrite.sh` at `.claude/observability/logwrite.sh`. `.gitignore:2` ignores `.claude/` wholesale, so the file was untracked, with no installer — it existed on one developer's machine only and nothing would recreate it on a fresh clone. This surfaced when T1.5 wired the new suite into CI: all 50 tests failed on both `ubuntu-latest` and `macos-latest` with `logwrite.sh: No such file or directory`, because CI's checkout does not contain the untracked file; the tests had only ever passed locally. The SDD contained both halves of this contradiction — its own Directory Map note said `report.py` lives under a tracked path "precisely because [it] must be reviewable and CI-covered," while placing the CI-covered writer somewhere that note's own logic excluded. The repo's actual, pre-existing convention — which this spec had departed from — is that a hook script with tests lives tracked under `plugins/<name>/`, with its tests under `plugins/<name>/tests/bats/`, which is exactly the shape CI's `plugins/*/tests/bats` glob already expects. Resolution (user decision): the writer moves to `plugins/tcs-helper/scripts/observability/logwrite.sh` and the suite to `plugins/tcs-helper/tests/bats/observability-writer.bats`, both tracked; `.github/workflows/tests.yml` reverts to its original `bats --recursive --print-output-on-failure plugins/*/tests/bats` — the widening T1.5 added is no longer needed and would break CI once `tests/bats` stops existing, since bats errors on a nonexistent path; the suite's `setup()` now derives `REPO_ROOT` via `git -C "$BATS_TEST_DIRNAME" rev-parse --show-toplevel` rather than counting `../..` levels, so a future move cannot silently break it again. This is a location change only: the writer is still self-contained per ADR-1, whose core decision (do not source `plugin_data.sh` at runtime from the plugin cache) is unaffected — see `solution.md`'s ADR-1 premise correction for the distinction between where the source lives in git and what a hook command points at when it runs. **This does not ship the capability**: publication still requires merging the PR and bumping `plugins/tcs-helper/.claude-plugin/plugin.json`, neither of which has happened; CON-8 and the PRD's Won't-Have both still hold |
| 2026-09-07 | **Correction** (T2.3): `parent_agent`'s payload source is unreachable by any means found so far — `log_agent.sh` carries it under an UNVERIFIED guessed key | The official hooks documentation and the shipped binary both come up empty: `agent_id`/`agent_type` identify only the current subagent, and the binary's one `parent_agent_id` string sits in unrelated team/inbox message-routing code, not a hook payload — the same dead-telemetry shape T1.4 already found for `claude_code.subagent.spawn`. `AGENT_PAYLOAD_KEY_PARENT="parent_agent_type"` in `log_agent.sh` is a guess by analogy, not a verified field. T2.4 must settle this: either the payload carries a parent field under some name, or `parent_agent` is removed from the record shape as unobtainable |
| 2026-09-07 | **Correction**: `_observability_field` treats a lookup key as a glob PATTERN, not a literal, because `$key`'s expansion is unquoted inside `${payload#*\"$key\":\"}` | Measured divergence: key `a*b` against payload key `axb` reads as present when it should be absent; key `a[b]` against literal payload key `a[b]` reads as absent when it should be present. No current caller passes a key with glob metacharacters, so nothing is broken today, but the function is the one `solution.md` itself calls "the redaction-critical line of the whole design." The fix quotes the key at both match sites — a deliberate semantic tightening, found while designing the fix for the same function's quadratic-cost-on-absent-key performance defect, and tested as its own behaviour change rather than folded silently into that performance commit |
| 2026-09-07 | T2.1 drops the fabricated `session_start` default for a payload missing `load_reason`; `reason` may now be an empty string | A missing `load_reason` is an anomaly — harness drift, a malformed payload — never verified absent at either real emission site. Defaulting it would make the anomaly permanently indistinguishable from a genuine `session_start` once it reaches `report.py`, exactly the "records wrong things" failure CON-9 forbids. `report.py` must count an empty `reason` as unknown. Same now-consistent posture as `bytes` (absent, never `0`, when unmeasurable) and the no-path guard (no record at all, rather than a phantom one) |
| 2026-09-07 | **Evidence, resolving an open question**: the `Skill` payload's key is `skill` — `{"skill":"<name>"[,"args":"..."]}` | Established from 358 real `Skill` tool_use invocations across session transcripts on this machine, all one shape. `log_skill.sh` holds it as a named constant, not inlined, so a T2.4 correction is one line if the direct hook-payload key ever differs. The transcript-input/hook-`tool_input` equivalence itself remains a well-supported inference, not a measurement — T2.4 confirms it directly |
| 2026-09-07 | **Correction** (T2.4, supersedes the 2026-09-07 T2.3 row above): `parent_agent` is REMOVED from the record shape as unobtainable, not merely unverified | Three independent lines of evidence, all agreeing: (1) the shipped CLI binary's only `parent_agent_id` string sits inside `claude_code.subagent.spawn`, telemetry T1.4 already proved dead (`vj()` hard-coded `false`); (2) the live hook documentation lists only `agent_id`/`agent_type` for a subagent, never a parent; (3) a real nested dispatch, measured live in a scratch repo with the three adapters registered — a `general-purpose` subagent (`a7442d09bc92dcfb3`) that itself dispatched an `Explore` subagent (`a6fcabd09ca9ea3ab`) five seconds later — produced a `SubagentStart` payload for the nested one carrying no parent-shaped field under any name; the adapter correctly omitted it rather than emitting an empty one. `log_agent.sh`'s `AGENT_PAYLOAD_KEY_PARENT` constant, its extraction, and the conditional `parent_agent=` branch are removed; `solution.md`'s `kind = agent` record shape and `observability-agent.bats` are updated to match. Nested dispatches are linked by `session` plus timestamp ordering, not by a parent field |
| 2026-09-07 | **Confirmed** in the same live measurement: `agent_type`/`agent_id` are real and correctly populated, and the skill adapter's `tool_input` key is genuinely `skill` | A real `SubagentStart` payload yielded `agent_type: "Explore"`, `agent_id: "a00fbef40074f47c6"` — previously only citation-verified against the hooks documentation, not seen on a live payload. A real `PreToolUse` payload for a `Skill` tool call produced `{"kind":"skill","skill":"dataviz"}`, confirming the 2026-09-07 evidence row above (358 transcripts) against the direct hook-payload shape rather than just the transcript inference |
| 2026-09-07 | **T3.4 repurposed, not dropped** (maintainer decision, opening phase 3): it becomes the report-side half of SDD-AC-17 — `report.py` reads the `kind: hook` records `timed-wrapper.sh` writes and renders each duration only when the record says `scope_note: single` | The task was written around ingesting the harness's own `hook_execution_complete` output, the route T1.4 found requires a locally running OTLP receiver (CON-6, and the Won't-Have "no server component"). `solution.md` had already moved on — SDD-AC-17 and the `kind = hook` record shape both read against `timed-wrapper.sh` — so only the plan's task text was stale, and the criterion needed a task to own it. Folding it into T3.5 instead was rejected: that would put a bash wrapper and a Python report under one review pass. Execution order in phase 3 is therefore T3.1–T3.3, then T3.5, then T3.4, then T3.6 — T3.4 reads what T3.5 writes |
| 2026-09-07 | **Inventory widened** (T3.1 review): the instruction inventory now includes every nested `CLAUDE.md` within the repo, excluding any under a `tests/fixtures/` path segment | The SDD's first inventory bullet — "the CLAUDE.md hierarchy from the repo root upward" — is literal, reaching the root file, its parent directories and `~/.claude/`, but never a subdirectory `CLAUDE.md`. Meanwhile `nested_traversal` is one of the five verified `load_reason` values, so the record demonstrably captures those files loading. That asymmetry is the defect: a nested `CLAUDE.md` could reach the numerator but never the denominator, making one that NEVER loads invisible to PRD F4's "configured but never loaded" — the exact dead weight #147 exists to find. Two real instances here (`docs/CLAUDE.md`, `docs/ai/CLAUDE.md`); the fixtures exclusion keeps `doc-product`'s sample from inflating the count. Surfaced by the T3.1 spec-compliance reviewer as an ambiguity flagged for awareness only, escalated rather than accepted, and confirmed a real gap |
| 2026-09-07 | **Inventory walk now respects `.gitignore`** (T3.1, found while landing the row above): a path git ignores is not this repo's configuration; determined by `git check-ignore` at walk time, fail-open and stated when git is absent | Widening the walk to nested files exposed it: the gitignored `claude-docker-home/` mount holds a marketplace checkout OF THIS SAME REPO, so the walk counted `CLAUDE.md`, `docs/CLAUDE.md` and `docs/ai/CLAUDE.md` twice each plus the mount's own — 4 of 21 entries (19%), each of which would then report as "never loaded". The duplicates are of the very files the report reasons about, so they corrupt the answer rather than padding a total; and the mount is one machine's artifact, so a fresh clone or CI would compute a different denominator from identical sources. Extending the hard-coded skip list was rejected as the "maintained manifest" the SDD's own `method:` line refuses — it would drift the moment a mount is renamed. Cost is one subprocess in a report that is offline by ADR-6, where CON-7 does not apply |
| 2026-09-07 | **Nested skills excluded from the coverage denominator but reported as UNREACHABLE** (T3.3); the bare/qualified name join is deliberately tolerant until T3.6 measures which form a real record carries | `plugins/tcs-team/` ships 15 `SKILL.md` files two levels deep and no one-level skills. All 15 declare `user-invocable: true`, yet no `tcs-team` skill appears in a live session's skill listing while its agents do — so the plugin is installed and only the skills are invisible; nesting depth is the only structural difference from plugins whose skills do appear. Counting them would park 15 entries in "never fired" forever, reading as unused when the truth is unreachable — different problems, different fixes, the same category error the batch/single distinction exists to prevent. They are named separately with a count instead, because 15 dead files is the dead weight #147 exists to find. Filed as issue #155; restructuring `tcs-team` is not this spec's business |
| 2026-09-07 | **`kind: hook` records take `session` from `$CLAUDE_CODE_SESSION_ID`, not the payload** (T3.5); marked UNVERIFIED until T3.6 measures it live | `timed-wrapper.sh` must never read stdin — a hook's JSON payload arrives there, and consuming it would hand every wrapped hook an empty payload in every session for as long as the wrapper is installed. So the wrapper cannot extract `session_id` the way the three adapters do. Measured consequence: hook records were written with `session:""`, which silently breaks the cross-kind join the field exists for and sits badly with SDD-AC-5. `$CLAUDE_CODE_SESSION_ID` is present in the environment, costs no fork, and is absent-safe — but that it reaches a harness-spawned hook, and that it equals the payload's `session_id`, are assumptions. Labelled UNVERIFIED in code and spec rather than asserted, the way the `skill` key was handled and confirmed at T2.4 — deliberately NOT the way `parent_agent` was guessed by analogy at T2.3 and disproven at T2.4. Found by running the wrapper by hand and reading the record it produced, not by a test |
| 2026-09-07 | **Correction to the T3.4 repurposing**: PRD F6 AC3 and F7 AC3 (documenting the wrapper's configuration, what it records and where, that nothing is transmitted, and how to remove it) are reassigned to T3.5 step 4b | Both criteria sat in T3.4's original step 3 as part of the "documented recipe for the diagnostic run". Repurposing T3.4 away from the dropped harness-ingest route removed that step and left no task owning either criterion — a gap introduced by the repurposing itself, not present before it. Caught by the T3.5 spec-compliance reviewer, which noticed the observability README still documents only the three phase-2 adapters. The duty belongs beside the wrapper it describes, so it lands in T3.5 rather than returning to T3.4 |

## Validation round — 2026-09-06

Four validators ran against the finished spec (completeness, consistency, coverage/ambiguity,
alignment). Combined: **29 PASS, 20 WARN, 10 FAIL**. Every FAIL and every actionable WARN is fixed;
the findings are recorded here because several were defects in *my own* reasoning and are worth not
repeating.

**The sharpest defect — the headline number had no source.** `bytes` (the size of a loaded
instruction file) is what PRD F4's byte-cost accounting reports, and it is the number #147 actually
needs. It is **not** in the harness payload, no task computed it, and the reduced-mode keep/drop
table did not mention it — so under the only configuration this phase enables, the central promise
could not have been met. Fixed: the adapter now stats the path itself (one deliberate fork, budgeted
and justified), `bytes` is classified reduced-mode-safe, and T2.1 carries it as a success criterion.

**Four values were used as if defined and were not**: the truncation limit (now 256, matching
`audit_log.sh`), the two switch names (now `CLAUDE_OBSERVABILITY_ENABLED` and
`CLAUDE_OBSERVABILITY_DETAIL`), and the two inventories that supply the denominator for "never
loaded" and "never fired" (now specified as filesystem walks with their exact globs). None of these
would have failed review as vague prose — they sat inside otherwise crisp Gherkin, which is the more
dangerous shape.

**A plan defect that would have shipped green**: the new bats suite was placed at `tests/bats/`,
which CI's `plugins/*/tests/bats` glob cannot reach. The tests would have passed locally and never
run in CI — under a checklist where I had ticked "project commands are accurate". T1.5 now extends
the glob.

**A justification of mine was overstated.** The SDD claimed `audit_log.sh` forks `sed` once per
field, "roughly nine processes per line", to justify a leaner writer. Traced with `bash -x`: that is
its *fallback* path; with `jq` present there are zero `sed` forks. The real saving is the `jq` fork
(~21 ms) and avoiding BSD `date`. Corrected in place, with the correction left visible.

**Two gaps in edge-case coverage**: non-UTF-8 bytes in POSIX paths (JSON requires UTF-8 — now CON-10,
with a stated strategy at both write and read time) and control characters in the JSON escaper (a
literal newline in a path would have split a record across two lines and broken every reader).

**Also fixed**: rotation under concurrent sessions (documented as an accepted loss rather than
locked, with the reason), recursion stated as impossible by construction (CON-11), template sections
that had been silently merged in `solution.md`, terminology overloading "record" for both one line
and the whole file, and a missing task for the user-facing documentation the PRD promises three
times.

**One pre-existing drift, reported not fixed**: spec 011's ADR-7 text says rotation keeps two
generations; its shipped `audit_log.sh` keeps three. This spec follows the code and says so — fixing
spec 011's text is spec 011's business.

## Context

Issue: [#153](https://github.com/MMoMM-org/the-custom-startup/issues/153) — observability: log what
actually loads and fires — instructions, skills, agents, hooks. Downstream consumer:
[#147](https://github.com/MMoMM-org/the-custom-startup/issues/147), which cannot decide memory-bank
routing without a denominator.

## Research findings (Claude Code 2.1.252, verified against the shipped binary)

### What the harness gives us natively

| Source | Native coverage | Mechanism |
|---|---|---|
| **Hooks** | yes, incl. duration — but per *(event:tool)* **batch**, not per command, and not per matcher either | OTel **log events** `hook_execution_start` / `hook_execution_complete`, the latter carrying `total_duration_ms`, `num_success`, `num_blocking`, `num_non_blocking_error`, `num_cancelled`. Reachable **only** via the documented `CLAUDE_CODE_ENABLE_TELEMETRY=1` + `OTEL_LOGS_EXPORTER=otlp` against a listening receiver — `OTEL_LOGS_EXPORTER=console` is inert in 2.1.252 (see the T1.4 finding below). `hook_definitions` (the configured command strings) never appears, even with `OTEL_LOG_TOOL_DETAILS=1` |
| **Skills** | yes | `claude_code.tool.execution` span carries `skill_name`; reachable via the documented `CLAUDE_CODE_ENHANCED_TELEMETRY_BETA=1` + `OTEL_TRACES_EXPORTER` |
| **Agents** | **no** | `claude_code.subagent.spawn` exists but is dead code — its only guard is `vj()`, hard-coded `false`. Agent identity must come from our own `SubagentStart` hook payload |
| **Instructions** | **no** | The `InstructionsLoaded` payload never enters telemetry; only "a batch ran" does. Our own hook is required — which is the original purpose of #153 |

`hook_name` is `` `${event}:${toolName}` ``, **not** `` `${event}:${matcher}` `` as an earlier version
of this table stated — see the T1.4 finding below. `num_hooks` is the count of registered commands
sharing that *tool*, not that matcher: two entries with two distinct matcher strings that both match
the same tool still collapse into one measurement group. **Consequence:** hooks sharing a tool can
never be told apart by configuration alone, regardless of how their matchers are written.

### T1.4 — the ADR-7 verification spike: per-hook attribution is not configurable

Six hook configurations run through nested `claude -p` sessions against a local OTLP receiver,
capturing the harness's own `hook_execution_complete` log records, with payloads independently
verified. Reproduction artifacts (settings, collector, run script, raw OTLP capture, marker files,
debug logs) are at
`/tmp/claude-1001/-Volumes-Moon-Coding-the-custom-startup/c6f9a186-9dd6-4fe8-b0ff-02ae99c27674/scratchpad/t14/`
— not checked into the repo.

| Arr. | configuration | `hook_name` | `num_hooks` | `total_duration_ms` |
|---|---|---|---|---|
| A | 2 entries, both matcher `Read` | `PreToolUse:Read` | 2 | 407 |
| B | 2 entries, matchers `Read` and `Read\|Glob` | `PreToolUse:Read` | 2 | 410 |
| C | 1 entry, matcher `Read`, 2 commands | `PreToolUse:Read` | 2 | 406 |
| D | 1 entry, matcher `Read\|Glob`, 1 command | `PreToolUse:Read` | 1 | 56 |
| E | 1 entry, matcher `.*`, 1 command | `PreToolUse:Read` | 1 | 63 |
| F | 2 entries, both matcher `Read`, both sleeping 0.40s | `PreToolUse:Read` | 2 | 406 |

Hook commands slept 0.05s and 0.40s except in F. Exactly one `hook_execution_start`/
`hook_execution_complete` pair fired per run in every arrangement; marker files confirm both
commands actually ran in A, B, C and F.

**Finding 1 — one measurement group; a per-command matcher is not expressible.** B is the decisive
negative: two entries with two *distinct* matcher strings still collapse into ONE record with
`num_hooks=2`. Splitting hooks onto separate matchers — the cheaper alternative PRD F7's fourth
acceptance criterion asked to evaluate first — does not produce separate measurement groups.

**Finding 2 — `hook_name` is `${event}:${toolName}`, not `${event}:${matcher}`.** D and E prove it:
matcher `Read|Glob` and matcher `.*` both report `PreToolUse:Read`. The matcher string can never
appear in the label. This corrects the claim previously stated as verified in the table above.

**Finding 3 — hooks in a group run in parallel; subtraction cannot recover per-hook duration
either.** F: two 0.40s hooks total 406 ms, not ~800 ms, with marker timestamps 1.02 ms apart.
`total_duration_ms` is approximately the max of the group, not the sum.

Every captured OTLP payload was grepped for the hook command strings: zero hits. `hook_definitions`
never appears, even with `OTEL_LOG_TOOL_DETAILS=1`. The complete attribute set on hook events is:
`hook_event, hook_name, hook_matcher, hook_source, hook_type, num_hooks, num_success, num_blocking,
num_non_blocking_error, num_cancelled, total_duration_ms, managed_only, safe_mode, prompt.id,
session.id, event.{name,sequence,timestamp}, user.*, organization.id, terminal.type`. `hook_matcher`
does exist as an attribute — but per Finding 1, two entries sharing an event still collapse into one
record regardless of matcher, so it still yields no per-command identity.

**A new discovery worth recording**: an undocumented `hook_registered` log event fires once per
registered command at session start, carrying `hook_event`, `hook_matcher`, `hook_source`
(`userSettings` / `flagSettings` / `merged`) and `hook_type` — a free load-time inventory of
registered hooks, directly relevant to the "never fired" denominator PRD F8 needs. It carries no
command string, so two commands sharing an entry remain indistinguishable by it.

**A second correction, independently verified: `OTEL_LOGS_EXPORTER=console` is inert in Claude Code
2.1.252.** It yields `getOtlpLogExporters: types=[], protocol=undefined, endpoint=undefined`, then
`Created 0 log exporter(s)`, then `[WARN] [3P telemetry] Event dropped (no event logger
initialized)`. Nothing is ever printed. Only `otlp` is accepted, and that requires a listening
receiver — which is why Feature 6's original harness-telemetry route (see Decisions Log below) is
dropped in favour of the timing wrapper. Also confirmed: `--debug-file` output carries no hook
durations at all (only `tool_dispatch_end … durationMs` for tool calls), so it cannot substitute
either.

### `InstructionsLoaded` — the load-bearing primitive

Real hook event since CLI 2.1.69 (2026-03-04). Payload: `{file_path, memory_type, load_reason,
globs, trigger_file_path, parent_file_path}` on top of the base `{session_id, transcript_path, cwd,
prompt_id}`. Five `load_reason` values, verified at both emission sites in the binary:

- lazy: `let k = d.globs ? "path_glob_match" : d.parent ? "include" : "nested_traversal"`
- eager: `session_start` (default) and `compact`, via `llr()` / `nextEagerLoadReason`

`load_reason` doubles as the hook matcher. The eager path runs only under `hasInstructionsLoadedHook`
— **with no hook registered the harness does no work, so the instrument costs nothing while off.**

### Privacy — two independent channels

The `OTEL_LOG_*` family (`OTEL_LOG_TOOL_DETAILS`, `OTEL_LOG_USER_PROMPTS`,
`OTEL_LOG_ASSISTANT_RESPONSES`, `OTEL_LOG_TOOL_CONTENT`, `OTEL_LOG_RAW_API_BODIES`, all default off)
governs **only** Anthropic's own OTel export. **Hook stdin JSON is delivered in full, always, with no
env var that redacts it** — and that is our primary source. Redaction therefore has to be ours.

Ranked leak risk in hook stdin: Bash `tool_input.command` (full command line, inline secrets) >
Write/Edit `file_path` + `content`/`new_string` > `cwd` and `transcript_path` on *every* event >
`InstructionsLoaded` absolute paths.

Claude Code's own split is worth copying: it always records `bash_command` (just `argv[0]`) and gates
only `full_command` (the whole line) behind a flag.

Enabling local telemetry sends **nothing** to Anthropic — that is a separate channel
(`[Anthropic telemetry]` vs `[3P telemetry]` in debug output) with its own opt-outs
(`DISABLE_TELEMETRY`, `DO_NOT_TRACK`, `CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC`).

### Storage — existing precedent in this repo

`tcs-git-helpers` already solved the equivalent problem (ADR-7, spec 011): append-only JSONL under
`${CLAUDE_PLUGIN_DATA}/audit/`, i.e. **outside the repo tree**, size-based rotation at 1 MB through
`.1`/`.2`/`.3`, fields truncated to 256 chars with a `*_truncated` flag. Out-of-tree is structurally
stronger than gitignored: `git add -A` cannot reach it.

### Performance — measured, not estimated (Linux container; absolute figures do not transfer to macOS)

| Approach | Cost per hook invocation |
|---|---|
| bash builtin `time` + `TIMEFORMAT` | **~0 extra** — no timestamp process is forked at all |
| `date +%s%N` ×2 | ~0.75 ms — **and broken on macOS**: BSD `date` has no `%N` |
| `perl -MTime::HiRes` ×2 | ~4.6 ms |
| `jq` for one scalar field | **~21 ms** — 55–75× a `grep`/`sed` equivalent, ~∞× pure-bash expansion |
| full candidate wrapper (builtin `time`, no-fork stdin, bash-native field extraction) | ~0.85 ms overhead |
| the same wrapper **gated off** by an env var | still ~0.3 ms, because it is still a fork in the call path |

This repo's own `hooks.json` files produce ~3 hook invocations per Bash/Edit tool call → roughly
300–900 per hour. At ~0.85 ms that is well under a second per hour; with `jq` it would be 6–19
seconds per hour *and* inflate a 0.7 ms guard script by 30×, which would trip the harness's own
"Slow PreToolUse hooks" warning **because of the instrument**.

Two traps confirmed live, both matching entries already in this repo's memory bank: the decimal
separator in a comma locale corrupts formatted durations unless `LC_ALL=C` is set, and the Bash tool
here runs **zsh**, so a wrapper must carry an explicit `#!/usr/bin/env bash` rather than assume bash.

**The benchmarked candidate is not protocol-safe**: it discards the wrapped hook's stdout and stderr
and loses its exit code inside a command substitution. Hook stdout is parsed as JSON, stderr is
surfaced, and exit code 2 means "block". The measured cost stands; the script must be rebuilt around
those three constraints.

### Prior art — surveyed, none adopted

`disler/claude-code-hooks-multi-agent-observability` (no licence file; server + SQLite + Vue UI;
feature-frozen since 2026-02), `TechNickAI/claude_telemetry` (MIT but replaces the `claude` command
— ruled out as invasive; no commits in ~10 months), `simple10/agents-observe` (Docker + React),
`NirDiamant/claude-watch` (licence inconsistent). **None covers instruction loading.**
`karanb192/claude-code-hooks` (MIT, active) ships an `instructions-audit` hook — the only project
found that touches this event at all, for security scanning rather than logging; whether it binds to
the event or scans at `SessionStart` was not verified.

No `docs/about/sources.md` entry is warranted for the survey itself — that file's bar is a concrete
artifact actually taken. Register at implementation time if a specific mechanism is borrowed.

---
*This file is managed by the xdd-meta skill.*
