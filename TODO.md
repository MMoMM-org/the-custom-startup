# The Custom Startup — TODO

Tracking all customization work on the `customizing` branch.
Feature branches are created per item so each can be PR'd independently upstream.

---

## TCS v2 — Entscheidungsprotokoll & Roadmap

**Stand:** 2026-03-27

### Entschiedene Punkte (nicht nochmal diskutieren)

- [x] 4-Plugin-Architektur: tcs-workflow / tcs-team / tcs-helper / tcs-patterns — **same repo**
- [x] tcs-start → tcs-workflow Umbenennung — **done**
- [x] tcs-patterns: 17 Skills, same repo — **done** (merged)
- [x] skill-evaluate + skill-import — **done** (merged)
- [x] M2 Scope: file-only, kein MCP — MCP kommt in M4/M5
- [x] Routing-Grenze: MCP/Kairn ab **medium lived** (nicht erst "really short") — wird in M5 umgesetzt
  - Files bleiben Source of Truth; MCP/Kairn sind zusätzliche Abfrageebene, kein Ersatz
- [x] Reihenfolge: M2 → M4 → M5

### Reihenfolge

```
M2 (Memory System, file-only)
  └─ M4 (Satori/MCP Gateway)
       └─ M5 (Memory + MCP Integration)
```

M4 kann parallel zu späteren M2-Phasen beginnen wenn M2 Phase 1-3 stabil ist.

---

## M2 — Memory + CLAUDE.md System

**Spec:** `docs/XDD/specs/001-memory-claude/` (PRD ✓, SDD ✓, Plan ✓)
**Plan:** `docs/superpowers/plans/2026-03-25-memory-system-m2.md` (6 Phasen)
**Status:** ✅ complete (merged to `customizing` 2026-03-26)

### Vor dem Start

- [x] ROADMAP.md: `.start/specs/` → `docs/XDD/specs/` korrigieren
- [x] `2026-03-25-memory-system-m2.md`: `.start/specs/` → `docs/XDD/specs/` korrigieren
- [x] `001-memory-claude/solution.md` §3 Routing-Tabelle: Hinweis ergänzen dass MCP ab medium lived in M5 einsetzt

### Implementation (6 Phasen)

- [x] Phase 1: Python-Infrastruktur (`lib/`, `reflect_utils.py`, Queue-Format)
- [x] Phase 2: Hooks (`capture_learning.py`, `session_start_reminder.py`, `check_learnings.py`, `post_commit_reminder.py`)
- [x] Phase 3: `memory-add` Routing-Logik
- [x] Phase 4: `memory-sync`, `memory-cleanup`, `memory-promote`
- [x] Phase 5: `tcs-helper:setup` (Onboarding-Wizard + Templates)
- [x] Phase 6: Integration & Validierung (23 tests pass)

### Nach M2

- [x] `tcs-helper:setup` → tcs-patterns als optionalen Install-Schritt einbauen
- [x] AGENTS.md / README: tcs-patterns dokumentieren
- [x] tcs-patterns `reference/` Stubs befüllen (citypaul/.dotfiles als Quelle) — 2026-03-27
- [x] `testing` + `test-design-reviewer` Skills zu tcs-patterns hinzufügen (17 total) — 2026-03-27
- [x] `xdd-tdd` um optionalen MUTATE-Checkpoint erweitert — 2026-03-27
- [x] `docs/concept/sources.md` Attribution aktualisiert — 2026-03-27

---

## M4 — Satori/MCP Gateway

**Repo:** `MMoMM-org/miyo-satori` (standalone, TCS includes as git submodule)
**Spec:** `docs/XDD/specs/004-satori-gateway/` (PRD ✓, SDD fehlt, Plan fehlt)
**Basis:** `docs/concept/v2/context-mode-MCP-Server.md` + `docs/concept/v2/TCS v2 Memory & Context Layout Spec.md` §5
**Status:** PRD geschrieben — SDD als nächstes

### Entschiedene Punkte

- [x] Name: **Satori** (`miyo-satori`)
- [x] Eigenes Repo — standalone, als git submodule in TCS unter `modules/satori/`; wiederverwendbar außerhalb TCS
- [x] Gateway/Registry: single MCP entry point, downstream Server via Namespace `<server>_<tool>`
- [x] Handler/Plugin-Architektur zwischen Satori und jedem downstream Server (default: passthrough)
- [x] Hot/cold: Server nur starten wenn a) enabled und b) tatsächlich aufgerufen
- [x] Security: OUT primär (keine Secrets an downstream), IN optional (Filter auf Rückgabe)
- [x] Kairn: optionaler Handler, kein hard dependency
- [x] g/p/r Config-Separation: `~/.satori/mcp.json` / project dir / repo root

### Noch offen (für SDD)

- [ ] Discovery: wie TCS-Skills erkennen ob Satori läuft (tool-check vs CLAUDE.md flag vs beides)
- [ ] Auto-Registration: `.mcp.json` im Repo-Root automatisch registrieren — abhängig von Claude Code MCP-Reload-Verhalten

---

## M5 — Memory + MCP Integration

**Spec:** `docs/XDD/specs/005-memory-mcp/` (requirements.md vorhanden, Placeholder)
**Status:** Wartet auf M2 + M4

### Kernentscheidung (bereits gefällt)

| Lifetime | M2 (file) | M5 (MCP added) |
|---|---|---|
| medium lived | `docs/ai/memory/` Source of Truth | + context-mode Index + Kairn semantisch |
| short lived | `docs/ai/memory/context.md` | context-mode primary |
| really short | context window | context-mode primary + Kairn |

---

## Offene Konzept-Fragen

- [ ] `docs/concept/v2/` ist Perplexity-Brainstorming — **nicht direkt als Spec verwenden**
  - Für M4: §5 (Context-Mode + Kairn) als Basis heranziehen, bereinigen
  - Für M5: Routing-Tabelle §3.2 als Ausgangspunkt, Grenze aber verschoben (→ oben)
- [x] ADR-Location: `docs/XDD/adr/` default (via `startup.toml` `docs_base` → configurable per repo)

---

## Nächster Schritt → M4 starten

1. Entscheidungspunkte in TODO.md M4-Abschnitt durchgehen (Name, Registry-Konzept, Hot/cold)
2. `docs/concept/v2/context-mode-MCP-Server.md` + `TCS v2 Memory & Context Layout Spec.md §5` lesen
3. Spec unter `docs/XDD/specs/004-satori-gateway/` schreiben (PRD → SDD → Plan)

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