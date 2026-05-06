---
title: "Phase 3: Extract Mode and Settings Parsers"
status: pending
version: "1.0"
phase: 3
---

# Phase 3: Extract Mode and Settings Parsers

## Phase Context

**GATE**: Read all referenced files before starting this phase.

**Specification References**:
- `[ref: SDD/Building Block View — Directory Map; lines: 244-280]` — parser scripts location
- `[ref: SDD/Implementation Examples — Settings Parser; lines: 582-600]` — TS parser approach
- `[ref: SDD/Acceptance Criteria — Extract mode; lines: 887-895]` — EARS criteria
- `[ref: SDD/Error Handling — Parser dependency missing + Settings file unparseable; lines: 666-668]` — failure modes
- `[ref: SDD/ADR-5; lines: 791-796]` — separate parsers + dependency reporting
- `[ref: PRD/Feature 3 — extract mode; lines: 138-163]` — PRD acceptance criteria

**Key Decisions**:
- ADR-5: separate Bash scripts per source type. Each detects its own runtime dependencies before parsing and surfaces a clear, actionable error when missing.
- v1 source coverage: TypeScript interface, JSON Schema, Pydantic / dataclass model. Manifest extraction is v2.
- Common output format: TSV with columns `name`, `type`, `default`, `description`. Rendered to Markdown via shared `templates/configuration-template.md`.
- Diff-vs-existing on re-run: never overwrite silently; surface changes for review.
- Missing-description fields → `[NEEDS DESCRIPTION]` markers, not fabricated.

**Dependencies**:
- Phase 1 (skeleton + mode router exists; `modes/extract.md` stub will be replaced).
- Independent of Phase 2; can begin in parallel calendar-wise once Phase 1 is done.

---

## Tasks

This phase delivers a working `extract` mode that produces `docs/configuration.md` from one of three settings sources, with clean dependency reporting when a required runtime is missing. Verifiable outcome: `/doc-product extract` on a TS interface produces a configuration page matching the source; on a Pydantic source with `python3` missing, surfaces a clear install instruction.

