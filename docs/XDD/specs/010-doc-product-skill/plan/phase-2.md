---
title: "Phase 2: Review Mode and Reader-Test Engine"
status: pending
version: "1.0"
phase: 2
---

# Phase 2: Review Mode and Reader-Test Engine

## Phase Context

**GATE**: Read all referenced files before starting this phase.

**Specification References**:
- `[ref: SDD/Interface Specifications — Persona File Schema; lines: 343-410]` — persona format
- `[ref: SDD/Interface Specifications — claude -p Invocation Contract; lines: 412-460]` — subprocess contract
- `[ref: SDD/Interface Specifications — Gap Report Schema; lines: 462-485]` — output schema
- `[ref: SDD/Implementation Examples — Reader-Test Bash Driver; lines: 503-580]` — reference implementation
- `[ref: SDD/Runtime View — Primary Flow review mode; lines: 605-650]` — orchestration
- `[ref: SDD/Acceptance Criteria — Review mode; lines: 898-907]` — EARS criteria
- `[ref: PRD/Feature 4 — review mode; lines: 165-185]` — PRD acceptance criteria
- `[ref: PRD/Detailed Feature Specifications — review mode; lines: 197-235]` — flows + edge cases
- `[ref: SDD/ADR-2; lines: 773-777]` — claude -p subprocess rationale
- `[ref: SDD/ADR-3; lines: 779-783]` — stateless review
- `[ref: SDD/ADR-4; lines: 785-789]` — persona override semantics
- `[ref: SDD/ADR-6; lines: 798-802]` — gap report inline only

**Key Decisions**:
- ADR-2 + ADR-3: subprocess via `claude -p`, output is conversation-only (no on-disk reports).
- ADR-4: project `.claude/doc-personas.md` replaces defaults; `extends: defaults` is opt-in.
- ADR-6: gap report is rendered Markdown into the parent conversation, never `Write`-ed to disk.
- Generic personas (per 2026-05-06 inline-question resolution): defaults avoid project-type/OS hardcoding.
- Multi-page corpus per question: each question has its own `pages: [...]` list, concatenated with delimiters.
- Strict 100% on required questions for the doc set to PASS.

**Dependencies**:
- Phase 1 (skeleton + mode router exists; `modes/review.md` stub will be replaced).

---

## Tasks

This phase delivers a working `review` mode that produces a gap report when invoked against a `docs/` directory. Verifiable outcome: `/doc-product review` against a known-good doc returns PASS; against a known-bad doc returns FAIL with specific gaps named.

- [ ] **T2.1 Default Personas Template** `[activity: build-feature]` `[parallel: true]`

  1. **Prime**: Read SDD §Persona File Schema in detail. Re-read PRD personas section to remember the user-facing intent.
  2. **Test**: After authoring `templates/personas-default.md`, verify by inspection: 4 personas present (first-time-installer, config-explorer, troubleshooter, migrator); each has id, required, description, questions list; each question has id, required, text, pages. Test the schema is parseable: write a tiny Bash helper that emits each persona's required-question count via `grep`/`awk` and verify the numbers match what's expected.
  3. **Implement**: Author `templates/personas-default.md` with the YAML structure from SDD §Persona File Schema (post-2026-05-06 generic-language version). Include the 4 personas with their generic phrasing.
  4. **Validate**: Inspection check; parser sanity check.
  5. **Success**:
     - [ ] File matches SDD persona schema (post-update) `[ref: SDD/Persona File Schema; lines: 343-410]`
     - [ ] Default personas use generic language (no "plugin", no "macOS" hardcoded) `[ref: SDD/Acceptance Criteria — Review mode last; lines: 906-907]`

- [ ] **T2.2 Persona Override Resolution Helper** `[activity: build-feature]`

  1. **Prime**: Read SDD §Persona File Schema "Override mechanism" + ADR-4 confirmed text. `[ref: SDD/ADR-4; lines: 785-789]`
  2. **Test**: Pressure scenarios (Bash unit tests against fixture persona files):
     - No `.claude/doc-personas.md` → use defaults verbatim.
     - `.claude/doc-personas.md` exists, no `extends:` directive → entirely replaces defaults.
     - `.claude/doc-personas.md` exists with `extends: defaults` → starts from defaults, project entries augment / override by `id`.
     - `.claude/doc-personas.md` malformed (missing required field, persona with zero questions) → script exits non-zero with descriptive error per SDD §Error Handling.
  3. **Implement**: Author a helper Bash function (in `scripts/reader-test.sh` or a separate `scripts/lib-personas.sh`) that resolves the active persona set. Bash 3.2 compatible — no associative arrays. Use `git rev-parse --show-toplevel` to anchor `.claude/doc-personas.md` resolution.
  4. **Validate**: All pressure scenarios pass.
  5. **Success**:
     - [ ] Override resolution matches ADR-4 contract `[ref: SDD/ADR-4; lines: 785-789]`
     - [ ] Malformed persona file produces actionable error before any subprocess call `[ref: SDD/Error Handling — Persona file malformed; lines: 663]`
     - [ ] Bash 3.2 compatible — `bash --version` shows 3.2 on the test environment, script runs without error `[ref: SDD/CON-9; line: 77]`

