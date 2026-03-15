# The Custom Startup — TODO

Tracking all customization work on the `customizing` branch.
Feature branches are created per item so each can be PR'd independently upstream.

---

## #1 — install.sh: Modular & Flexible

**Branch:** `feat/install-modular`
**Status:** pending

### Goals

- [ ] Ask **where** to install: Global (`~/.claude`) or repo-local (`.claude/` in current dir)
- [ ] Ask **which plugins**: `start` only, `team` only, or both
- [ ] Ask **which output style**: The Startup / The ScaleUp / skip
- [ ] Ask **whether to install statusline** (yes / no / already have one)
- [ ] Make **marketplace URL configurable** via CLI flag (`--marketplace <org/repo>`), default to `MMoMM-org/the-custom-startup`
- [ ] All **dependency checks upfront** together, with OS-specific install instructions (macOS/Ubuntu/Windows)
- [ ] **Re-run support**: calling the script again lets you change specific things (statusline, agent config, output style) without full reinstall
- [ ] **Idempotency**: re-running is safe, no destructive overwrites
- [ ] **Statusline conflict detection**: check if `statusLine` is already set in settings.json, offer options (keep / replace / skip)
- [ ] **Rename statusline file**: from generic `statusline.sh` → `the-custom-startup-statusline.sh`
- [ ] **Granular exit codes** per step, better error messages
- [ ] Optional `--dry-run` flag: show what would happen without doing it

---

## #2 — Statusline: Configurator + Alternatives

**Branch:** `feat/statusline-configurator`
**Status:** pending

### Goals

**Standalone configurator script** (`scripts/configure-statusline.sh`):
- [ ] Interactive wizard: choose statusline variant, set plan, toggle components, custom format
- [ ] Works globally and **per-repo** (each repo can have its own statusline config)
- [ ] Generates `statusline.toml` from wizard answers
- [ ] Re-runnable without re-downloading anything

**Three statusline variants** (user picks one during install/configure):

1. **`the-custom-startup-statusline.sh`** — current script from this repo (renamed), TOML-configured
2. **`the-custom-startup-statusline-simple.sh`** — lightweight, no `jq` dependency
3. **`the-custom-startup-statusline-starship.sh`** — Starship-based (requires Starship already installed)

**Starship integration:**
- [ ] Document the approach from Reddit (r/ClaudeCode) in `docs/statusline-starship.md` with attribution link
- [ ] Implement the simple Starship config described in that post
- [ ] Add Starship detection to install.sh (skip option if not installed)
- [ ] All three variants share the same TOML config format where possible

**Fix in existing statusline.sh:**
- [ ] Verify `ccusage` blocks are parsed correctly from Claude Code JSON input
- [ ] Audit `cache_creation_input_tokens` and `cache_read_input_tokens` handling

**Starship source (save in docs):**
> https://www.reddit.com/r/ClaudeCode/comments/1r81675/use_your_starship_prompt_as_the_claude_code/

---

## #3 — README: Split & Restructure

**Branch:** `feat/docs-restructure`
**Status:** pending

### Goals

**README.md** becomes a lean entry point (~100 lines):
- [ ] What is it (2–3 sentences)
- [ ] Quick install (one-liner + manual option)
- [ ] Quick start (2 commands)
- [ ] Links to docs/

**Extract to `docs/`:**
- [ ] `docs/workflow.md` — Complete workflow, step-by-step walkthrough, resume pattern
- [ ] `docs/skills.md` — Skill reference table, capability matrix, when-skills-overlap
- [ ] `docs/statusline.md` — Config, placeholders, color thresholds, plan defaults
- [ ] `docs/output-styles.md` — The Startup vs The ScaleUp comparison
- [ ] `docs/philosophy.md` — Why, principles, research references (merge with existing PHILOSOPHY.md / PRINCIPLES.md)
- [ ] `docs/statusline-starship.md` — Starship integration guide (see #2)

---

## #4 — Multi-AI Workflow

**Branch:** `feat/multi-ai-workflow`
**Status:** pending

### Goals

**Documentation** (`docs/multi-ai-workflow.md`):
- [ ] Which phases work best in which tool:
  - `/specify` PRD → Claude.ai chat (conversational, no file access needed)
  - `/brainstorm` → Claude.ai or Perplexity
  - `/analyze` → Perplexity (research-heavy)
  - `/implement` → stays in Claude Code (needs file access)
- [ ] Clear decision guide: when to leave Claude Code

**Export/Import tooling:**
- [ ] `scripts/export-spec.sh` — exports spec context as a self-contained prompt for paste into any chat AI
- [ ] `scripts/import-spec.sh` — imports AI-generated output (e.g. architecture doc) as SDD into `.start/specs/`

**Prompt templates** (`docs/templates/`):
- [ ] `docs/templates/prd-prompt.md` — template for Claude.ai to create a PRD
- [ ] `docs/templates/brainstorm-prompt.md` — template for ideation sessions
- [ ] `docs/templates/perplexity-research.md` — template for Perplexity research queries
- [ ] Each template includes: context setup, the-startup framing, expected output format

---

## General

- [ ] All new files in **English**
- [ ] Each feature gets its own branch → PR-able upstream
- [ ] `customizing` branch = integration + planning only, no direct implementation commits
