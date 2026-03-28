---
title: "Memory + MCP Integration (M5)"
spec: 005-memory-mcp
document: requirements
status: draft
version: "1.0"
last-updated: 2026-03-27
---

# Product Requirements Document
## Memory + MCP Integration (M5)

## Validation Checklist

### CRITICAL GATES (Must Pass)

- [x] All required sections are complete
- [x] No [NEEDS CLARIFICATION] markers remain
- [x] Problem statement is specific and measurable
- [x] Every feature has testable acceptance criteria (Gherkin format)
- [x] No contradictions between sections

### QUALITY CHECKS (Should Pass)

- [x] Problem is validated by evidence (not assumptions)
- [x] Context → Problem → Solution flow makes sense
- [x] Every persona has at least one user journey
- [x] All MoSCoW categories addressed (Must/Should/Could/Won't)
- [x] No technical implementation details included
- [x] A new team member could understand this PRD

---

## Product Overview

### Vision

Give Claude Code persistent, searchable memory and safe multi-language execution across
sessions — automatically, without changing a single existing skill or workflow.

### Problem Statement

Claude Code loses all context when a session ends or compacts. Developers using it for
complex, multi-day projects face three compounding problems:

1. **Context loss on compaction** — tool outputs, decisions, and captured state are
   discarded mid-session when the context window fills. The developer must re-explain
   what was built and why.

2. **No cross-session recall** — there is no way to ask "what did we decide about auth
   last week?" or "what errors did we see when running the migration?" without manually
   reading through memory files or git log.

3. **Execution without context reduction** — running code (tests, scripts, data pipelines)
   inside Claude Code dumps full output into the context window. A 1 MB test run consumes
   context budget that could be used for reasoning.

These problems compound: more context is lost → more re-explaining → less context left for
actual work. The cost per session grows as projects grow.

### Value Proposition

M5 connects Satori (the M4 MCP gateway) to the TCS workflow so that:

- **Context is captured automatically** — tool outputs, session state, and decisions are
  stored by Satori hooks without the developer doing anything different.
- **Past context is searchable** — one command retrieves relevant decisions, errors, or
  tool outputs from any prior session, ranked by relevance.
- **Execution is context-efficient** — running code via `satori_exec` returns only the
  relevant portion of output; large outputs are indexed and queryable rather than dumped
  into context.
- **Existing skills work unchanged** — the architecture is transparent; no skill
  modifications are required.

---

## User Personas

### Primary Persona: Solo Developer (Power Claude Code User)

- **Role:** Individual developer using Claude Code as a primary development environment
  across multiple projects and sessions.
- **Technical expertise:** High — comfortable with MCP servers, TOML config, CLI tools.
- **Goals:**
  - Continue work across sessions without losing context or re-explaining state.
  - Search past decisions and captured outputs without leaving the workflow.
  - Run scripts and tests without blowing the context budget.
- **Pain Points:**
  - Session compaction silently discards tool outputs and intermediate state.
  - Re-reading memory files manually to restore context after a break.
  - Long test/script outputs consuming context that should be used for reasoning.

### Secondary Personas

None. M5 is a single-persona feature — it targets the developer using TCS + Satori. There
are no end-user personas (this is developer tooling, not a consumer product).

---

## User Journey Maps

### Primary Journey: Cross-Session Context Continuity

1. **Setup (once):** Developer installs TCS + Satori. During `install.sh`, opts in to
   context-mode. Satori is configured; hooks are active.

2. **Working session:** Developer works normally — runs tools, implements features, makes
   decisions. Satori captures tool outputs and session state automatically in the background.

3. **Session ends / compacts:** Satori flushes a session guide (≤2KB) before compaction.
   Context window clears. Developer goes offline.

4. **Next session:** Developer resumes. Session start reminder indicates context-mode is
   active. Developer uses `/context-search` to retrieve what was decided or built in the
   prior session. Relevant context is returned in seconds, without reading files manually.

5. **Ongoing:** As projects grow, the knowledge base accumulates indexed content.
   Cross-session search quality improves. Context budget per session stays roughly constant
   because execution output is indexed rather than inlined.

### Secondary Journey: Context-Efficient Execution

1. Developer asks Claude to run a test suite or data pipeline.
2. Claude calls `satori_exec("bash", "run", {language: "shell", code: "...", intent: "find failing tests"})`.
3. Satori runs the code in a sandboxed environment. If output exceeds 5KB, it is indexed
   into the knowledge base and searched by intent — only the relevant section is returned.
4. Developer sees a focused result (e.g., the 3 failing test names) rather than 800 lines
   of test runner output consuming their context budget.

---

## Feature Requirements

### Must Have

#### F1 — Install opt-in for context-mode

- **User Story:** As a developer, I want to opt in to context-mode during TCS installation
  so that Satori is configured correctly without manual TOML editing.
- **Acceptance Criteria:**
  - [ ] Given the developer runs `install.sh`, When they reach the optional features prompt, Then context-mode is listed as an opt-in option with a clear description
  - [ ] Given the developer opts in, When install completes, Then `satori.toml` contains a `[context]` block with `db_path`, `session_guide_max_bytes`, and `retain_days`
  - [ ] Given the developer opts out, When install completes, Then no `[context]` block is written and no Satori tools are used by hooks
  - [ ] Given the developer opts in, When a new session starts, Then the session start reminder includes a note that context-mode is active

#### F2 — Satori detection for skills and hooks

- **User Story:** As a skill, I want to detect whether Satori is running so that I can
  use Satori tools when available and fall back to file-based memory when not.
- **Acceptance Criteria:**
  - [ ] Given Satori is running, When a skill checks for it, Then `satori_context` appears in the available tool list
  - [ ] Given Satori is not running, When a skill checks for it, Then the tool is absent and file-based fallback is used
  - [ ] Given a hook script runs, When it checks for Satori, Then it checks for the `.satori/` directory in the repo root
  - [ ] Given Satori is absent, When a hook would call a Satori tool, Then it silently skips the Satori call with no error

#### F3 — satori_exec builtin server ("bash")

- **User Story:** As a developer, I want to run code in multiple languages via Claude
  without dumping full output into the context window.
- **Acceptance Criteria:**
  - [ ] Given Satori is running, When I call `satori_exec("bash", "run", {language, code})`, Then the code executes in a sandboxed environment
  - [ ] Given the output is under 5KB, When execution completes, Then full output is returned
  - [ ] Given the output exceeds 5KB and `intent` is provided, When execution completes, Then output is indexed and only the intent-relevant section is returned
  - [ ] Given code in any of the 11 supported languages, When I call run, Then the correct runtime is used (js/ts/python/shell/ruby/go/rust/php/perl/r/elixir)
  - [ ] Given a shell command batch, When I call `satori_exec("bash", "batch", {commands, queries})`, Then all commands run sequentially, outputs are indexed, and search results are returned in a single response
  - [ ] Given I disable the "bash" server via `satori_manage(disable, {name: "bash"})`, When Satori starts, Then the builtin server is not registered
  - [ ] Given execution output goes through Satori, When any output is returned, Then the Satori router pipeline (security scan, capture, summarize) has been applied

#### F4 — satori_kb knowledge base tool

- **User Story:** As a developer, I want to index documents and URLs and search them
  semantically so that I can retrieve relevant content without it entering the context window.
- **Acceptance Criteria:**
  - [ ] Given markdown content, When I call `satori_kb("index", {content, title})`, Then the content is chunked by headings and stored in `kb.sqlite`
  - [ ] Given a URL, When I call `satori_kb("fetch_and_index", {url})`, Then the page is fetched, converted to markdown, chunked, and indexed — the raw HTML never enters context
  - [ ] Given a search query, When I call `satori_kb("search", {query})`, Then results are ranked by relevance using BM25 + trigram RRF with proximity reranking
  - [ ] Given a typo in the query ("kuberntes"), When search runs, Then Levenshtein correction fires before the FTS query
  - [ ] Given a multi-term query, When results are returned, Then snippets are centred around where the query terms appear (smart snippets, not first-N-chars)
  - [ ] Given 9 or more search calls in a session, When the 9th call is made, Then it is blocked and a redirect to `satori_exec("bash", "batch", ...)` is suggested
  - [ ] Given `contentType: "code"`, When search runs, Then only code-typed chunks are returned
  - [ ] Given `kb.sqlite` does not exist, When the first index call is made, Then the database and FTS5 schema are created automatically

#### F5 — Memory routing (really-short-lived → Satori DB)

- **User Story:** As a developer, I want session state (task progress, recent errors,
  active files) to be captured automatically so I don't lose it on compaction.
- **Acceptance Criteria:**
  - [ ] Given Satori is running, When a PostToolUse hook fires, Then really-short-lived state (task progress, recent errors) is written to the Satori context DB
  - [ ] Given a PreCompact hook fires, When Satori is running, Then a session guide (≤2KB) is flushed to the context DB before the window clears
  - [ ] Given context.md (short-lived), When Satori is running, Then context.md is NOT moved to Satori — it remains a file (human-readable, git-tracked)
  - [ ] Given Satori is absent, When hooks fire, Then all state writes fall back to file-based memory with no error

#### F6 — Uninstall clean removal

- **User Story:** As a developer, I want uninstall to offer removing the context and
  knowledge base databases without doing so automatically.
- **Acceptance Criteria:**
  - [ ] Given the developer runs uninstall, When context-mode was previously enabled, Then they are prompted to optionally remove `.satori/db.sqlite`
  - [ ] Given the developer runs uninstall, When `kb.sqlite` exists, Then they are prompted separately to optionally remove `.satori/kb.sqlite`
  - [ ] Given the developer declines both prompts, When uninstall completes, Then both databases are preserved
  - [ ] Given uninstall runs, When the developer did not opt in to context-mode, Then no DB prompts are shown

#### F7 — Kairn backend prep field

- **User Story:** As a developer, I want to be able to set `context.backend = "kairn"` in
  `satori.toml` so that Kairn can be swapped in post-MVP without breaking the current config schema.
- **Acceptance Criteria:**
  - [ ] Given `context.backend` is absent or `"satori"`, When Satori starts, Then the SQLite context DB is used normally
  - [ ] Given `context.backend = "kairn"`, When Satori starts, Then a warning is logged: "context.backend=kairn not yet supported, falling back to satori"
  - [ ] Given any value of `context.backend`, When skills or hooks call `satori_context`, Then behaviour is unchanged from their perspective

---

### Should Have

- **context-search skill** (ships from miyo-satori, not TCS) — allows developers to query the Satori context DB with natural language from within the Claude Code session.
- **Session start context restore** — on session start, `satori_context restore` is called and the session guide is injected, replacing the need to manually load `context.md`.

### Could Have

- `satori_kb("stats")` — context savings report and call counts (post-MVP).
- `satori_kb("doctor")` — diagnose runtimes, FTS5, and hook configuration (post-MVP).
- Ambient context injection — hooks inject relevant prior-session context into `/implement`, `/debug`, `/review` calls automatically (M5.1).

### Won't Have (This Phase)

- Kairn client implementation — `context.backend = "kairn"` is parsed but not functional.
- `ctx_execute_file` path-variable injection — deferred to M5.1.
- `ctx_upgrade` equivalent — post-MVP.
- Any changes to existing TCS skills — architecture is transparent; skills are untouched.
- Consumer-facing UI — this is developer CLI tooling only.

---

## Detailed Feature Specifications

### Feature: satori_exec builtin server (F3)

**Description:** A zero-config execution server built into Satori that runs code in 11
languages. It auto-registers at startup and routes through the full Satori pipeline —
security scan, capture, and summarize — so all output is treated consistently with any
other MCP tool call. Large outputs are indexed into the knowledge base rather than returned
inline, keeping the context budget under control.

**User Flow:**
1. Developer (or skill) calls `satori_exec("bash", "run", {language: "python", code: "...", intent: "find slow queries"})`
2. Satori routes to the builtin "bash" server
3. Code executes in a sandboxed environment with denied env vars stripped
4. Output is measured: under 5KB → returned directly; over 5KB with intent → indexed to `kb.sqlite`, relevant section returned + vocabulary for follow-up queries
5. Result returns through Satori pipeline (security scan on output, capture to context DB)

**Business Rules:**
- The "bash" server is registered automatically; no user config required
- Users may disable it: `satori_manage(disable, {name: "bash"})` — respected on next startup
- All 11 languages must be available subject to runtime detection; missing runtimes return a clear error naming the missing tool
- Hard output byte cap: 100MB; process is killed if exceeded
- Background mode: process continues after response; partial output returned

**Edge Cases:**
- Runtime not installed (e.g., `ruby` absent) → Error: "Runtime 'ruby' not found. Install ruby to use this language."
- Code hangs past timeout (default 30s) → Process group killed; partial output + timeout message returned
- Intent provided but output under 5KB → Full output returned (intent ignored, not an error)
- `batch` with 0 commands → Error: "commands array must not be empty"
- Dangerous env vars present in environment → Stripped by `#buildSafeEnv` before execution; no error surfaced to caller

### Feature: satori_kb knowledge base (F4)

**Description:** A dedicated knowledge base tool backed by a separate SQLite FTS5 database.
Indexes markdown content (from direct input or fetched URLs) and searches it with a
multi-strategy ranking pipeline. Designed to keep reference content out of the context
window entirely — index once, query selectively.

**User Flow:**
1. Developer calls `satori_kb("fetch_and_index", {url: "https://docs.example.com/api"})`
2. Satori fetches the URL, converts HTML to markdown, chunks by headings
3. Chunks are stored in `kb.sqlite` with FTS5 index
4. Later: `satori_kb("search", {query: "rate limiting"})` returns ranked snippets from the indexed content
5. Raw page content never appeared in the context window at any point

**Business Rules:**
- `kb.sqlite` is separate from the session context DB (`db.sqlite`) — independently purgeable
- Chunking: split at markdown headings; code blocks are kept intact (never split mid-block)
- Heading weight: titles and headings are indexed at 5× BM25 weight
- RRF merge: Porter-stemming FTS + trigram FTS results merged; documents ranking well in both surface higher
- Progressive throttling: 9+ search calls in a session are blocked and redirected to batch
- `contentType` filter: when provided, only chunks of that type (`code` or `prose`) are returned

**Edge Cases:**
- URL returns non-200 status → Error: "Failed to fetch URL: HTTP 404"
- URL content is not HTML (PDF, binary) → Error: "Unsupported content type: application/pdf"
- Query matches nothing → Empty results array returned; no error
- `kb.sqlite` corrupted → Log error, attempt recreation; if recreation fails, surface error to caller
- Index call with empty content → Error: "content must not be empty"

---

## Success Metrics

### Key Performance Indicators

- **Adoption:** Developer enables context-mode on first `install.sh` run (opt-in rate target: 80% of active TCS users who have Satori installed).
- **Context budget retention:** With context-mode enabled, average context consumed per session on execution-heavy workflows decreases by ≥40% compared to baseline (inline output).
- **Cross-session recall accuracy:** `/context-search` returns a relevant result in the top-3 for ≥85% of queries against a known indexed corpus.
- **Zero skill regressions:** All existing TCS skill tests pass unchanged after M5 ships (architecture transparency gate).

### Tracking Requirements

| Event | Properties | Purpose |
|-------|------------|---------|
| `context_mode_enabled` | install timestamp, satori version | Track opt-in rate |
| `satori_exec_run` | language, output_size_bytes, intent_present, truncated | Measure context savings from execution |
| `satori_kb_search` | query length, result count, throttle_level | Monitor search quality and throttle behaviour |
| `satori_kb_index` | content_size_bytes, chunk_count, source (direct/url) | Track knowledge base growth |
| `context_restore_called` | session_guide_size_bytes, restore_latency_ms | Measure session continuity effectiveness |

---

## Constraints and Assumptions

### Constraints

- M2 (file-based memory) and M4 (Satori gateway) must be complete before M5 ships — both are ✅.
- Satori is an optional dependency — M5 features must degrade cleanly when Satori is absent; no hard dependency on Satori in TCS skills.
- The "bash" builtin server and `satori_kb` ship inside the miyo-satori repo — TCS only adds the install prompt, hook wiring, and `context.backend` field.
- `context-search` skill is owned by miyo-satori, not TCS — its implementation is out of TCS scope.

### Assumptions

- The developer has Node.js available (required by Satori).
- Language runtimes for satori_exec (python3, ruby, etc.) are the developer's responsibility to install — Satori surfaces clear errors when a runtime is absent.
- The miyo-satori submodule is kept up to date by the developer; TCS does not auto-update it.
- Kairn (the post-MVP backend) will expose a compatible API so that swapping `context.backend` requires no TCS code changes.

---

## Risks and Mitigations

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| `kb.sqlite` grows unbounded | Medium — disk usage, slow search | Medium | `retain_days` config; manual purge prompt in uninstall; post-MVP vacuum on startup |
| Satori not running when hooks fire | Low — graceful degradation | High (common during setup) | All hook paths check for Satori presence; silent skip when absent |
| Builtin "bash" server executes dangerous code | High — security | Low (Satori security scan applied) | `#buildSafeEnv` strips dangerous env vars; process group kill on timeout; security scan on output |
| Progressive throttling surprises developer | Low — UX friction | Medium | Clear redirect message naming `satori_exec batch` as the next step |
| Kairn API incompatibility post-MVP | Medium — rework | Low (field is prep only) | `context.backend` field is parsed but Kairn code is not shipped; no functional coupling in M5 |
| context-search skill out of sync with Satori API | Medium — broken search | Low | Skill is owned by miyo-satori; Satori owns both sides of that interface |

---

## Open Questions

- [ ] Session guide format: should the ≤2KB PreCompact snapshot follow the same schema as the M2 session guide, or is it Satori-defined? (Decision owner: miyo-satori)
- [ ] `satori_kb` URL fetching: should redirects be followed automatically? Max redirect hops? (Decision at SDD)
- [ ] Progressive throttling counter: per-session only, or does it persist across compactions within the same process? (Decision at SDD)

---

## Supporting Research

### Competitive Analysis

**context-mode (mksglu/context-mode):** The primary reference implementation. Provides
`ctx_execute`, `ctx_index`, `ctx_search`, `ctx_fetch_and_index`, `ctx_batch_execute`,
`ctx_stats`, `ctx_doctor`, `ctx_upgrade`. M5 ports the core execution and knowledge base
features into Satori as first-class MCP tools, adding the Satori router pipeline (security
scan, capture, summarize) on top.

Key differentiator: context-mode is standalone; Satori integrates it with a gateway
architecture, session context DB, and the TCS memory system.

**Kairn (primeline-ai/kairn):** Post-MVP backend for long-term memory with auto-decay.
Not a direct competitor — it replaces Satori's SQLite DB rather than replacing Satori
itself. The `context.backend` field in M5 reserves the extension point.

### User Research

Single user (Marcus) — direct requirement authoring from lived experience with Claude Code
session compaction and context budget exhaustion on multi-day projects.

Key insight: the problem is not lack of memory files; it's the friction of reading them
back manually and the context cost of execution output. M5 targets both pain points with
automatic capture (hooks) and intent-driven output reduction (satori_exec).

### Market Data

Not applicable — this is internal developer tooling for a single-user framework.
