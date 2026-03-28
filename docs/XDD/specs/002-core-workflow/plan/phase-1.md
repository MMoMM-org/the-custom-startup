---
title: "Phase 1: Foundation"
status: completed
version: "1.0"
phase: 1
---

# Phase 1: Foundation

## Phase Context

**GATE**: Read all referenced files before starting this phase.

**Specification References**:
- `[ref: SDD/Building Block View/Directory Map; lines: 173-259]` — full directory map for all three plugins
- `[ref: SDD/Interface Specifications/startup.toml Schema; lines: 265-283]` — startup.toml resolution logic
- `[ref: SDD/ADR-1]` — git mv approach for plugin rename
- `[ref: SDD/ADR-2]` — G/R scope model for startup.toml
- `[ref: SDD/ADR-5]` — one-time migration, no legacy fallback
- `[ref: SDD/Constraints; CON-1, CON-6]` — bash 3.2, Python venv
- `[ref: PRD/Feature 1]` — plugin rename acceptance criteria
- `[ref: PRD/Feature 15]` — docs/XDD/ and startup.toml acceptance criteria

**Key Decisions**:
- ADR-1: Use `git mv plugins/tcs-start plugins/tcs-workflow` — preserves git history; no copy-and-delete
- ADR-2: `~/.claude/startup.toml` (global, user-wide defaults) overridden by `.claude/startup.toml` (repo-level). Single `[tcs] docs_base` key.
- ADR-5: One-time migration script moves `.start/specs/` → `docs/XDD/specs/`. No legacy path fallback after migration.
- CON-6: Python venv — fix `--break-system-packages` anti-pattern in tcs-helper test setup

**Dependencies**:
- None — this is the foundation phase. All other phases depend on Phase 1.

---

## Tasks

Establishes the structural foundation: plugin rename, config file, docs/XDD/ directory tree, one-time spec migration, and Python venv fix. After this phase, tcs-workflow exists as a plugin directory with correct `plugin.json`, `startup.toml` is in place, `docs/XDD/` is the canonical artifact location, and CI can run tests with venv.

- [x] **T1.1 Plugin directory rename (tcs-start → tcs-workflow)** `[activity: backend-api]`

  1. Prime: Read `plugins/tcs-start/.claude-plugin/plugin.json` to understand current manifest. Read `plugins/tcs-helper/.claude-plugin/plugin.json` and `plugins/tcs-team/.claude-plugin/plugin.json` to understand coexistence. `[ref: SDD/Building Block View/Directory Map; lines: 175-218]`
  2. Test: After rename, `ls plugins/tcs-workflow/` returns the full directory tree. `plugin.json` name field reads `"tcs-workflow"`. `plugins/tcs-start/` no longer exists. Git history for all files is preserved (`git log --follow plugins/tcs-workflow/skills/brainstorm/SKILL.md` shows pre-rename commits). `[ref: PRD/Feature 1/AC-1.1, AC-1.2, AC-1.5]`
  3. Implement: Run `git mv plugins/tcs-start plugins/tcs-workflow`. Update `plugin.json`: change `name` to `"tcs-workflow"`, add `agents` key pointing to `agents/` directory. Update any internal `@import` or cross-references inside the plugin that use the old name. `[ref: SDD/ADR-1]`
  4. Validate: Run `git log --follow plugins/tcs-workflow/skills/brainstorm/SKILL.md` — pre-rename commits present. `ls plugins/tcs-workflow/` — full skill tree intact. `plugins/tcs-start/` absent. Plugin manifest valid JSON. `[ref: PRD/Feature 1/AC-1.5]`
  5. Success: `plugins/tcs-workflow/` exists with all original content; `plugins/tcs-start/` is gone; `plugin.json` name = `"tcs-workflow"` `[ref: PRD/Feature 1/AC-1.1]`; git history preserved `[ref: PRD/Feature 1/AC-1.5]`; `./install.sh` completes without error `[ref: SDD/Project Commands]`

- [x] **T1.2 Create .claude/startup.toml with G/R scope** `[activity: domain-modeling]`

  1. Prime: Read `[ref: SDD/Interface Specifications/startup.toml Schema; lines: 265-283]` for schema and resolution logic. Read `plugins/tcs-workflow/skills/xdd-meta/SKILL.md` to understand current path resolution. `[ref: PRD/Feature 15]`
  2. Test: `.claude/startup.toml` exists with valid TOML syntax. `[tcs] docs_base = "docs/XDD"` present. TOML parses without error (`python3 -c "import tomllib; tomllib.load(open('.claude/startup.toml', 'rb'))"`). Resolution logic in xdd-meta: `docs_base` from `.claude/startup.toml` takes priority over the default. If `.claude/startup.toml` absent, default `docs/XDD` applies. `[ref: PRD/Feature 15/AC-15.1, AC-15.3]`
  3. Implement: Create `.claude/startup.toml` with content from `[ref: SDD/Interface Specifications/startup.toml Schema]`. Update `plugins/tcs-workflow/skills/xdd-meta/SKILL.md` to implement the resolution logic: bash reads `.claude/startup.toml` with `grep`/`sed` (no TOML library required — extract `docs_base` value from `[tcs]` section). `[ref: SDD/ADR-2]`
  4. Validate: `.claude/startup.toml` passes TOML parse. xdd-meta resolution test: with `.claude/startup.toml` present, `docs_base = "docs/XDD"`. With file absent, same default. With custom value `docs_base = "custom/path"`, resolution returns `custom/path`. `[ref: PRD/Feature 15/AC-15.3]`
  5. Success: `.claude/startup.toml` created with correct schema `[ref: PRD/Feature 15/AC-15.1]`; xdd-meta reads `docs_base` from file if present, defaults to `docs/XDD` if absent `[ref: PRD/Feature 15/AC-15.3]`; bash 3.2 compatible (no TOML library, grep/sed only) `[ref: SDD/CON-1]`

