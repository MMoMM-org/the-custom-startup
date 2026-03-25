---
phase: 2
title: memory-route Skill
status: pending
spec: 001-memory-claude
---

# Phase 2 — memory-route Skill

## Gate

Phase 1 complete (templates define target structure).

## Context

Ref: SDD §3.1 (memory-route), §5 (claude-reflect integration).

`memory-route` is the TCS repo-layer extension of `/reflect`. It takes learnings (from reflect output or manual input) and routes each one to the correct `docs/ai/memory/` category file. It follows the same extension pattern as `/miyo-reflect`.

## Tasks

- [ ] Verify `learnings-queue.json` schema against claude-reflect source before implementing queue reader (see SDD §3.1 for expected schema; confirm field names match actual implementation)
- [ ] Create `plugins/tcs-helper/skills/memory-route/` directory
- [ ] Write `SKILL.md` with:
  - YAML frontmatter: name, description, user-invocable: true, argument-hint, allowed-tools
  - Persona: routes learnings to correct category file
  - Interface: State with learnings[], routed[], unclassified[]
  - Constraints (Always/Never)
  - Workflow: classify → append → update index
- [ ] Implement classification logic in SKILL.md:
  - Keyword/pattern rules for each category (see SDD §3.1)
  - Fallback: AskUserQuestion when unclassified
- [ ] Write `reference/routing-rules.md` — detailed classification guide with examples
- [ ] Write `reference/category-formats.md` — entry format for each category file
  - Date prefix, context note, what NOT to include
- [ ] Write `examples/output-example.md` — example routing session
- [ ] Implement deduplication check before appending:
  - Check if semantically identical entry already exists in target file
  - Skip duplicates silently; include in report as "skipped (duplicate)"
- [ ] Implement YOLO mode flag:
  - When `$CLAUDE_YOLO_MODE` is set or `--yolo` argument present:
    - Simultaneous write: route learning to category file as normal AND append to `docs/ai/memory/yolo-review.md`
    - `yolo-review.md` is an audit log — writes have already landed in category files
    - At end of YOLO session, user runs `/memory-route --review-yolo` to inspect the log and selectively remove unwanted entries from category files
- [ ] Implement standalone mode (no prior /reflect run):
  - Accept learning text directly as argument
  - Accept multiple learnings as newline-separated argument
- [ ] Register skill in `plugins/tcs-helper/.claude-plugin/plugin.json`

## Verification

- [ ] SKILL.md loads without errors
- [ ] Given a sample learning "always use `fd` not `find`", routes to `tools.md`
- [ ] Given a sample learning "UserRepository must return null for unknown emails", routes to `domain.md`
- [ ] Given a sample learning "decided to use hexagonal architecture", routes to `decisions.md`
- [ ] Unclassifiable learning triggers AskUserQuestion
- [ ] Appended entries have date + context note
- [ ] `memory.md` index last-updated date is updated after routing
- [ ] Running with the same learning twice does not create a duplicate entry
- [ ] Running with `--yolo` flag writes to `yolo-review.md` in addition to target file
- [ ] Running without prior `/reflect` (direct argument) routes correctly
