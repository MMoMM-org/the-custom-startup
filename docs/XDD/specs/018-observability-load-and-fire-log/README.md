# Specification: 018-observability-load-and-fire-log

## Status

| Field | Value |
|-------|-------|
| **Created** | 2026-09-06 |
| **Current Phase** | Ready |
| **Decomposition tier** | Incremental |
| **Last Updated** | 2026-09-06 |

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