- [x] **T1.3 Create docs/XDD/ directory tree** `[activity: backend-api]`

  1. Prime: Read `[ref: SDD/Building Block View/Directory Map/Config and artifact directories; lines: 244-258]` for exact directory structure. Read `.gitignore` to understand current gitignore patterns. `[ref: PRD/Feature 15]`
  2. Test: `docs/XDD/specs/`, `docs/XDD/adr/`, `docs/XDD/ideas/` all exist. `docs/ai/external/claude/` exists. `.gitignore` includes `docs/ai/external/` entry. Each new directory has a `.gitkeep` so git tracks it. `[ref: PRD/Feature 15/AC-15.1, AC-15.2]`
  3. Implement: Create `docs/XDD/specs/`, `docs/XDD/adr/`, `docs/XDD/ideas/` with `.gitkeep` files. Create `docs/ai/external/claude/` with `.gitkeep`. Add `docs/ai/external/` to `.gitignore`. `[ref: SDD/Building Block View/Directory Map; lines: 250-258]`
  4. Validate: All 4 directories exist. `.gitkeep` files present. `.gitignore` contains `docs/ai/external/`. `git status` shows new directories tracked (not ignored). `[ref: PRD/Feature 15/AC-15.2]`
  5. Success: Directory tree matches SDD spec exactly `[ref: SDD/Building Block View/Directory Map; lines: 244-258]`; `docs/ai/external/` is gitignored `[ref: SDD/Building Block View/Directory Map; line: 258]`; `docs/XDD/` dirs are tracked `[ref: PRD/Feature 15/AC-15.1]`

- [x] **T1.4 One-time spec migration (.start/specs/ → docs/XDD/specs/)** `[activity: backend-api]`

  1. Prime: Read `[ref: SDD/ADR-5]` — one-time migration, no legacy fallback. Run `ls .start/specs/` to see current spec directories. Check if any skills hardcode `.start/specs/` path. `[ref: PRD/Feature 15]`
  2. Test: After migration, `docs/XDD/specs/` contains all directories previously in `.start/specs/`. `.start/specs/` is empty or removed. No skill references `.start/specs/` (grep check). Git history for migrated files preserved (`git log --follow`). `[ref: PRD/Feature 15/AC-15.4, AC-15.5]`
  3. Implement: Run `git mv .start/specs/* docs/XDD/specs/` (or loop for each spec directory). If `.start/specs/` is now empty, remove it. Search all SKILL.md files for `.start/specs/` references with `rg ".start/specs"` — update each to `docs/XDD/specs/`. `[ref: SDD/ADR-5]`
  4. Validate: `ls docs/XDD/specs/` shows migrated directories. `rg ".start/specs" plugins/` returns 0 results. `git log --follow docs/XDD/specs/002-core-workflow/requirements.md` shows pre-migration commits. `[ref: PRD/Feature 15/AC-15.4]`
  5. Success: All specs in `docs/XDD/specs/` `[ref: PRD/Feature 15/AC-15.1]`; no skill references old path `[ref: SDD/ADR-5]`; git history preserved `[ref: PRD/Feature 15/AC-15.5]`

- [x] **T1.5 Fix Python venv in tcs-helper test setup** `[activity: backend-api]`

  1. Prime: Run `ls tests/tcs-helper/` to find test files. Read any `conftest.py` or test runner scripts that use `--break-system-packages`. Read `[ref: SDD/CON-6]`. `[ref: PRD/Implementation Principles/Cross-Cutting]`
  2. Test: Running `source venv/bin/activate && python3 -m pytest tests/tcs-helper/ -q` succeeds. No invocation of `pip install --break-system-packages` anywhere in tests/ or scripts/. `venv/` directory excluded from git (`.gitignore` entry present). `[ref: SDD/CON-6]`
  3. Implement: Create `venv/` if absent: `python3 -m venv venv && source venv/bin/activate && pip install pytest`. Remove any `--break-system-packages` flags. Add `venv/` to `.gitignore` if not already present. Update any CI or test runner docs to reference venv activation. `[ref: SDD/CON-6]`
  4. Validate: `source venv/bin/activate && python3 -m pytest tests/tcs-helper/ -q` — all tests pass. `rg "break-system-packages" .` returns 0 results. `.gitignore` contains `venv/`. `[ref: SDD/CON-6]`
  5. Success: All tcs-helper tests pass with venv `[ref: SDD/CON-6]`; `--break-system-packages` removed everywhere `[ref: SDD/CON-6]`; `venv/` gitignored `[ref: SDD/CON-6]`

- [x] **T1.6 Phase 1 Validation** `[activity: validate]`

  - Run `./install.sh` — completes without error; `tcs-workflow` plugin listed.
  - `ls plugins/tcs-workflow/` — full skill tree present; `plugins/tcs-start/` absent.
  - `python3 -c "import tomllib; tomllib.load(open('.claude/startup.toml', 'rb'))"` — valid TOML.
  - `ls docs/XDD/specs/` — spec directories migrated.
  - `rg ".start/specs" plugins/` — 0 results.
  - `source venv/bin/activate && python3 -m pytest tests/tcs-helper/ -q` — all pass.
  - All Phase 1 PRD acceptance criteria: Feature 1 (AC-1.1, AC-1.2, AC-1.5) and Feature 15 (AC-15.1–AC-15.5) verifiably met.
