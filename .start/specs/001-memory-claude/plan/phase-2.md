---
phase: 2
title: memory Skill (capture + routing)
status: pending
spec: 001-memory-claude
---

# Phase 2 — memory Skill

## Gate

Phase 1 complete (templates define target structure).

## Context

Ref: SDD §3.1 (memory), §5 (claude-reflect migration).

`/memory` is the TCS learning-capture command. It replaces `/reflect` (claude-reflect) for TCS repos, handling all three scopes (global/project/repo) and routing each learning to the correct category file.

## Tasks

- [ ] Verify `learnings-queue.json` schema against claude-reflect source before implementing queue reader (see SDD §3.1 for expected schema; confirm field names match actual implementation)
- [ ] Verify exact env var for `--dangerously-skip-permissions` detection before implementing YOLO mode
- [ ] Create `plugins/tcs-helper/skills/memory/` directory
- [ ] Write `SKILL.md` with:
  - YAML frontmatter: name, description, user-invocable: true, argument-hint, allowed-tools
  - Auto-trigger keywords: reflect, remember, learned, note this, add to memory, route this
  - Persona: classifies and routes learnings to correct scope + category
  - Interface: State with learnings[], routed[], skipped[], unclassified[], yolo: bool
  - Constraints (Always/Never)
  - Workflow: classify → determine scope → deduplicate → write (or stage if YOLO)
- [ ] Implement classification + scope logic in SKILL.md:
  - Keyword/pattern rules for each category (see SDD §3.1)
  - Scope detection: personal/global vs project vs repo
  - Fallback: AskUserQuestion when unclassified
- [ ] Write `reference/routing-rules.md` — detailed classification guide with examples for all 3 scopes
- [ ] Write `reference/category-formats.md` — entry format for each category file
  - Date prefix, context note, what NOT to include
- [ ] Write `examples/output-example.md` — example routing session (repo-scope and global-scope learnings)
- [ ] Implement deduplication check before appending:
  - Check if semantically identical entry already exists in target file
  - Skip duplicates silently; include in report as "skipped (duplicate)"
  - Cross-scope duplicates NOT checked here (handled by memory-cleanup)
- [ ] Implement YOLO/bypass mode:
  - Detect `--dangerously-skip-permissions` via env var (TBD — verify first)
  - Do NOT write to normal memory files in this mode
  - Write staged entries to `docs/ai/memory/yolo-review.md` in checkbox format
  - Implement `--review-yolo` sub-command: present entries, write accepted ones to target files
- [ ] Implement SessionStart hook that checks for `yolo-review.md` and reminds user
- [ ] Register skill in `plugins/tcs-helper/.claude-plugin/plugin.json`

## Verification

- [ ] SKILL.md loads without errors
- [ ] Given a sample learning "always use `fd` not `find`", routes to `tools.md`
- [ ] Given a sample learning "UserRepository must return null for unknown emails", routes to `domain.md`
- [ ] Given a sample learning "decided to use hexagonal architecture", routes to `decisions.md`
- [ ] Given a personal correction "stop using semicolons in summaries", routes to global scope
- [ ] Unclassifiable learning triggers AskUserQuestion
- [ ] Appended entries have date + context note
- [ ] `memory.md` index last-updated date is updated after routing (repo-scope only)
- [ ] Running with the same learning twice does not create a duplicate entry
- [ ] In YOLO/bypass mode: no writes to category files; entries appear in `yolo-review.md` with checkboxes
- [ ] `--review-yolo`: accepted entries written to target files, reviewed entries removed from yolo-review.md
- [ ] SessionStart hook warns when `yolo-review.md` exists
- [ ] Running with direct argument routes correctly (no queue file needed)
