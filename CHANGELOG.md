# Changelog

All notable changes to The Custom Agentic Startup will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased] — docs navigation

### Fixed

- **Five relative links pointed outside their own directories (#137).** Fallout from the docs
  rewrite, which moved the flat `docs/*.md` files into `getting-started/`, `guides/` and
  `reference/` without updating the prefixes aimed at them. Every target existed one directory
  over, so each link looked plausible while resolving to nothing. Three sat in
  `installation.md` alone, sending anyone following the manual install to a 404 for the
  `startup.toml` format, the output styles and the multi-AI templates — the three things that
  section tells them to read next. A sixth of the same class, the statusline guide, was fixed in
  #135.

### Added

- **`tests/test_docs_links.py` resolves every relative link in the user-facing docs.** Nothing
  catches this class by reading a diff, so it is checked rather than remembered. It runs in the
  existing pytest job — no new CI surface — skips fenced blocks and inline code spans (the
  plan-file checklist in `xdd.md` and the Starship TOML in `statusline.md` are examples, not
  links), and names where a failing link *would* have resolved without its leading `../`.

---

## [Unreleased] — statusline hardening

### Added

- **Extra-usage credit consumption on the enhanced statusline (#129), opt-in.** `rate_limits`
  covers the 5-hour and 7-day windows and says nothing about credits — the spend that accrues
  once a plan's included usage is exhausted. Nothing else reported it either: ccusage prices
  tokens at API list rates against a subscription profile, which is not the credit balance and
  reads reassuringly low while credits drain. Set `show_extra_usage = true` for
  `💳 ██░░░░░░░░ 23% €34.10/€150.00`.

  It is **off by default**, because it is the only part of the statusline that leaves the machine
  or reads a credential. Credential resolution (`CLAUDE_CODE_OAUTH_TOKEN`,
  `~/.claude/.credentials.json`, the system keychain) happens on the fetch path only — a render
  served from cache touches none of the three. That ordering is load-bearing rather than tidy:
  `security find-generic-password` can raise an access dialog, and Claude Code waits on the
  statusline synchronously, so a credential read per render would be a hung prompt rather than a
  slow one. Keychain lookups are bounded to 2s by the new `tcs_bounded` (which emulates
  `timeout(1)`, absent from stock macOS), the fetch to 5s; a failure backs off for one
  `usage_cache_ttl`; the last good reading is served for up to 24h; the token reaches curl through
  a config file on stdin rather than argv, and is charset-checked first; concurrent sessions share
  one in-flight fetch.

  **The currency is read, not assumed.** Verifying against a live account found
  `extra_usage.utilization` returning `null` while a parallel `spend` object carried the real
  `percent`, a `currency` and a per-amount `exponent` — and that account bills in EUR. `spend` is
  therefore read first and `extra_usage` is the fallback. The endpoint is undocumented: every
  field is guarded and the segment being absent is unremarkable.

### Changed

- **The payload is read in one `jq` pass (#130).** The enhanced variant spawned eight
  `echo | jq` per render, on a path the client waits for synchronously. One `@tsv` pass replaces
  them. Every field carries a `-` sentinel: without it an absent field collapses to nothing, the
  positional read slides by one, and every value after it is silently wrong — a missing model
  name would arrive as the directory.

### Fixed

- **Caches no longer sit as loose files in a world-writable directory (#131).** They were named
  `/tmp/tcs-statusline-<kind>-<cksum of repo path>` — a predictable name anyone sharing the
  machine can pre-create as a symlink and have the statusline write through. They now live in a
  per-uid directory created `mode 700`, preferring `XDG_RUNTIME_DIR`, checked for symlink and
  ownership before every use. When that check fails, caching is switched off rather than
  redirected. The daily cleanup is scoped to that directory instead of globbing all of `/tmp`.
- **The standard variant rendered `null` for missing fields.** No `//` fallbacks meant a payload
  without `.model` displayed `🤖 null`, and a missing `context_window_size` silently removed the
  context bar entirely. Each field now has a fallback.

---

## [Unreleased] — statusline

### Changed

- **The budget bar reads `rate_limits` from the statusline payload (#118).** That is the
  server's own subscription usage — the same figures `/usage` reports — so it needs no plan
  constant, no `bun x ccusage` subprocess per cache window, no 5s timeout to stall on, and no
  ever-growing `~/.bun/install/cache`. The ccusage token bar stays as the fallback. Both the
  5-hour and 7-day windows are shown, with a countdown derived from `resets_at`.
- **No dollar figure beside the rate-limit bar.** `cost` is not part of the statusline payload
  contract — verified against the schema Claude Code ships in its own statusline authoring
  instructions, through 2.1.252. The enhanced variant had been reading `.cost.total_cost_usd`
  and rendering a permanent `$0.00`; it now reads the field as empty and prints nothing when it
  is absent, so a real value lights up if the key ever appears.

### Fixed

- **ccusage was still being fetched even when `rate_limits` supplied the bar.** The loader ran
  unconditionally before rendering, so preferring `rate_limits` stopped *using* the result
  without stopping the `bun x ccusage` spawn, the up-to-5s timeout stall, or the growth of
  `~/.bun/install/cache`. It now runs only when the fallback bar will actually be drawn.
- **The documented config path did not exist.** Script headers, `--help` output and the example
  TOML all named `~/.config/the-agentic-startup/`, while the code reads
  `~/.config/the-custom-startup/` — so a config placed as documented was silently ignored.
- **The bar emitted invalid UTF-8.** It was built with `printf "%Ns" | tr ' ' '█'`, and `tr`
  maps byte to byte while `█` is three bytes (`e2 96 88`) — so a "full" bar was ten bare `e2`
  bytes, rendering as replacement glyphs in every terminal. Built by appending whole characters
  now.
- **The bar is clamped to ten cells.** One cell per 10% with no upper bound meant a value above
  100 — documented as possible for `spend_limit` — drew a wider bar and broke the fixed-width
  layout. The drawn value is clamped; the true percentage is still reported next to it.
- **The bar accepts fractional percentages.** `rate_limits` reports floats, and the integer
  comparison against the warn/danger thresholds could not take them.
- **`awk`'s output honours `LC_NUMERIC` even though its parsing does not.** The remaining
  unguarded call in the standard variant rendered `$12,50` in a comma-decimal locale. All
  currency formatting now runs under `LC_ALL=C`.

---

## [Unreleased] — spec-013

### Added

- **rule-enforcer skill** (`plugins/tcs-helper/skills/rule-enforcer/`) — user-invocable triage skill for converting recurrence rules into concrete enforcement mechanisms via a 4-question workflow (Q1: scope, Q2: durable-state?, Q3: automation type, Q4: decision gate). Routes to CI workflows, git hooks, Claude PostToolUse hooks, or memory capture.
- **intercept-rule-recurrence hook** (`plugins/tcs-helper/scripts/intercept_rule_recurrence.py`) — UserPromptSubmit hook that watches prompts for recurrence trigger phrases (English: "always", "every", "remember to"; German: "immer", "jedes Mal", "erinnern") and suggests `/rule-enforcer` when detected.
- **Mechanism matrix** (`plugins/tcs-helper/skills/rule-enforcer/reference/mechanism-matrix.md`) — 7 × 3 decision matrix (scope × automation-type × mechanism) documenting 21 (Q3, Q4) → mechanism routes (CI, pre-push, PostToolUse, memory).
- **3 session-violation fixtures** (`tests/fixtures/`) documenting motivating rule violations from 2026-04 → 05-21: (a) forgot to bump marketplace.json after plugin changes (PR #29), (b) forgot to update CHANGELOG/README after shipping a feature, (c) forgot to run skill-author after editing skills.

### Context

This spec was motivated by a pattern of session violations. Recurring mental load of remembering to (1) bump marketplace.json on plugin edits, (2) update CHANGELOG + README after shipping, (3) run skill-author post-edit, led to the rule-enforcer: a single triage entry point that routes recurrence rules to durable enforcement mechanisms rather than relying on ad-hoc memory.

---

## [4.3.0] - 2026-05-21

### Added

- **`tcs-workflow:xdd-meta` Finalize step (PR #27)** — `xdd-meta` skill gained Step 5 "Finalize" with a new `Implemented` phase enum and verb-dispatch entry point. Closes the spec README atomically when implementation completes (sets `Current Phase` to `Implemented`, appends a shipping note to the Decisions Log). Idempotent — safe to call on an already-finalized spec.
- **`tcs-workflow:implement` Step 7 auto-closes spec (PR #27)** — `implement` now invokes `xdd-meta finalize <specId>` before the commit/PR prompt. Fixes the bug where shipped specs stayed stuck on `Ready (implement-ready)` because no workflow step transitioned the spec-level README.
- **Auto-bump CI workflow** (`.github/workflows/auto-bump-versions.yml`, PR #29) — patch-bumps `plugins/<X>/.claude-plugin/plugin.json` and `.claude-plugin/marketplace.json` on push to `main` whenever plugin code changes without a matching manifest bump. Plugin-aware, no-op when nothing under `plugins/` changed, escape hatch for manual minor/major bumps (CI sees the diff and skips). `[skip ci]` in commit message prevents recursive trigger. Bash 3.2 + python3 helper at `scripts/ci/auto-bump-versions.sh`.

### Fixed

- 9 of 12 specs (005–011) were stuck on `Ready` despite shipping (PR #30 retroactive close-out). The Finalize step prevents recurrence; this fixed the existing stale spec READMEs in one batch.

### Internal

- `plugins/tcs-workflow/.claude-plugin/plugin.json`: `4.2.0 → 4.3.0` (PR #28 catch-up for PR #27).
- `.claude-plugin/marketplace.json` `metadata.version`: `4.2.1 → 4.3.0`.

---

## [4.0.0] - 2026-03-28

> For full history see `git log`.

### Breaking Changes

- **Plugin renamed: `tcs-start` → `tcs-workflow`** — upgraders must reinstall the core workflow plugin under its new name. Any references to `tcs-start:*` in project CLAUDE.md files or scripts must be updated to `tcs-workflow:*`.

### Added

- **`tcs-patterns` plugin** (v1.1.0, optional) — 17 domain pattern skills, install only what your stack needs:
  - Architecture: `ddd`, `hexagonal`, `functional`, `event-driven`
  - API & Types: `api-design`, `typescript-strict`
  - Testing: `testing`, `mutation-testing`, `frontend-testing`, `react-testing`, `test-design-reviewer`
  - Platforms: `node-service`, `python-project`, `go-idiomatic`
  - DevOps: `twelve-factor`
  - Integrations: `mcp-server`, `obsidian-plugin`
  - All 17 skills include `reference/` files with extended protocols (v1.1.0)
- **XDD workflow skills** (6 new skills in `tcs-workflow`):
  - `xdd` — spec-driven development entry point
  - `xdd-meta` — spec metadata management
  - `xdd-prd` — Product Requirements Document generation
  - `xdd-sdd` — Solution Design Document generation
  - `xdd-plan` — execution plan generation
  - `xdd-tdd` — Test-Driven Development integration
- **`tcs-team` v3.3.0** — new `record-decision` agent for capturing architectural decisions

### Changed

- **Documentation restructured** — flat `docs/` reorganized into 4-subdirectory information architecture:
  - `getting-started/` — installation and quickstart
  - `reference/` — skills, agents, plugins, commands
  - `guides/` — workflow and multi-AI guides
  - `about/` — philosophy, principles, changelog

---

## [3.2.3] - 2026-03-23

### Changed
- `find-agents.sh` moved from `scripts/` into `skills/skill-author/` — co-located with the skill that uses it
- Cache directory path format corrected to `marketplace/plugin/version/` throughout all docs and references
- `AGENTS.md` repo structure updated with correct `tcs-start`/`tcs-team`/`tcs-helper` plugin names

### Fixed
- Removed incorrect `get-specs-dir.sh` reference from `tcs-helper` README and `docs/plugins.md` — that script belongs to `tcs-start`/`tcs-team`, not the helper plugin
- `find-agents.sh` header comment updated to reflect 3-segment cache path (`marketplace/plugin/version/`)

### Docs
- `tcs-helper` plugin added to root README plugins section and `docs/installation.md`
- `docs/output-styles.md` cache path examples now include version segment

---

## [3.2.2] - 2026-03-23

> **Note:** This is the initial release of the MMoMM-org fork of [rsmdt/the-startup](https://github.com/rsmdt/the-startup). All entries below are additions on top of the upstream 3.2.x baseline.

### Added
- **Plugin rename** — `start` → `tcs-start`, `team` → `tcs-team` for marketplace namespacing
- **`tcs-helper` plugin** (optional) — skill authoring tools for plugin developers
  - `skill-author` skill: create, audit, and convert Claude Code skills with PICS structure, duplicate detection, model selection, agent discovery, and deployment verification
  - `find-agents.sh`: discovers all installed agents across `~/.claude/agents/` and plugin caches
- **Self-announcement** — all skills and agents now identify themselves at activation (`Active skill: …` / `Active agent: …`)
- **Configurable specs directory** — `get-specs-dir.sh` reads `.claude/startup.toml` (local or global) and falls back through standard path chain
- **Local clone install** — `install.sh` can install directly from a local repo clone without requiring a published marketplace release
- **Docs expansion** — `docs/concepts.md`, `docs/installation.md`, `docs/plugins.md` added; README restructured

### Changed
- All hardcoded `.start/specs` paths replaced with configurable references via `startup.toml`

---

## [3.2.1] - 2026-03-16

> Initial fork from [rsmdt/the-startup](https://github.com/rsmdt/the-startup) as MMoMM-org/the-custom-startup.

### Added
- **Interactive install wizard** (`install.sh`) — guided setup for install target (global / repo / custom), plugin selection, output style, statusline, multi-AI templates, and startup config; confirmation summary before writing anything
- **Interactive uninstall wizard** (`uninstall.sh`) — mirrors install choices, removes only what was installed
- **3 statusline variants**:
  - Standard — single-line git branch + token usage
  - Enhanced — adds live token budget bar (requires `ccusage`)
  - Starship bridge — integrates with Starship prompt
  - All configured via `statusline.toml`
- **Multi-AI workflow** — `export-spec.sh` and `import-spec.sh` scripts; prompt templates for Claude.ai and Perplexity; `docs/multi-ai-workflow.md` guide
- **Startup configuration** — `.claude/startup.toml` for specs directory and other project settings
- **Script naming convention** — all statusline scripts share `the-custom-startup-*` prefix
- **Bash 3.2 compatibility** — `case`-based lookup functions replace `declare -A` associative arrays (macOS default shell)

### Changed
- Branding updated to `the-custom-startup` / `MMoMM-org`
- README restructured with docs/ directory and full workflow documentation

---

## [2.0.0] - 2025-10-12

### Changed
- **BREAKING:** Complete migration from npm CLI package to Claude Code plugin architecture
- Installation now uses `/plugin install` instead of `npx the-agentic-startup install`
- Removed Ink-based TUI installer (no longer needed with plugin system)
- Simplified installation process - one command installs everything

### Added
- **Hooks System**: SessionStart and UserPromptSubmit hooks
  - Welcome banner on first plugin session
  - Git branch statusline integration
- **Plugin Manifest**: `.claude-plugin/plugin.json` for plugin discovery
- **Scripts Directory**: `scripts/spec.sh` for spec generation
- **Spec Command**: `/s:spec` for creating numbered specification directories
- Auto-incrementing spec IDs (001, 002, 003...)
- TOML output format for spec metadata reading
- Template generation support via `--add` flag

### Improved
- **File References**: Commands now use @ notation (`@rules/agent-delegation.md`) instead of placeholders
- **Component Discovery**: All components (agents, commands, hooks) auto-discovered by Claude Code
- **Directory Structure**: Flattened structure with all components at repository root
- **Documentation**: Updated README for plugin installation and usage
- **Agent Access**: All 50 agents immediately available after installation

### Removed
- npm package installation workflow
- Interactive TUI installer (Ink components)
- Lock file management system
- Settings.json merger and backup/restore
- CLI-specific source code (`src/cli/`, `src/ui/`, `src/core/installer/`)
- Build-time placeholder replacement

### Technical
- Plugin structure follows official Claude Code specifications
- Hooks use `${CLAUDE_PLUGIN_ROOT}` for script paths
- Commands use @ notation for runtime file references
- No build step required - files used as committed to Git
- Cross-platform statusline support (bash/PowerShell)

### Migration Guide

**From 1.x (npm) to 2.x (plugin):**

1. Uninstall npm package:
   ```bash
   npx the-agentic-startup uninstall
   npm uninstall -g the-agentic-startup
   ```

2. Install plugin:
   ```bash
   /plugin install irudiperera/the-startup
   ```

3. Output style (manual installation):
   - Copy `assets/claude/output-styles/the-startup.md` to `~/.claude/output-styles/`
   - Activate: `/settings add "outputStyle": "the-startup"`

**What stays the same:**
- All 50 agents work identically
- All slash commands work identically
- Specification workflow unchanged
- Documentation structure unchanged
- Agent delegation rules unchanged

**What's better:**
- Simpler installation (one command)
- Automatic updates via plugin system
- Welcome banner on first use
- Git statusline integration

## [1.0.0] - 2025-09-13

### Added
- Initial release as npm CLI package
- Interactive installation via Ink-based TUI
- 50 specialized agents across 9 professional roles
- 5 slash commands: `/s:specify`, `/s:analyze`, `/s:implement`, `/s:refactor`, `/s:init`
- The Startup output style
- Statusline integration (manual configuration)
- Agent delegation rules and cycle patterns
- Template system for PRD, SDD, PLAN, DOR, DOD, TASK-DOD
- Lock file system for tracking installed components
- Settings.json deep merge with backup/restore
- Rollback mechanism for failed installations
- Component selection during installation
- Cross-platform support (macOS, Linux, Windows)

### Technical
- Built with TypeScript
- CLI using Commander.js
- TUI using Ink (React for CLI)
- Published to npm registry
- Installable via `npx` or `npm install -g`

---

[4.0.0]: https://github.com/MMoMM-org/the-custom-startup/compare/v3.2.3...v4.0.0
[3.2.3]: https://github.com/MMoMM-org/the-custom-startup/compare/v3.2.2...v3.2.3
[3.2.2]: https://github.com/MMoMM-org/the-custom-startup/compare/v3.2.1...v3.2.2
[3.2.1]: https://github.com/MMoMM-org/the-custom-startup/releases/tag/v3.2.1
[2.0.0]: https://github.com/irudiperera/the-startup/compare/v1.0.0...v2.0.0
[1.0.0]: https://github.com/irudiperera/the-startup/releases/tag/v1.0.0
