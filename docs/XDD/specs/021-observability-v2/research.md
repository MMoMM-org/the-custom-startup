# Research — 021 observability-v2

Four read-only research passes, 2026-10-11. Citations are as the researchers gave them; the PRD and SDD verify anything they build on.

## Measured payloads (Claude Code 2.1.296)

See README § Context. Probe: `claude -p --settings` with a hook that dumps every payload, plus one interactive named dispatch in a live session.

## Requirements

**Purpose of the record** — 018 personas: maintainer deciding structure from evidence ("which shipped skills are ever used"; pain: "no way to tell a skill that never fires from one that fires invisibly"), plugin consumer (an update must never start recording their Bash command lines), session diagnostician. 019 roles: Operator, Subject, Analyst ("in which repos did each shipped skill/agent fire"; keep/drop/rework). #153: one log answers which instructions loaded, which skills fired, which agents were dispatched, which hooks ran.

**#165** — cannot tell *unused* from *only ever typed* for `user-invocable` skills. 0/8 typed commands recorded here; Hashi 23 typed, 0 records (true figure 1/84). The issue body claims typed `/tcs-workflow:implement` did record on 2026-09-09; the later comment and `scripts/observability/README.md` say typed never records — resolved by the 2026-10-11 probe: typed fires `UserPromptExpansion`, never `PreToolUse:Skill`. The issue comment proposed `UserPromptSubmit` and flagged unresolved commands as false positives; `UserPromptExpansion` only fires on expansion.

**#166** — named dispatch (`impl-t41`) cannot be credited. Per-source figure printed 9/84, correct 11/84 (12/84 with #165). SubagentStart has no type/parent field. Options named in the issue: stop naming, or retroactive transcript join (out of #162 scope).

**#172** — which agent ran a `reset` (spec-020 incident; bypass #171). Stated requirements: `PreToolUse` on `Bash`, not `PostToolUse` (override token visible before it takes effect; denied commands never reach PostToolUse); git-mutating commands; record command, `CLAUDE_ALLOW_*` presence and first-token position, the guard's decision, session, agent identifier; state the attribution limit rather than wait.

