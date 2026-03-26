---
phase: 2
title: memory-add Skill + Python Infrastructure
status: pending
spec: 001-memory-claude
---

# Phase 2 — memory-add Skill + Python Infrastructure

## Gate

Phase 1 complete (templates define target structure).

## Context

Ref: SDD §3.1 (memory-add), §5 (claude-reflect relationship).

`/memory-add` is the TCS learning-capture command. It is built on claude-reflect's Python infrastructure (hooks, queue format, session scanning) — extended with repo-level category routing to `docs/ai/memory/`. The Python scripts handle passive capture (hooks) and queue I/O; the SKILL.md handles only AI reasoning (classification, scope disambiguation).

## Tasks

### Python Scripts + Hooks

- [ ] Study `scripts/lib/reflect_utils.py` from claude-reflect — reuse queue I/O, path utilities, pattern detection
- [ ] Write `plugins/tcs-helper/scripts/lib/reflect_utils.py` — extended version with TCS additions:
  - Queue I/O: same as claude-reflect (JSON array format)
  - Queue item additions: `tcs_category` and `tcs_target` fields
  - Queue location: `~/.claude/projects/<encoded>/learnings-queue.json`
- [ ] Write `plugins/tcs-helper/scripts/capture_learning.py` — UserPromptSubmit hook (based on claude-reflect's version):
  - Reads `{"prompt": "..."}` from stdin
  - Regex detection for corrections, guardrails, explicit "remember:" prefix
  - Appends to queue on match; `sys.exit(0)` always
- [ ] Write `plugins/tcs-helper/scripts/session_start_reminder.py` — SessionStart hook:
  - Reads queue, outputs pending count
  - Checks for `docs/ai/memory/yolo-review.md` existence → adds YOLO reminder
  - Reads `CLAUDE_REFLECT_REMINDER=false` env var to suppress
- [ ] Write `plugins/tcs-helper/scripts/check_learnings.py` — PreCompact hook:
  - Backs up queue to `~/.claude/learnings-backups/pre-compact-<timestamp>.json`
- [ ] Write `plugins/tcs-helper/scripts/post_commit_reminder.py` — PostToolUse(Bash) hook:
  - Detects `git commit` (not `--amend`) in stdin command
  - Outputs reminder to run `/memory-add`
- [ ] Write `plugins/tcs-helper/scripts/merge_hooks.py` — standalone utility:
  - Merges tcs-helper's hook definitions into `~/.claude/settings.json`
  - Additive: existing hooks preserved, duplicates skipped
  - Used by setup skill (Phase 6)
- [ ] Write `plugins/tcs-helper/hooks/hooks.json`:
  - UserPromptSubmit, SessionStart, PreCompact, PostToolUse(Bash)
  - References scripts via `${CLAUDE_PLUGIN_ROOT}`

### Skill (SKILL.md — AI layer only)

- [ ] Create `plugins/tcs-helper/skills/memory-add/` directory
- [ ] Write `SKILL.md` with:
  - YAML frontmatter: name, description, user-invocable: true, argument-hint, allowed-tools
  - Auto-trigger keywords: reflect, remember, learned, note this, add to memory, route this
  - Interface: State with learnings[], routed[], skipped[], unclassified[], yolo: bool
  - Workflow: read queue → classify → determine scope → deduplicate (code) → write or stage
- [ ] Implement classification logic in SKILL.md (AI reasoning):
  - Category keywords for each of the 6 categories (see SDD §3.1)
  - Scope detection: personal/workflow correction → global; project fact → project; default → repo
  - Fallback: AskUserQuestion when unclassified
- [ ] Implement YOLO/bypass mode in SKILL.md:
  - Detect `YOLO=true` environment variable
  - When active: write to `docs/ai/memory/yolo-review.md` only (checkbox format, see SDD §3.1.4)
  - Implement `--review-yolo` sub-command
- [ ] Write `reference/routing-rules.md` — classification guide with examples for all 3 scopes
- [ ] Write `reference/category-formats.md` — entry format (date prefix, context note, what NOT to include)
- [ ] Write `examples/output-example.md` — example session routing (repo + global scope learnings)
- [ ] Register skill in `plugins/tcs-helper/.claude-plugin/plugin.json`

## Verification

- [ ] `capture_learning.py` writes to queue on correction prompt ("no, use X not Y")
- [ ] `session_start_reminder.py` outputs queue count on session start
- [ ] `session_start_reminder.py` outputs YOLO reminder when `yolo-review.md` exists
- [ ] Queue format matches SDD §3.1.2 (JSON array with required fields)
- [ ] Given a sample learning "always use `fd` not `find`", routes to `tools.md`
- [ ] Given a sample learning "UserRepository must return null for unknown emails", routes to `domain.md`
- [ ] Given a sample learning "decided to use hexagonal architecture", routes to `decisions.md`
- [ ] Given a personal correction "stop using semicolons in summaries", routes to global scope
- [ ] Unclassifiable learning triggers AskUserQuestion
- [ ] Appended entries have date + context note
- [ ] `memory.md` index last-updated date is updated after routing (repo-scope only)
- [ ] Running with the same learning twice does not create a duplicate entry
- [ ] With `YOLO=true`: no writes to category files; entries in `yolo-review.md` with checkboxes
- [ ] `--review-yolo`: accepted entries written to target files; yolo-review.md cleared
- [ ] `merge_hooks.py` adds hooks to settings.json without overwriting existing ones
