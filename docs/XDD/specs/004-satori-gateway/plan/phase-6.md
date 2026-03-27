---
title: "Phase 6: Hooks & Session Integration"
status: pending
version: "1.0"
phase: 6
---

# Phase 6: Hooks & Session Integration

## Phase Context

**GATE**: Read `docs/XDD/specs/004-satori-gateway/solution.md` sections "Hooks Architecture" and "Session Snapshot Format" before starting. Also read context-mode's hooks.json and skills/context-mode/SKILL.md.

**Specification References**:
- `[ref: SDD/Hooks Architecture]` — 5 hooks: PostToolUse, PreCompact, SessionStart, UserPromptSubmit, PreToolUse
- `[ref: SDD/Hooks Architecture/Event classification]` — full tool → category/type/priority mapping
- `[ref: SDD/Session Snapshot Format]` — XML, 2048 bytes, priority tiers
- `[ref: PRD/R1 Context Server]` — satori_context restore/flush acceptance criteria

**Key Decisions**:
- Hooks are bash/node scripts in `.claude-plugin/hooks/`; invoked by Claude Code's hook system
- `PostToolUse`: reads `CLAUDE_TOOL_NAME` + `CLAUDE_TOOL_OUTPUT` env vars; calls SessionDB + ContentDB
- `PreCompact`: calls `buildResumeSnapshot()` → `sessionDb.upsertResume()` → increments compact_count
- `SessionStart`: reads unconsumed resume → injects `<session_resume>` block into context
- Hook scripts connect to Satori via local socket or write directly to the DB (simpler for MVP)
- Non-blocking: hook failures log to stderr, never block Claude

**Dependencies**: Phase 5 (all tools and DB wired up).

---

## Tasks

Implements all 5 Claude Code hooks that feed session events into the DB, build snapshots at
compaction time, and restore context at session start.

- [ ] **T6.1 Hook manifest (.claude-plugin/hooks/hooks.json)** `[activity: build-platform]`

  1. Prime: Read context-mode `.claude-plugin/hooks/hooks.json` for structure. Claude Code hooks documentation: hook types, environment variable names, matcher patterns. `[ref: SDD/Hooks Architecture]`
  2. Test: `hooks.json` is valid JSON. Each of the 5 hook types listed. `PostToolUse` matcher covers all relevant tool names (Read, Write, Edit, MultiEdit, Bash, WebFetch, Agent, Task, TaskCreate, TaskUpdate). Scripts referenced in hooks.json exist. `[ref: SDD/Hooks Architecture]`
  3. Implement: Create `.claude-plugin/hooks/hooks.json` with 5 entries. Each entry: `event`, `matcher` (where applicable), `command` (node script path or bash script). Reference scripts in `hooks/scripts/`. `[ref: SDD/Hooks Architecture]`
  4. Validate: `cat .claude-plugin/hooks/hooks.json | node -e "process.stdin.resume(); let d=''; process.stdin.on('data',c=>d+=c); process.stdin.on('end',()=>JSON.parse(d))"` — valid JSON. All referenced script files exist. `[ref: SDD/Hooks Architecture]`
  5. Success: hooks.json valid; all 5 hook types declared; script paths resolve.

- [ ] **T6.2 PostToolUse hook (event capture)** `[activity: build-feature]`

  1. Prime: Read `[ref: SDD/Hooks Architecture/Event classification]` — all 14 mappings. How Claude Code passes tool name and output to hooks (env vars or stdin JSON). `[ref: SDD/Hooks Architecture]`
  2. Test: Hook script invoked with `CLAUDE_TOOL_NAME=Read` + mock file path input: inserts a `file_read` event into `session_events`. Hook invoked with `CLAUDE_TOOL_NAME=TaskCreate` + task data: inserts `task_create` event. Unknown tool name: inserts nothing, exits 0. Error during DB write: logs to stderr, exits 0 (non-blocking). `[ref: SDD/Hooks Architecture/Event classification]`
  3. Implement: Create `hooks/scripts/post-tool-use.ts` (compiled to `dist/hooks/`). Read hook payload from stdin or env. Call `extractEvent(toolName, input, output)`. If non-null, open SessionDB (`.satori/db.sqlite`), call `sessionDb.insertEvent()`, close. Also: if tool produces content output (Read, Bash, WebFetch), call `contentDb.insertCapture()` with raw output. `[ref: SDD/Hooks Architecture]`
  4. Validate: Integration test: run hook script in subprocess with mocked env, verify DB contains correct event row. Error test: DB path not writable → script exits 0 (non-blocking). `[ref: SDD/Hooks Architecture/Event classification]`
  5. Success: PostToolUse correctly classifies and stores all 14 event categories; never blocks Claude.

