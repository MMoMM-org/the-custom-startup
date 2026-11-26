# Research — 024 observability denials report

Two research passes on 2026-11-26, plus a docs check. Sources are named per point.

## Claude Code hook events (docs: hooks.md, permissions.md, sandboxing.md, sessions.md)

| Case | Event | Notes |
|---|---|---|
| PreToolUse hook returns `deny` | none after PreToolUse | PostToolUseFailure "doesn't fire for tool calls rejected before execution"; no later event names the denying hook |
| Settings deny rule / user rejects prompt | none | PermissionDenied does not fire for these; PermissionRequest fires only before the prompt |
| Auto-mode classifier block | `PermissionDenied` | `tool_name`, `tool_input`, `tool_use_id`, `reason`; `retry: true` only lets the model retry |
| Sandbox violation | none | visible only in command output (EPERM text, denied host named in the result) |
| Tool ran and failed | `PostToolUseFailure` | `error`, `is_interrupt`, `duration_ms` |

Transcripts: `~/.claude/projects/<project>/<session-id>.jsonl`; "The entry format is internal to Claude Code and changes between versions" (sessions.md).

## Constraints from specs 018, 019, 021

- Privacy rules bind the recorder: two opt-in switches, off by default (018 solution.md:399-404); hooks registered only in untracked `settings.local.json` (021 CON-8, 019 ADR-1); reduced mode drops arguments, file contents, `transcript_path`, absolute cwd, prompt and response text (018 solution.md:815-822); CON-13: no flag value, argument, path, message or prompt text in a record (021 solution.md:115-117).
- 021 Won't Have: "Retroactive attribution of historical named records through a join against session transcripts" (requirements.md:358-359); 021 research.md:21 "offline transcript join (#166)" a non-goal. Report-side precedent, needs an explicit narrowing (logged in README).
- 021 Won't Have: the guard's verdict in the git record — hooks run in parallel; a denied command is still recorded as an attempt (solution.md:595-596).
- Per-source sections, no pooled totals (019 ADR-7, solution.md:495-502). Honesty layer: UNKNOWN / NOT RECORDING / STALE never shown as 0 (report.py:1605-1635); empty git section says "not proof none happened" (report.py:1845-1855).
- `encode_project_path` exists in `plugins/tcs-helper/scripts/lib/reflect_utils.py:13-17`; reusing it across plugins falls under 021 CON-12 ("mirror the contract, not the code").
- tcs-git-helpers `audit/overrides.jsonl` (frozen fields `ts, repo, branch, hook, env_var, master, command, pattern, tool_input_truncated`) holds override consumptions, protect-git-internals denies, ask-guard asks; its `command` value must not be rendered (CON-13). report.py reads neither it nor transcripts today.
- `docs/ai/memory/declined.md`: nothing on denials, transcripts or PermissionDenied.

## Denials in local transcripts (6189 files, 5.17 GB, Claude Code 2.1.71–2.1.332)

Layout: 635 session files plus 5554 subagent files at `<projdir>/<sessionId>/subagents/agent-*.jsonl`.

Traps: `type: "api-request-blob"` lines duplicate tool results — count `type == "user"` only. Text matching without `is_error: true` is mostly noise (e.g. 666 "Operation not permitted" hits in successful output).

| Family | Count | Versions | Reliability |
|---|---|---|---|
| `^PreToolUse:(\w+) hook error: ` + message | 198 | 2.1.286–332 | high; tool in prefix |
| Hook deny without prefix (`tcs-git-helpers DENIED` 271, `Refusing to (Write\|Edit)` 77, `Dangerous flag detected` 55, `rm -rf on critical…` 40) | 443 | 2.1.114–309 | medium; by known opening only |
| `The user doesn't want to proceed with this tool use` | 206 | 2.1.71–332 | high; 133 AskUserQuestion and 27 ExitPlanMode are not action denials |
| Auto-mode classifier `…Reason: [Category]…` | 50 | 2.1.138+ | high; category parseable |
| Older classifier `Permission for this action has been denied. Reason:` | 13 | 2.1.114–132 | high |
| `Permission to use <Tool> has been denied…` | 44 | 2.1.75–318 | mostly subagents; not proven to be settings deny rules |
| Built-in safety check | 14 | | high |
| Worktree isolation guard | 149 | 2.1.290–319 | mostly subagents |
| Sandbox `Operation not permitted` | 312 | | low; same as other EPERM |
| Network `CONNECT tunnel failed, response 403` | 50 | | medium |
| `Read-only file system` / `could not lock config file` | 0 / 1 | | |
| MCP-specific | 0 | | |

- Fields on denial lines: `type`, `timestamp`, `sessionId`, `cwd`, `version`, `gitBranch`, `isSidechain`, `uuid`, `toolUseResult`; `agentId` in subagents. `tool_use_id` links to the assistant `tool_use` in the same file (tool name). `toolUseResult` is not a reliable mirror; read `message.content`.
- Not identifiable as distinct shapes: settings deny-rule denials; ask-then-user-rejected.
- Hook and rule: `tcs-git-helpers DENIED: N rule(s) matched` + `  - [RULE]` lines parse reliably (top: BRANCH_FROM_UNFINISHED 148, DESTRUCTIVE_CHECKOUT 94, FORCE_BRANCH_DELETE 74, REMOTE_BRANCH_DELETE 52). Only 2.1.114–132 recorded the hook (`hook_blocking_error` attachment with `hookName`); newer versions do not name it, so the hook comes from a table of known openings. No protect-git-internals message found.
- Drift: `PreToolUse:` prefix from 2.1.286; 2.1.286–309 mix prefixed and bare forms (cause unknown); classifier wording changed between 2.1.132 and 2.1.138.
- Repo mapping: project dir = cwd with `/` and `.` replaced by `-`; 22 of 58 dirs hold several cwds; worktree sessions live under the parent repo with cwd `…/.claude/worktrees/<name>`. Key by per-line `cwd`, stripped back to the repo root; case varies.
- Cost: one full single-threaded Python pass 63 s; an `rg -l` pre-filter on the deny strings leaves 427 files.
