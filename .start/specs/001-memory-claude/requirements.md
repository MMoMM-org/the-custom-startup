---
spec: 001-memory-claude
document: requirements
status: complete
---

# PRD — Memory + CLAUDE.md System (M2)

## Problem

Claude Code sessions are stateless. Knowledge discovered in one session (patterns, decisions, tool quirks, domain rules) must be re-discovered or re-entered in every new session. Existing approaches either overload a single CLAUDE.md file (growing to 189+ lines, loading everything always) or scatter facts across ad-hoc notes with no consistent structure.

The result: context bloat, repeated corrections, and knowledge that lives only in session history.

## Goal

A file-based memory system that:
1. Persists knowledge across sessions at the right granularity
2. Loads only what's relevant (progressive disclosure, not front-loading)
3. Routes new learnings to the correct location automatically
4. Shrinks over time as domain patterns are promoted to reusable skills
5. Works entirely without MCP or external dependencies (MCP integration is M5)

## Users

- **Marcus** — primary user, uses TCS across multiple repos and the MiYo project ecosystem
- **Any TCS user** — the system should work for any repo after running `tcs-helper:setup`

## User Stories

### Memory Structure
- As a developer, I want my repo's learned knowledge organized by category (general conventions, tool quirks, domain rules, decisions, troubleshooting) so I can find and update it without reading everything.
- As a developer, I want the memory bank visible in `docs/ai/` (not hidden in `.claude/`) so it's part of the project documentation, not a hidden implementation detail.
- As a developer, I want each category file to stay focused and lean so that loading one file doesn't pull in unrelated noise.

### CLAUDE.md Design
- As a developer, I want the root CLAUDE.md to stay under 100 lines so it loads fast and stays readable.
- As a developer, I want per-directory CLAUDE.md files (src/, test/, docs/) to load automatically when I work in those directories, so context is relevant without explicit loading.
- As a developer, I want routing rules in CLAUDE.md (not in MEMORY.md) so the index budget isn't wasted on instructions.

### Learning Capture
- As a developer, I want corrections and learnings from a session to be routed to the correct category file automatically (via `memory-route` after `/reflect`), so I don't have to manually decide where each learning goes.
- As a developer, I want the memory index (memory.md) to stay under 200 lines so it loads within context budget on every session start.

### Maintenance
- As a developer, I want to periodically clean up stale entries, archive resolved troubleshooting, and remove duplicates (via `memory-cleanup`) without losing important historical facts.
- As a developer, I want repeating domain patterns in `domain.md` to be detectable and promotable to `tcs-patterns` skills (via `memory-promote`), so the memory file shrinks as knowledge matures.

### Onboarding
- As a developer starting a new repo, I want `tcs-helper:setup` to generate the full `docs/ai/memory/` structure and lean CLAUDE.md files for me, so setup takes minutes not hours.

## Scope

**In scope (M2):**
- `docs/ai/memory/` directory structure with 6 category files
- Root CLAUDE.md template + per-directory CLAUDE.md templates (src/, test/, docs/, docs/ai/)
- `tcs-helper:memory-route` skill
- `tcs-helper:memory-sync` skill
- `tcs-helper:memory-cleanup` skill
- `tcs-helper:memory-promote` skill
- `tcs-helper:setup` skill (project onboarding)
- Integration with `claude-reflect` (memory-route extends /reflect)
- Scope × Lifetime × Category routing table

**Out of scope (M5):**
- MCP context server integration
- "Really short lived" session data (stays in context window or auto-memory for now)
- Semantic memory queries (Kairn)

**Out of scope (M1):**
- Core workflow skill changes (tcs-start → tcs-workflow rename, new workflow skills)

## Success Criteria

- [ ] Root CLAUDE.md for a new repo is < 100 lines after setup
- [ ] `docs/ai/memory/memory.md` index stays ≤ 200 lines
- [ ] Running `/reflect` followed by `/memory-route` correctly routes learnings to category files with no manual intervention
- [ ] Running `/memory-route` twice on the same learnings does not create duplicate entries (idempotent)
- [ ] `/memory-route` can be invoked standalone (without prior `/reflect`) by pasting learning text directly
- [ ] `memory-sync` detects and reports: missing @import in CLAUDE.md, orphaned memory files, routing rules in wrong file, and index approaching 200-line budget
- [ ] `memory-promote` surfaces a domain pattern as a tcs-patterns candidate and replaces the domain.md entry with a pointer after approval
- [ ] `memory-promote` behaves gracefully when session history is absent (analyses domain.md alone, confidence = Low)
- [ ] `tcs-helper:setup` generates complete `docs/ai/` structure in a new repo in one invocation
- [ ] `tcs-helper:setup` running on a repo with an existing CLAUDE.md adds the memory section without overwriting existing content
- [ ] All memory operations function without any MCP server installed
- [ ] All memory operations function without `claude-reflect` installed (degraded mode: manual input only)

## Non-Goals

- This is not a replacement for `claude-reflect`. It extends it; installing claude-reflect enables automatic capture but is not required.
- This is not a database or semantic search system. Files are human-readable markdown.
- This is not a session state manager. Session/really-short-lived data is handled in M5.