- [ ] **T6.3 PreCompact hook (snapshot builder)** `[activity: build-feature]`

  1. Prime: Read `[ref: SDD/Session Snapshot Format]` — full XML spec. `sessionDb.upsertResume()`, `sessionDb.incrementCompactCount()`. `[ref: SDD/Session Snapshot Format]`
  2. Test: PreCompact hook invoked: reads all session events from DB → calls `buildResumeSnapshot()` → stores result in `session_resume` table with `consumed = 0`. `compact_count` incremented. XML output ≤ 2048 bytes. With 0 events: minimal XML (`<session_resume ...></session_resume>`). `[ref: SDD/Session Snapshot Format]`
  3. Implement: Create `hooks/scripts/pre-compact.ts`. Get session ID from env. Read events via `sessionDb.getEvents()`. Call `buildResumeSnapshot(events, {compactCount})`. Call `sessionDb.upsertResume()`. Call `sessionDb.incrementCompactCount()`. `[ref: SDD/Session Snapshot Format]`
  4. Validate: Integration test: insert 20 events across categories, run hook, verify `session_resume` table has row with `consumed = 0` and valid XML. `compact_count` in `session_meta` = 1. `[ref: SDD/Session Snapshot Format]`
  5. Success: PreCompact produces valid XML snapshot ≤ 2048 bytes; always exits 0.

- [ ] **T6.4 SessionStart hook (context injection)** `[activity: build-feature]`

  1. Prime: How Claude Code's `SessionStart` hook can inject text into the context. `sessionDb.getResume()`, `sessionDb.markResumeConsumed()`. `[ref: SDD/Hooks Architecture]`
  2. Test: SessionStart hook invoked: reads `session_resume` where `consumed = 0`, outputs XML as injection text, calls `markResumeConsumed()`. No unconsumed resume: outputs nothing. Already consumed: outputs nothing. `[ref: SDD/Hooks Architecture]`
  3. Implement: Create `hooks/scripts/session-start.ts`. Get session ID. `sessionDb.getResume()` → if row exists and `consumed = 0`: print XML to stdout (Claude Code injects stdout from SessionStart hooks), call `markResumeConsumed()`. `[ref: SDD/Hooks Architecture]`
  4. Validate: Integration test: write resume to DB, run hook, capture stdout — contains `<session_resume>` XML. Run again: stdout empty. `[ref: SDD/Hooks Architecture]`
  5. Success: SessionStart outputs resume XML exactly once; subsequent calls output nothing.

- [ ] **T6.5 UserPromptSubmit and PreToolUse hooks** `[activity: build-feature]`

  1. Prime: Read `[ref: SDD/Hooks Architecture]` — UserPromptSubmit (lightweight hint) and PreToolUse (intercept Bash/Read/Grep for classification). What PreToolUse can do (block, modify, pass through). `[ref: SDD/Hooks Architecture]`
  2. Test: UserPromptSubmit: if no unconsumed resume in DB, outputs a brief hint line; if resume was already injected this session, outputs nothing. PreToolUse with Bash tool: records intent (`cwd_change` if `cd` detected in command; `git_op` if `git` in command). PreToolUse exits 0 (never blocks). `[ref: SDD/Hooks Architecture]`
  3. Implement: Create `hooks/scripts/user-prompt-submit.ts` — lightweight; checks for unconsumed resume; if absent, prints one-line hint. Create `hooks/scripts/pre-tool-use.ts` — reads tool name + arguments from hook payload; classifies if Bash (parse for `cd`, `git`, common patterns) or Read/Grep (file path → file_read intent); calls `sessionDb.insertEvent()` for matching categories; always exits 0. `[ref: SDD/Hooks Architecture]`
  4. Validate: UserPromptSubmit: with resume → no hint; without → hint appears. PreToolUse with `git commit` Bash payload → `git_op` event in DB. PreToolUse with unknown Bash → no event inserted, exits 0. `[ref: SDD/Hooks Architecture]`
  5. Success: Both hooks non-blocking; PreToolUse correctly detects git/cd patterns; UserPromptSubmit hint is ≤1 line.

- [ ] **T6.6 Phase 6 Validation** `[activity: validate]`

  - `npm test` — all Phase 6 tests pass.
  - `npm run typecheck` — 0 errors.
  - End-to-end session test (scripted):
    1. Insert 10 file events via PostToolUse hook
    2. Run PreCompact hook → `session_resume` row created
    3. Run SessionStart hook → XML printed to stdout; row marked consumed
    4. Run SessionStart hook again → no output
  - `satori_context(restore)` after step 3 → returns snapshot XML.
  - All hook scripts exit 0 even when given malformed input.
