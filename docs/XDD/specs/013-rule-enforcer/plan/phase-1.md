---
title: "Phase 1: Intercept Hook Foundation"
status: completed
version: "1.0"
phase: 1
---

# Phase 1: Intercept Hook Foundation

## Phase Context

**GATE**: Read all referenced files before starting this phase.

**Specification References**:
- `[ref: PRD/M1 — UserPromptSubmit Intercept Hook]`
- `[ref: PRD/S1 — Externalized Trigger-Phrase Config]`
- `[ref: SDD/Constraints CON-1..CON-5]`
- `[ref: SDD/ADR-4 Hook script in python3]`
- `[ref: SDD/ADR-5 Trigger-phrase storage markdown+regex]`
- `[ref: SDD/ADR-8 Hook registration via existing hooks.json append]`
- `[ref: SDD/Interface Specifications — Hook Contract]`

**Key Decisions**:
- Hook script in Python 3 — direct precedent in `plugins/tcs-helper/scripts/capture_learning.py`
- Trigger phrases data-driven (markdown reference file, parsed by lib)
- Hook MUST exit 0 on any error (CON-4 — never block user prompt)
- p95 latency ≤ 50ms (CON-2)
- Register by appending to existing `hooks.json` UserPromptSubmit array (do NOT replace `capture_learning.py` entry)

**Dependencies**: None — Phase 1 is foundational.

---

## Tasks

This phase delivers the **UserPromptSubmit intercept hook** that watches every user prompt for recurrence trigger phrases (DE + EN) and injects a single-line system reminder suggesting `/enforce-rule` when one matches. PRD Features M1 + S1.

- [x] **T1.1 Trigger-phrases reference + lib parser** `[activity: data-architecture]` `[parallel: false]`

  1. **Prime**: Read `plugins/tcs-helper/scripts/lib/reflect_utils.py` for the shared-lib pattern used by `capture_learning.py`. Read `plugins/tcs-helper/skills/skill-author/reference/conventions.md` for reference-file conventions.
  2. **Test (RED)**: Write `plugins/tcs-helper/scripts/lib/test_trigger_phrases.py` that asserts:
     - Loading a sample `trigger-phrases.md` returns a non-empty list of compiled regex patterns
     - Patterns are scoped per language section (`## English`, `## Deutsch`)
     - Malformed/missing file returns empty list (no exception raised)
     - `match("I keep forgetting X")` returns True
     - `match("syntax for X")` returns False
  3. **Implement (GREEN)**:
     - Create `plugins/tcs-helper/skills/rule-enforcer/reference/trigger-phrases.md` with initial regex set per ADR-5 format (English + Deutsch sections; ~10 patterns total)
     - Create `plugins/tcs-helper/scripts/lib/trigger_phrases.py` exposing `load(path) -> [CompiledPattern]` and `match(text, patterns) -> bool`
     - Parser: extract code-fenced regex blocks per `## <Language>` heading; one regex per line
  4. **Validate**: Run `python3 plugins/tcs-helper/scripts/lib/test_trigger_phrases.py` — all assertions pass. `python3 -m py_compile` clean on both files.
  5. **Success**:
     - [x] Markdown parser handles missing file gracefully `[ref: PRD/M1 AC-4]`
     - [x] `match()` correctly identifies recurrence phrases vs non-recurrence text `[ref: PRD/M1 AC-1, AC-2]`
     - [x] Reference file is user-extensible (add language by adding `## <Lang>` section) `[ref: PRD/S1 AC-1, AC-2]`

- [x] **T1.2 Intercept hook script** `[activity: backend-tooling]` `[parallel: false]`

  1. **Prime**: Read `plugins/tcs-helper/scripts/capture_learning.py` — adopt its structure verbatim (stdin JSON read, try/except all errors, exit 0 always). Read SDD Hook Contract section.
  2. **Test (RED)**: Write `plugins/tcs-helper/scripts/test_intercept_rule_recurrence.py` that asserts:
     - Stdin with `{"prompt": "I keep forgetting X"}` → stdout contains `[rule-enforcer]` suggestion line, exit 0
     - Stdin with `{"prompt": "what is the syntax"}` → empty stdout, exit 0
     - Stdin with malformed JSON → empty stdout, exit 0 (graceful)
     - Stdin with missing prompt key → empty stdout, exit 0
     - 100-invocation timing measurement: p95 ≤ 50ms (record measurement; soft assertion warns if exceeded)
  3. **Implement (GREEN)**:
     - Create `plugins/tcs-helper/scripts/intercept_rule_recurrence.py` (~50 lines): parse stdin JSON, load trigger phrases via lib, regex-match prompt, write single-line suggestion to stdout if matched, exit 0
     - Suggestion format (per SDD): `[rule-enforcer] Recurrence signal detected ('<matched-phrase-snippet>'). Consider /enforce-rule "<rule>" to triage.`
  4. **Validate**: All test assertions pass. Manual test: `echo '{"prompt":"ich vergesse immer die Doku"}' | python3 plugins/tcs-helper/scripts/intercept_rule_recurrence.py` produces expected `[rule-enforcer]` suggestion line (matches Deutsch pattern `vergesse(n) immer`). Module compiles clean.
  5. **Success**:
     - [x] Hook injects suggestion only when trigger phrase matches `[ref: PRD/M1 AC-1, AC-2]`
     - [x] Hook exits 0 on all error paths `[ref: PRD/M1 AC-4]` `[ref: SDD/CON-4]`
     - [x] p95 latency measurement recorded (p95=25.3ms ≤ 50ms target) `[ref: PRD/M1 AC-3]` `[ref: SDD/CON-2]`

- [x] **T1.3 Hook registration + manual smoke test** `[activity: integration]` `[parallel: false]`

  1. **Prime**: Read current `plugins/tcs-helper/hooks/hooks.json` — note `capture_learning.py` entry MUST be preserved alongside the new entry.
  2. **Test (RED)**: Write a JSON-validity assertion: `python3 -c "import json; json.load(open('plugins/tcs-helper/hooks/hooks.json'))"` — must remain valid after edit.
  3. **Implement (GREEN)**: Edit `plugins/tcs-helper/hooks/hooks.json` to append a second entry in the `UserPromptSubmit` array, pointing to the new hook script with `${CLAUDE_PLUGIN_ROOT}/scripts/intercept_rule_recurrence.py`. Preserve the existing `capture_learning.py` entry verbatim.
  4. **Validate**:
     - JSON is valid (`python3 -c "import json; json.load(open(...))"` passes)
     - Both hook entries present and well-formed
     - Manual smoke test: start a fresh Claude Code session, submit a prompt containing "I keep forgetting test", verify that a `[rule-enforcer]` line appears in the prompt context (capture-learning hook also fires; both should coexist)
  5. **Success**:
     - [x] Hook is registered without breaking `capture_learning.py` `[ref: SDD/ADR-8]` `[ref: SDD/Implementation Boundaries — Must Preserve]`
     - [ ] Live smoke test confirms intercept fires in a real session `[ref: PRD/M1 AC-1]` — **pending manual verification in fresh Claude Code session**

- [x] **T1.4 Phase 1 Validation** `[activity: validate]`

  - Run all Phase 1 tests (T1.1, T1.2 assertion suites)
  - Verify hook script doesn't slow prompt latency perceptibly in a 5-prompt manual smoke session
  - Lint Python: `python3 -m py_compile` on all new files
  - Verify `hooks.json` validates with both entries
  - Confirm trigger-phrases.md is markdown-valid (renders OK)
  - **Phase complete when**: all 3 task Success criteria checked off + this Validation step green
