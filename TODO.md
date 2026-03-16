# The Custom Startup — TODO

Tracking all customization work on the `customizing` branch.
Feature branches are created per item so each can be PR'd independently upstream.

---

## #1 — install.sh: Modular & Flexible

**Branch:** `feat/install-modular`
**Status:** ✅ done (merged to `customizing` 2026-03-16)

### Delivered

- [x] Ask **where** to install: global / current repo / other repo path
- [x] Ask **which plugins**: start / team / both
- [x] Ask **which output style**: The Startup / The ScaleUp / skip
- [x] Ask **whether to install statusline** — with conflict detection (keep / replace / skip)
- [x] All **dependency checks upfront** (claude, jq, curl) with OS-specific hints
- [x] **Idempotency**: re-running is safe
- [x] **Statusline conflict detection**: checks existing `statusLine` in settings.json
- [x] **Rename scripts**: `statusline-lib.sh` → `the-custom-startup-statusline-lib.sh`, `configure-statusline.sh` → `the-custom-startup-configure-statusline.sh`
- [x] **Configurable specs directory**: prompts for name, writes `.claude/startup.toml`
- [x] **Path resolution chain**: startup.toml → the-custom-startup/specs → .start/specs → docs/specs
- [x] **Confirmation summary** before doing anything
- [x] stdin via `/dev/tty` (works with `curl | bash`)

### Deferred (out of scope)

- [ ] `--marketplace <org/repo>` CLI flag
- [ ] `--dry-run` flag
- [ ] Granular exit codes per step

---

## #2 — Statusline: Configurator + Alternatives

**Branch:** `feat/statusline-configurator`
**Status:** ✅ done (merged to `customizing`)

### Delivered

- [x] `the-custom-startup-configure-statusline.sh` — interactive wizard, variant selection, TOML generation, remote install, `--repo-path` support
- [x] `the-custom-startup-statusline-lib.sh` — shared library (TOML parser, config, plan data, cache, formatters)
- [x] `the-custom-startup-statusline-standard.sh` — single-line, placeholder-based
- [x] `the-custom-startup-statusline-enhanced.sh` — two-line, token budget bar, OSC 8, ccusage
- [x] `the-custom-startup-statusline-starship.sh` — Starship bridge
- [x] `statusline.toml` — unified config template
- [x] `docs/statusline.md` — full reference
- [x] `docs/statusline-starship.md` — Starship setup guide

### Open

- [ ] Verify `ccusage` blocks parsed correctly (`inputTokens + outputTokens`, not `totalTokens`)
- [ ] Audit `cache_creation_input_tokens` / `cache_read_input_tokens` handling in lib

---

## #3 — README: Split & Restructure

**Branch:** `feat/docs-restructure`
**Status:** ✅ done (merged to `customizing` 2026-03-16)

### Delivered

- [x] `README.md` — lean entry point with THE CUSTOM STARTUP ASCII logo, fork attribution, Quick Start, links to docs/
- [x] `docs/index.md` — documentation index (one-liner per doc, organized by category)
- [x] `docs/workflow.md` — complete workflow, step-by-step walkthrough, startup.toml config, fallback chain, multi-AI reference
- [x] `docs/skills.md` — decision tree, full command reference table, skill details, team agent roster
- [x] `docs/plugins.md` — start plugin, team plugin, output styles, install-from-fork instructions
- [x] `docs/output-styles.md` — The Startup vs The ScaleUp comparison with voice samples and behavior descriptions
- [x] `docs/PHILOSOPHY.md` — condensed into curated guide: core philosophy, activity-based architecture, research foundation, agent design principles

---

## #4 — Multi-AI Workflow

**Branch:** `feat/multi-ai-workflow`
**Status:** ✅ done

### Delivered

- [x] `docs/multi-ai-workflow.md` — which phases work best in which tool
- [x] `scripts/export-spec.sh` — exports spec as prompt for external AI tools
- [x] `scripts/import-spec.sh` — imports AI-generated output as PRD/SDD
- [x] `docs/templates/prd-prompt.md`, `brainstorm-prompt.md`, `research-prompt.md`, `constitution-prompt.md`
- [x] `docs/templates/setup-claude-project.md`, `setup-perplexity-space.md`

---

## #5 — Configurable Specs Directory

**Status:** ✅ done (delivered as part of #1, 2026-03-16)

- [x] `.claude/startup.toml` written by install.sh with `specs_dir` + `ideas_dir`
- [x] `export-spec.sh` + `import-spec.sh` use full priority chain
- [x] `specify-meta` SKILL.md updated with path resolution instructions
- [x] All skill example paths updated: `.start/specs/` → `the-custom-startup/specs/`

---

## General

- [ ] All new files in **English**
- [ ] Each feature gets its own branch → PR-able upstream