- [ ] **T3.1 parse-ts-settings.sh — TypeScript Interface Parser** `[activity: build-feature]` `[parallel: true]`

  1. **Prime**: Read SDD §Settings Parser implementation example + ADR-5 rationale. `[ref: SDD/Settings Parser; lines: 582-600]`
  2. **Test**: Pressure scenarios on fixture TS files:
     - Single `interface Settings { … }` with primitive types and JSDoc → emits TSV with name / type / default (where `=` literal present) / description.
     - Field with no JSDoc → description column is `[NEEDS DESCRIPTION]`.
     - Field with union type (`string | number`): emits the literal union as the type.
     - Multiple interfaces in one file (`Settings`, `InternalState`): script asks via stdout which one is user-facing settings (or relies on caller's dispatcher to disambiguate via AskUserQuestion).
     - Source contains generics, mapped types, intersection types: emits `[NEEDS REVIEW]` for those fields rather than guessing.
  3. **Implement**: Author `scripts/parse-ts-settings.sh`. Bash 3.2 compatible. Regex-based parsing; reasonable cleanup of JSDoc comments (`/** … */` block extraction). Output: TSV on stdout. Errors / `[NEEDS REVIEW]` lines on stderr.
  4. **Validate**: All pressure scenarios pass; `shellcheck` clean.
  5. **Success**:
     - [ ] TS interface produces complete TSV `[ref: PRD/F3 AC1; lines: 142-143]`
     - [ ] Missing JSDoc → `[NEEDS DESCRIPTION]`, never fabricated `[ref: PRD/F3 AC5; lines: 159-160]`
     - [ ] Unparseable constructs → `[NEEDS REVIEW]`, listed on stderr `[ref: SDD/Risks — TS parsing fragility; lines: 922-923]`

- [ ] **T3.2 parse-jsonschema.sh — JSON Schema Parser** `[activity: build-feature]` `[parallel: true]`

  1. **Prime**: Read SDD ADR-5 + the dependency-check requirement (`jq` is required for this parser).
  2. **Test**: Pressure scenarios:
     - Happy path JSON Schema with `properties`, `default`, `description` → emits TSV.
     - Missing description → `[NEEDS DESCRIPTION]`.
     - Field with `enum` constraint → type column captures it (e.g. `enum: "small" | "medium" | "large"`).
     - `jq` not on PATH → exits non-zero before parsing with the SDD-specified missing-dependency message (names jq, says why, gives install command).
     - Schema lacks `properties` (e.g. it's a top-level array schema): exits with descriptive error, not a fabricated empty table.
  3. **Implement**: Author `scripts/parse-jsonschema.sh`. Front-runs `command -v jq` check. Uses `jq` filters to walk `properties`, emit TSV.
  4. **Validate**: All pressure scenarios pass.
  5. **Success**:
     - [ ] JSON Schema produces complete TSV `[ref: PRD/F3 AC2; lines: 144-145]`
     - [ ] Missing-dependency error surfaces `(a) name (b) why (c) install command` per ADR-5 `[ref: SDD/ADR-5 added constraint; lines: 794-795]`

- [ ] **T3.3 parse-pydantic.sh — Pydantic / Dataclass Parser** `[activity: build-feature]` `[parallel: true]`

  1. **Prime**: Read SDD ADR-5 + the dependency-check requirement (`python3` is required for this parser).
  2. **Test**: Pressure scenarios:
     - Pydantic v2 `BaseModel` subclass with `Field(default=…, description="…")` → TSV.
     - Pydantic v1 `BaseModel` (no `Field()`, just type annotations + class-level defaults) → TSV.
     - Plain `@dataclass` with class-level defaults and docstrings → TSV.
     - Field without `description` / no class-level docstring → `[NEEDS DESCRIPTION]`.
     - `python3` not on PATH → SDD-specified missing-dependency error, names python3, says why, gives `brew install python3` (macOS) and `apt-get install python3` (Linux) install commands.
     - Module that imports unavailable third-party deps (e.g. `pydantic` not installed in the parser's run environment): surfaces "Pydantic module unavailable — install with `pip install pydantic` in the parser's environment, or convert to JSON Schema first" rather than crashing.
  3. **Implement**: Author `scripts/parse-pydantic.sh`. Front-runs `command -v python3` check. Uses inline `python3 -c '…'` to introspect the module via `importlib` and emit TSV. Handle Pydantic v1 / v2 / dataclass via duck-typing. Gracefully report dependency issues.
  4. **Validate**: All pressure scenarios pass.
  5. **Success**:
     - [ ] Pydantic / dataclass produces complete TSV `[ref: PRD/F3 AC3; lines: 146-147]`
     - [ ] Missing python3 → SDD-specified install message `[ref: SDD/Acceptance Criteria — extract dependency; lines: 894-895]`
     - [ ] Missing pydantic module → actionable secondary install message; does not crash

- [ ] **T3.4 Configuration Template + Markdown Renderer** `[activity: template-design]`

  1. **Prime**: Read PRD F3 acceptance criteria for the configuration page format.
  2. **Test**: Given a fixture TSV file, the renderer produces a Markdown table matching the template: rows for each setting; columns for Name, Type, Default, Description; example value row per setting if available; `[NEEDS DESCRIPTION]` and `[NEEDS REVIEW]` markers preserved verbatim.
  3. **Implement**: Author `templates/configuration-template.md`. Renderer logic lives in `modes/extract.md` (Markdown instructions to Claude — no Bash write). Include a header section for the configuration page (intro paragraph + table).
  4. **Validate**: Fixture-driven inspection.
  5. **Success**:
     - [ ] Template renders TSV → configuration.md matching PRD F3 contract `[ref: PRD/F3 user story + ACs; lines: 138-163]`
     - [ ] Markers preserved through rendering pipeline

- [ ] **T3.5 modes/extract.md — Source Detection, Dispatch, Diff** `[activity: build-feature]`

  1. **Prime**: Read SDD §ADR-5 + acceptance criteria EARS clauses for extract.
  2. **Test**: Pressure scenarios:
     - Repo with a single TS settings file (e.g. `src/settings.ts` containing `interface Settings`): mode detects, dispatches to T3.1 parser, renders configuration.md.
     - Repo with both TS and Python settings: mode asks via AskUserQuestion which is the user-facing source.
     - Repo with no recognised source: mode asks via AskUserQuestion for the source path and type.
     - Re-run after settings change: mode produces new TSV, diffs against existing `docs/configuration.md`, surfaces changes for the author's review (does NOT auto-overwrite).
     - First-run with no `docs/configuration.md`: mode writes the file directly (no diff possible).
     - v1 manifest behaviour: a `manifest.json` / `plugin.json` in the repo is silently ignored (per PRD F3 final AC).
  3. **Implement**: Author `modes/extract.md` per SDD. Source detection uses file globbing (`*.ts`, `*.json`, `*.py`). Dispatcher invokes T3.1/T3.2/T3.3 via Bash. Diff is `git diff --no-index` against existing file or by string compare.
  4. **Validate**: All pressure scenarios pass.
  5. **Success**:
     - [ ] Source detection + dispatch matches PRD F3 AC1-AC3 `[ref: PRD/F3; lines: 142-147]`
     - [ ] Re-run diff surfaces changes, never silent overwrite `[ref: PRD/F3 AC4; lines: 156-158]`
     - [ ] v1 ignores manifest sources `[ref: SDD/Acceptance Criteria — extract last clause; line: 893]`

- [ ] **T3.6 Phase 3 Validation** `[activity: validate]`

  - Run `/skill-author audit`.
  - Run end-to-end extract against three real targets: a fixture TS interface, a fixture JSON Schema, a fixture Pydantic class.
  - Run extract against a test repo with `python3` artificially removed from PATH — verify the missing-dependency message format.
  - Verify against SDD §Acceptance Criteria — Extract mode (all 7 EARS criteria pass).
  - If any deviation from SDD was required, log in Deviations.

---

## Deviations

(None yet.)
