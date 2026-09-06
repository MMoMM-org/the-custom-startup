---
title: "Phase 2: Adapters and registration"
status: pending
version: "1.0"
phase: 2
---

# Phase 2: Adapters and registration

## Phase Context

**GATE**: Read all referenced files before starting this phase.

**Specification References**:
- `[ref: SDD/Interface Specifications — inbound]` — the three payload shapes and their fields
- `[ref: SDD/Application Data Models]` — which payload field becomes which record field
- `[ref: SDD/Runtime View — Primary Flow]` — the six-step path from harness to appended line
- `[ref: SDD/Architecture Decisions — ADR-2, ADR-3]`
- `docs/XDD/specs/018-observability-load-and-fire-log/README.md` § `InstructionsLoaded` — the five
  load reasons and both emission sites

**Key Decisions**:
- Adapters are thin by contract: read stdin once, extract two or three scalars, call the writer.
  Any logic beyond that belongs in the report, where it costs nothing (SDD/Solution Strategy).
- The skill adapter reads `tool_input`, which is a nested object. It extracts the one scalar it
  needs and **must not** be extended to walk that object — the extractor is a string operation, not
  a parser `[ref: SDD/Known Technical Issues]`.
- Registering a no-op hook "just in case" is forbidden: `hasInstructionsLoadedHook` is what makes
  the feature free while off, and a registered hook switches that cost back on
  `[ref: SDD/Implementation Gotchas]`.

**Dependencies**: Phase 1 (T1.1–T1.3). The adapters call the writer; without it they have nothing to
call. T1.4 does not block this phase.

---

## Tasks

Delivers the three capture paths and turns the feature on in this repo for the first time.

- [ ] **T2.1 Instruction-load adapter** `[activity: backend-api]` `[parallel: true]`

  1. Prime: read the `InstructionsLoaded` payload contract and the five load reasons
     `[ref: SDD/Interface Specifications]`
  2. Test: a `session_start` payload yields one record with `reason: session_start`, the file's
     scope, and a repo-relative path; a payload carrying `globs` yields `reason: path_glob_match`
     with `trigger` populated; a payload carrying a parent yields `reason: include` with `parent`
     populated; an absolute path outside the repo is reduced to its basename, never emitted whole
  3. Implement: `.claude/observability/log_instructions.sh`
  4. Validate: bats green; the adapter writes nothing to stdout (CON-4)
  5. Success: `[ref: SDD/SDD-AC-2, SDD-AC-3, SDD-AC-4]`; `[ref: PRD/F1]`

- [ ] **T2.2 Skill adapter** `[activity: backend-api]` `[parallel: true]`

  1. Prime: read the `PreToolUse` payload shape and the nested-`tool_input` caveat
     `[ref: SDD/Known Technical Issues]`
  2. Test: a `Skill` tool call yields one `kind: skill` record naming the skill; a payload whose
     `tool_input` lacks the expected key yields a record with an empty skill and **never** the
     serialised object; a non-`Skill` tool call yields no record at all
  3. Implement: `.claude/observability/log_skill.sh`
  4. Validate: bats green; nothing on stdout
  5. Success: `[ref: SDD/SDD-AC-16]`; `[ref: PRD/F5]`

- [ ] **T2.3 Agent adapter** `[activity: backend-api]` `[parallel: true]`

  1. Prime: read the `SubagentStart` payload shape `[ref: SDD/Interface Specifications]`
  2. Test: a dispatch yields one `kind: agent` record with the agent type and id; a nested dispatch
     records the parent agent; a payload missing `agent_type` still produces a well-formed line
  3. Implement: `.claude/observability/log_agent.sh`
  4. Validate: bats green; nothing on stdout
  5. Success: `[ref: SDD/SDD-AC-16]`; `[ref: PRD/F5]`

- [ ] **T2.4 Registration and self-check** `[activity: infrastructure]`

  1. Prime: read the hook registration shape in `plugins/tcs-helper/hooks/hooks.json` and the
     directory map `[ref: SDD/Directory Map]`
  2. Test: with the enable switch unset, a session creates no data directory and no file; with it
     set, a real session start produces at least one instruction record; `selfcheck` reports
     enabled state, detail state, record path and last-write time, and says "not recording" rather
     than reporting an empty result as a finding
  3. Implement: `.claude/settings.json` registration for the three events, plus
     `.claude/observability/selfcheck.sh`
  4. Validate: run a real session in this repo and inspect the produced records by hand — the first
     point at which the design meets the actual harness rather than a fixture
  5. Success: `[ref: SDD/SDD-AC-1]`; the `kind: state` record exists `[ref: SDD/Application Data Models]`;
     `[ref: PRD/F3]` (nothing recorded while off)

- [ ] **T2.5 Phase Validation** `[activity: validate]`

  - Run the full bats and pytest suites. Then verify the thing fixtures cannot: start a real session,
    confirm records appear for all three kinds, and confirm **no existing hook changed behaviour** —
    exit statuses, blocking behaviour and stdout of this repo's existing hooks are unchanged
    `[ref: SDD/Implementation Boundaries — Must Preserve]`.
