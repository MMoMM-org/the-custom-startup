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

- [ ] Verify `ccusage` blocks parsed correctly (`inputTokens + outputTokens`, not `totalTokens`)
- [ ] Audit `cache_creation_input_tokens` / `cache_read_input_tokens` handling in lib
- [ ] Add cleanup for /tmp files which are older then 14 days

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

### Open

- [ ] `docs/the-custom-philosophy.md` — why the change? 
- [ ] `docs/agents.md` — bundle the agent information here 

### Notes:

- workflow.md
	- before step by step we need the optional setup via /constitution
	- and before that the multi-ai Extension part
- multi-ai-workflow.md
	- the phase mapping doesn't relate to anything else in the documentation, the core loop is different
	- if it makes sense to have those phases we should explain them or reference them
	- but we also need to map them to the core loop.. or change the core loop to reference the phases
	- so which is the better approach?
	- we should link to the template files from the documentation and to the skills directly
	- same goes for the scripts.
	- the import-spec.sh part references .start is that only a documentation issue or a general issue (also code)?
	- typical session flow / step by step.. we should reference the files, also same issue with .start
- output-styles.md
	- customizing, we should probably add where they are saved after installation. People will probably not fork the repo to make changes to them
- plugin.md
	- we need to change the text to the-custom-startup etc.
	- the full reference should state that this is the original description and we should mention that some things where changed
		- eg. location of specs etc.. so that we don't need to update the original description
	- the tables should have a brief description what the agents / commands are used for
		- I need to figure out if we need more documentation later on to make it clearer how this is all used
- skills.md
	- again we need to change the naming to the-custom-startup
	- we should probably create an agents.md file and more the agents stuff to there
- statusline.md
	- also add the curl way to quick setup
	- link the files directly or say where they are located (e.g. statusline.toml) don't let the user guess or figure it out by himself
	- add a quick overview at the top.. standard, enhanced, starship with links to the headers
	- we need a visible representation how the token budget bar works if we use token not dollar
		- /usage in claude code displays all the necessary information correctly, question is just how to get this
- general readme or better license
	- we should state that the parts are also the mit license c Marcus Breiden, except the Starship Code.
	
	

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
