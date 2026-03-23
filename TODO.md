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

### Open

- [x] Logo needs to be changed to custom startup, should we have The Custom Agentic Startup as logo.. I would say yes.. needs to be changed in the Readme Too.
- [x] Script mentions that it will install the statusline to the users home directory config if I select repo, it should go to the repo
- [x] Error while trying to download the statusline: Could not download configure-statusline.sh — skipping statusline (SOURCE_URL now points to correct repo)
- [x] the installing lines have red text if there is an error (added `plugin update` fallback)
- [x] uses the wrong marketplace.. the startup, needs to use our own

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

- [x] Verify `ccusage` blocks parsed correctly (`inputTokens + outputTokens`, not `totalTokens`)
- [x] Audit `cache_creation_input_tokens` / `cache_read_input_tokens` handling in lib (confirmed: exclude both, I+O only matches /usage)
- [x] Add cleanup for /tmp files which are older then 14 days

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

### Delivered (follow-on, 2026-03-16)

- [x] `docs/agents.md` — full reference for all 8 roles and 15 activity agents
- [x] `docs/the-custom-philosophy.md` — why the fork exists
- [x] `docs/workflow.md` — added Step 0 (/constitution + multi-AI front-load), moved Multi-AI section before Step by Step
- [x] `docs/multi-ai-workflow.md` — fixed skill names, spec paths, template/script links, phase mapping explanation
- [x] `docs/output-styles.md` — added post-install cache location and customization note
- [x] `docs/plugins.md` — updated plugin IDs, added agents.md link, fixed philosophy link
- [x] `docs/skills.md` — replaced inline agent roster with agents.md link
- [x] `docs/statusline.md` — fixed script names, added nav anchors, curl quickstart, file location table, token bar ASCII viz
- [x] `docs/statusline-starship.md` — updated script and directory names
- [x] `docs/index.md` — added agents.md and the-custom-philosophy.md entries
- [x] `README.md` — updated product description, added License section
- [x] `LICENSE` — appended Marcus Breiden MIT block for new files, Reddit attribution for Starship integration
	
	

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

## #6 — Plugin Rename + tcs-helper + skill-author

**Branch:** multiple feature branches, merged to `customizing` 2026-03-23
**Status:** ✅ done

### Delivered

- [x] Rename plugins: `start` → `tcs-start`, `team` → `tcs-team`
- [x] New `tcs-helper` plugin — optional, for skill/agent development utilities
- [x] Rename `writing-skills` → `skill-author`, moved to `tcs-helper`
- [x] `skill-author` enriched with CSO, model selection, agent forking, TDD Iron Law (from obra/superpowers)
- [x] `find-agents.sh` — discovers installed agents across `~/.claude/agents/` and plugin caches
- [x] `get-specs-dir.sh` — reads startup.toml, falls back through standard chain; copied to all three plugins
- [x] Self-announcement lines added to all skills and agents
- [x] Hardcoded `.start/specs` paths replaced with configurable references in all skills/agents
- [x] `docs/concepts.md` — framework entry-point page (adapted from OpenSpec)
- [x] `docs/installation.md` — standalone install guide (curl wizard + manual marketplace steps)
- [x] `README.md` updated — better plugin/feature explanation, links to docs
- [x] `docs/index.md` updated — three-plugin architecture, concepts.md + installation.md added
- [x] `docs/plugins.md` rewritten — tcs-start / tcs-team / tcs-helper sections
- [x] All docs updated for tcs-start/tcs-team/tcs-helper naming
- [x] Slash command refs fixed: `/tcs-start:X` → `/X` (skills don't use plugin namespace in / menu)
- [x] `install.sh` / `uninstall.sh` updated for three plugins including tcs-helper
- [x] `~/.claude/CLAUDE.md` updated to reference `/skill-author` (tcs-helper)