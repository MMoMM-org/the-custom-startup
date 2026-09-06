# Specification: 018-observability-load-and-fire-log

## Status

| Field | Value |
|-------|-------|
| **Created** | 2026-09-06 |
| **Current Phase** | PLAN |
| **Decomposition tier** | Incremental |
| **Last Updated** | 2026-09-06 |

## Documents

| Document | Status | Notes |
|----------|--------|-------|
| requirements.md | completed | 8 features across all MoSCoW tiers, 32 acceptance criteria, 4 review decisions folded in |
| solution.md | completed | 7 components, 8 ADRs (4 user-confirmed), 20 acceptance criteria, full PRD traceability |
| plan/ | in_progress | |

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

## Context

Issue: [#153](https://github.com/MMoMM-org/the-custom-startup/issues/153) — observability: log what
actually loads and fires — instructions, skills, agents, hooks. Downstream consumer:
[#147](https://github.com/MMoMM-org/the-custom-startup/issues/147), which cannot decide memory-bank
routing without a denominator.

## Research findings (Claude Code 2.1.252, verified against the shipped binary)

### What the harness gives us natively

| Source | Native coverage | Mechanism |
|---|---|---|
| **Hooks** | yes, incl. duration — but per *(event:matcher)* **batch**, not per command | OTel **log events** `hook_execution_start` / `hook_execution_complete`, the latter carrying `total_duration_ms`, `num_success`, `num_blocking`, `num_non_blocking_error`, `num_cancelled`. Reachable via the documented `CLAUDE_CODE_ENABLE_TELEMETRY=1` + `OTEL_LOGS_EXPORTER=console`. `hook_definitions` (the configured command strings) additionally needs `OTEL_LOG_TOOL_DETAILS=1` |
| **Skills** | yes | `claude_code.tool.execution` span carries `skill_name`; reachable via the documented `CLAUDE_CODE_ENHANCED_TELEMETRY_BETA=1` + `OTEL_TRACES_EXPORTER` |
| **Agents** | **no** | `claude_code.subagent.spawn` exists but is dead code — its only guard is `vj()`, hard-coded `false`. Agent identity must come from our own `SubagentStart` hook payload |
| **Instructions** | **no** | The `InstructionsLoaded` payload never enters telemetry; only "a batch ran" does. Our own hook is required — which is the original purpose of #153 |

`hook_name` is `` `${event}:${matcher}` ``, never the individual command. `num_hooks` is the count
sharing that matcher. **Consequence:** if two hook commands share one matcher, no native signal can
say which was slow.

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