**Constraints a new kind must respect** — opt-in (two switches: `CLAUDE_OBSERVABILITY_ENABLED`, `CLAUDE_OBSERVABILITY_DETAIL`; never on by default or by update); registration only in `.claude/settings.local.json`, per named repo; no prompt/response text, no file contents, no hook command strings; Bash in reduced mode keeps argv[0] only; 256-byte field cap with `truncated`; nothing leaves the machine; fail-open (never changes a hook's exit/stdout); per-repo location outside the tree; size rotation 1 MB `.1–.3`, removal never deletes records; ~3–5 ms per matching event even when off; bash 3.2, no `jq`, no new dependency; empty/stale record reported as such; per-repo reports plus one union figure; wording at `scripts/observability/README.md:211-218`.

**Non-goals to not expand into** — Bash recording is an 018 *Won't Have* (T3.6) restated in 019: **this spec reverses it and must supersede it explicitly**. Also: prompt/response text; dashboard/server/db/network; pooled records; permanent timing layer; memory-bank restructuring (#147); offline transcript join (#166); shipping to plugin consumers; fixing the guard bypass (#171).

**Open questions raised** — UserPromptExpansion vs UserPromptSubmit; argument text in typed records; separate kind vs `route` field, double counting; Agent record replaces or sits beside SubagentStart, and the link; retroactive resolution; which git commands count, full line vs verb+flags; observability vs tcs-git-helpers audit, and where a "guard decision" could come from when hooks run in parallel; Bash-matcher cost; report wording; new collection period; re-running setup after h1→h2.

## Technical

**Blockers**
1. `registration.py` `REGISTRATION` is a dict keyed by event (:101-105) — one (matcher, script) per event. `add_registration` (:294-319) collapses all our entries under an event into one; three PreToolUse entries would keep only the last. Must become per (event, matcher).
2. Drift (`detect.sh:72-81, :467-488`) is judged by the global bundle marker only. Once one repo moves the bundle to h2, every repo reports OURS-CURRENT although its settings lack the new hooks.
3. The reduced-mode deny list (`logwrite.sh:557`: `command full_command hook_command content file_content transcript_path cwd prompt prompt_text response response_text`) drops `prompt`/`command` by name; `command_args`, `description` need an explicit `detail:` prefix.

**Adapters / writer** — adapters run as their own process, source `logwrite.sh` relative to their own path (never `CLAUDE_PLUGIN_ROOT`), drain stdin and exit 0 if sourcing fails; read stdin fork-free (`IFS= read -r -d ''`); `log_instructions.sh` gates on `CLAUDE_OBSERVABILITY_ENABLED` before reading and passes `_observability_toplevel=`. `logwrite.sh`: generic schema, frozen prefix `ts, kind, session, repo`, caller pairs appended in order, no kind allowlist (kind enum only in 018 solution.md:422); 256-byte cap; rotation at 1,024,000 bytes; no locking (one `printf >>`); always returns 0, silent. `_observability_field` is a flat first-match scan that stops at the first `"` — a command containing `\"` is cut short. `_observability_program_name` gives argv[0].

**Registration / bundle** — ownership by path namespace `$HOME/.claude/observability/`; writes backup → temp → `os.replace` under a lock; legacy migration via `LEGACY_SCRIPTS`. `detect.sh` keeps paired copies `OUR_EVENTS`/`LEGACY_SCRIPTS`; a foreign hook under any of our events is CONFLICT at event level. `bundle_install.sh` copies a fixed script list (:113) — new adapters must be added. Marker `^h[0-9]+$`, currently `h1`. CI gate `check-hook-bundle-version.sh` gates `scripts/observability/*.sh`.

**Report** (`scripts/observability/report.py`) — `fired_names` (:1006-1032) maps `skill`→`rec["skill"]`, `agent`→`rec["agent_type"]`: the plug-in point for a typed-skill kind (`command_name`→skill) and a dispatch kind (`subagent_type`→agent). `firing_coverage` (:1074-1140) joins on qualified `plugin:name` or unique bare name — **check whether `command_name` carries the `plugin:` prefix**. A git-op kind needs its own section in `build_load_report` (:1561-1712).

**Tests pinning current sets** — `test_observability_registration.py` (`EXPECTED_EVENTS`, `len(...) == 3` in several places, matcher fixtures); `test_observability_cross_file_agreement.py` (`OUR_EVENTS == set(REGISTRATION)`, `set(LEGACY_SCRIPTS) == set(REGISTRATION)`); `h1` hardcoded in `observability-bundle-version.bats`, `-bundle-install.bats`, `-drift-check.bats`, `-set-u-safety.bats`; event-list strings in `observability-setup.bats`; `observability-registration-matrix.bats`, `observability-detect.bats`; adapter suites `observability-skill.bats` / `-agent.bats` as templates; report tests incl. the T30 golden fixture.

**Reusing the tcs-git-helpers guard** — no generic "git-mutating" predicate exists (only destructive `PATTERN_*`); `_clausify` is heavy; `_check_and_consume_override` has side effects and must not be called. Cross-plugin `source` is forbidden by a documented rule ("mirror the contract, not the code"); any git classification is copied into the bundle with a parity test.

**018/019 constraints** — CON-1 bash 3.2; CON-4/5 silent, fail-open; CON-6 no new dependency; CON-7 ≤1 ms per hook; CON-9 record nothing rather than wrong things on payload drift; CON-11 must be re-derived before adding a fourth event; frozen field order; ADR-5 no `jq`/`date` in hook path (one `date` accepted). 019 CON-5 3–5 ms floor; ADR-3 bundle versioning; ADR-5 namespace ownership; ADR-7/8 per-repo report.

## Security / data protection

**Today** — 018 Won't Have: no prompt/response text, no Bash adapter. Rules: redaction is ours (stdin arrives unredacted); reduced mode keeps program name only; records outside the tree; free text capped and flagged. Two switches, off by default. Deny list exact-match only (renamed fields slip through); **`args` was recommended for the deny list and never added**.

**Location** — `~/.claude/plugins/data/observability-<repo>/observability/events.jsonl`; **mode 0644, dirs 0755, no `umask`** — world-readable, harmless today, not once commands are recorded. Keyed by repo basename: worktrees get their own dir, same-name repos share one. Never in VCS. Residual: `sync-docker` copies `~/.claude` content; whether `plugins/data` is excluded is unverified.

**Per-field recommendation**

| Field | Risk | Reduced mode |
|---|---|---|
| `command_name`, `command_source` | low | keep |
| `command_args` | high | `args_present` / `args_bytes` only; text via `detail:` |
| expansion `prompt` | high (skill body + args) | never |
| Agent `subagent_type` | low | keep |
| Agent `name` | low–medium | keep, capped |
| Agent `description` | medium | `detail:` only |
| Agent `prompt` | high | never |
| Bash command text | high (`GH_TOKEN=…`, `Authorization:` headers, `user:pass@` URLs, `--with-token`, `set-url`) | program + git subcommand + flag names, never values |
| `CLAUDE_ALLOW_*` tokens | low | variable names only |
| `agent_id`, `agent_type` | low | keep |

No credential-scrubbing helper exists; if detail mode ever stores Bash text, one is needed.

**Overlap with tcs-git-helpers** — `overrides.jsonl` records that an override was consumed on a branch, with no session/agent/command; complementary. Record override names plus attribution; leave the authoritative override record to tcs-git-helpers. (`overrides.jsonl` stores the full repo path, which 018 avoids.)

**Integrity** — both logs are user-writable; a subagent with Bash can edit, truncate, redirect (`CLAUDE_OBSERVABILITY_DATA`), disable (`CLAUDE_OBSERVABILITY_ENABLED`), or flood rotation. A record is evidence something happened; absence is not proof it did not.

## Performance

**Budgets** — 018 CON-7 (≤1 ms) never met on macOS; writer ~9 ms, ~13.3 ms end to end per event. 019 CON-5: 3–5 ms per matching event even when off. 011 git-helpers: PreToolUse:Bash non-push ≤80 ms p99. Perf tests use `_perf_budget_ms` × `TCS_PERF_SLACK` (4 in CI).

**Already on PreToolUse:Bash** — `block-bad-git-ops.sh` measured ~60 ms per non-git call (`$(cat)` + 2× `jq` + 5 sourced libs before any check).

**One `logwrite.sh` record** — 4–5 execs best case, ~7 worst (`git rev-parse` up to 3× without `_observability_toplevel=`, `mkdir -p`, `stat`, `date`, `basename`).

**Measured locally** — `/bin/bash -c :` ~2 ms; `/usr/bin/env bash` ~4 ms; warm `jq` ~4 ms; bash + `$(cat)` + case ~5–6 ms; bash + builtin `read -d ''` + case ~3 ms.

**Recommendation** — `#!/bin/bash`; builtin read; first logic is the enabled check plus a pure `case` string test for git, exiting before any fork or `source`; precise matching after. Budgets: non-git Bash ≤5 ms p50 added (macOS); git record ≤15 ms (pass `_observability_toplevel=`); rare events keep the 018 adapter cost. Perf fixtures warmed once in `setup()`. Optional follow-up: the same fast path in `block-bad-git-ops.sh` (~60 ms → ~3 ms on non-git calls) would more than offset the new hook.