- [ ] **T2.3 reader-test.sh — claude -p Invocation Driver** `[activity: build-feature]`

  1. **Prime**: Read SDD §claude -p Invocation Contract + §Reader-Test Bash Driver implementation example. `[ref: SDD/claude -p Invocation Contract; lines: 412-460]` `[ref: SDD/Reader-Test Bash Driver; lines: 503-580]`
  2. **Test**: Pressure scenarios for the script:
     - Happy path: a known-good doc with a clear answer → exit 0, JSON output with `found: yes`.
     - Known-bad doc (missing the answer): exit 0, JSON output with `found: no` plus populated `unclear:`.
     - `claude` CLI not on PATH: exit non-zero before any invocation; clear error per SDD §Error Handling.
     - `claude` rate-limited / network down: error caught, JSON emitted with `error: timeout_or_invocation_failure`, exit 0 (caller distinguishes infra from gap).
     - Malformed JSON from `claude -p`: same fallback, `error: unparseable_response`.
     - Multi-page corpus question: pages concatenated with BEGIN/END delimiters; missing page surfaces as `(page not found in repo)`, not silently dropped.
  3. **Implement**: Author `scripts/reader-test.sh` per the SDD example. Bash 3.2 compatible. Uses `git rev-parse --show-toplevel` for repo-anchored page resolution. Wraps `claude -p` with `timeout`. Validates JSON shape via `jq`.
  4. **Validate**: All pressure scenarios pass on the test environment. Script passes `shellcheck`.
  5. **Success**:
     - [ ] Single-tuple invocation produces SDD-compliant JSON envelope `[ref: SDD/claude -p Invocation Contract; lines: 412-460]`
     - [ ] Multi-page corpus concatenated with delimiters `[ref: SDD/Acceptance Criteria — review mode; lines: 904-905]`
     - [ ] Infrastructure errors distinguished from genuine gaps `[ref: SDD/Error Handling rows; lines: 660-665]`

- [ ] **T2.4 Gap Report Template and Renderer** `[activity: template-design]` `[parallel: true]`

  1. **Prime**: Read SDD §Gap Report Schema. `[ref: SDD/Gap Report Schema; lines: 462-485]`
  2. **Test**: Given a fixture aggregate-results JSON (mix of pass / fail / infra-error / informational), the renderer must produce Markdown matching the schema: header table by persona, "Failing required findings" section listing only required-fail items, "Optional findings" only when present, "Infrastructure errors" only when present. Verify presentation handles N=0 cases (no fails → no section, no infra errors → no section).
  3. **Implement**: Author `templates/gap-report-template.md` with the schema from SDD. Renderer logic lives in `modes/review.md` (Markdown templating instructions for Claude — no Bash file-write). Include the deterministic ordering: required-fail first, optional after, infrastructure last.
  4. **Validate**: Fixture-driven inspection — each fixture produces the expected Markdown.
  5. **Success**:
     - [ ] Template matches SDD §Gap Report Schema `[ref: SDD/Gap Report Schema; lines: 462-485]`
     - [ ] No file write — output renders inline only `[ref: SDD/ADR-6; lines: 798-802]`
     - [ ] Empty sections collapsed (zero-fail run still produces a meaningful report)

- [ ] **T2.5 modes/review.md — Orchestrator Workflow** `[activity: build-feature]`

  1. **Prime**: Read SDD §Runtime View — review mode primary flow + algorithm. `[ref: SDD/Runtime View; lines: 605-695]`
  2. **Test**: End-to-end pressure scenarios on a fixture docs/ tree:
     - Known-good docs (all required questions answerable from the corpus): `/doc-product review` returns PASS gap report.
     - Known-bad docs (one required question intentionally missing answer): returns FAIL with the exact gap named.
     - `--page docs/installation.md`: scope narrows correctly; only questions whose `pages:` intersects `installation.md` run.
     - Concurrency limit `READER_TEST_PARALLEL=2`: subprocess count never exceeds 2 at once (verified via `ps` snapshot during run).
     - `claude` CLI missing: mode exits before any subprocess call with the SDD-specified setup message `[ref: SDD/Error Handling — claude CLI missing; line: 660]`.
     - Non-interactive context (caller checking exit signal): on FAIL, the mode signals failure to its caller (Bash exit code from helper script, or a clear Markdown header for in-conversation use).
  3. **Implement**: Author `modes/review.md` per the SDD primary flow. The mode body is Markdown instructions to Claude that orchestrate: prereq check → load personas (T2.2 helper) → resolve scope → build plan → parallel dispatch via `xargs -P` or background-and-wait → aggregate via T2.4 renderer.
  4. **Validate**: All pressure scenarios produce documented behaviour. The full review run completes within the SDD performance target (≤ 60s for default 4 personas × 2 questions on a small docs/ tree).
  5. **Success**:
     - [ ] All 6 pressure scenarios pass `[ref: SDD/Acceptance Criteria — Review mode; lines: 898-907]`
     - [ ] Strict 100% required-question pass/fail logic enforced `[ref: SDD/ADR-3 + EARS criterion; lines: 779-783, 902]`
     - [ ] Performance target met `[ref: SDD/Quality Requirements — Performance; line: 815]`

- [ ] **T2.6 Phase 2 Validation** `[activity: validate]`

  - Run `/skill-author audit` on review mode files.
  - Run end-to-end review against a known-bad fixture (e.g. an early miyo-tomo README snapshot if available, or a stripped-down test fixture).
  - Verify gap report renders entirely inline; no `.reader-test/` directory created (per ADR-3).
  - Verify against SDD §Acceptance Criteria — Review mode (all 7 EARS criteria pass).
  - If any deviation from SDD was required, log in Deviations.

---

## Deviations

(None yet.)
