# Changelog

All notable changes to The Custom Agentic Startup will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased] — memory

### Added

- **`docs/ai/memory/declined.md` — a journal of what was ruled out, and the condition that reopens
  it.** The memory bank stores what is true now; nothing stored what we decided *not* to do. A
  rejected idea therefore resurfaced weeks later as if fresh and was re-argued from zero by a
  session that never saw the original conversation.

  This session alone produced eight structural declines, and they were scattered across two pull
  request bodies, two issue comments, a changelog entry and `sources.md` — a parallel session would
  have found none of them. The journal is seeded with all eight, each with a `Revisit if` condition,
  so a decline reopens on a stated trigger rather than on forgetting.

  Wired so it fires rather than sitting there: `/memory-add` routes rejection wording to it and is
  told that a decline is not a decision; `docs/ai/CLAUDE.md` says to read it before proposing
  anything structural; it appears in the index, the routing reference, the shipped routing template,
  and `/memory-setup`'s scaffold.

  It sits **outside** the 24 KB bank budget, along with `routing-reference.md` — neither is
  auto-loaded, and a journal pruned to fit a budget deletes exactly the history it exists to keep.
  `/memory-sync` excludes both, with that reasoning recorded, so the bank number keeps tracking the
  always-loaded cost.

  Adapted from [`tonydzi/claude-bible`](https://github.com/tonydzi/claude-bible) (MIT) § 5. Their
  frontmatter precedence scheme was evaluated in the same pass and declined — the first entry the
  journal records about itself.

---

## [Unreleased] — agent authoring

### Added

- **A routing rule for agent memory** (#85), so the fourth store does not become the fragmentation
  `/memory-sync` exists to prevent. The discriminating question: would the main session, another
  agent, or a human reviewing later need this? → Memory Bank. Is it useful only to this one agent,
  built up across repetitions only it witnesses? → agent memory. Almost everything is the first
  case.

  `routing-reference.md` now also records *why* the store exists — what actually reaches a
  subagent is narrower than it looks. The `CLAUDE.md` hierarchy and its `@`-imports arrive in full,
  but `memory.md` links the category files as plain Markdown rather than `@`-imports, so an agent
  must choose to read them; user auto-memory never arrives at all. And a subagent can write to none
  of these layers — what it learns dies with it unless a human notices it in the report and runs
  `/memory-add`. Agent memory is the only write-back channel there is.

  Two hard constraints are stated with it: never on a read-only agent (the field grants unscoped
  `Write`/`Edit` — #144), and never for anything a second party needs.

- **`agent-author` warns that `memory:` silently widens an agent's tool whitelist** (#85). The
  field auto-enables `Read`, `Write` and `Edit`, and the write access is general-purpose rather
  than confined to the memory directory — measured on Claude Code 2.1.252 against a control
  differing in that one line. A reviewer declaring `tools: Read, Grep, Glob` alongside
  `memory: project` can write anywhere while every line a reader would check still says read-only.
  Documented in `conventions.md` § Tool Scoping with the measurement, on the `memory` row of the
  frontmatter table, and as an `anti-patterns.md` entry. Whether this gets scoped upstream is
  tracked in #144.

- **`agent-author` documents five subagent frontmatter fields it was missing** (#85): `effort`,
  `observer`, `observerMessage`, `observeSubagents`, `experimental`. Read out of the shipped schema
  in Claude Code 2.1.252 — the issue had two, a spike had three, and none of the five appear in the
  documentation's own field reference. `observer` gained a section: a read-only background watcher
  spawned on every run of the observed agent, which is not the same thing as the review agents
  `tcs-workflow` dispatches against a finished diff.

- **Agent types are indexed at session start**, so a just-authored agent is not dispatchable in the
  session that created it — `Agent type '<name>' not found`, the same shape as the already-recorded
  plugin cache staleness. A nested `claude -p` run indexes at its own startup and is the workaround.
  Found while spiking #99, and true of agent authoring generally.

### Changed

- **§ Observers is rewritten around what the #99 spike measured**, and the description above it
  ("a read-only background watcher") turned out to be the schema's framing rather than the
  behaviour.

  The mechanism is gated on the environment flag `CLAUDE_CODE_EXPERIMENTAL_OBSERVER_AGENTS`, and
  when it is unset an `observer:` declaration is a **silent no-op** — no spawn, no error, no entry
  in `permission_denials`, no `[agentObserver]` log, because the gate sits upstream of the arming
  code that would log. Four probe runs produced exactly that nothing before the flag was found, and
  the hypothesis those runs supported — that observers cannot supervise a headless run — was wrong.

  With the flag set, three measured behaviours differ from the framing:

  - **"Read-only" describes the digest, not the observer.** An observer with no `tools:` line
    received `Bash, Edit, Read, Write, Skill, ToolSearch, ObserverReport`, does not inherit the
    observed agent's scoping, and used `Bash` to write into the observed agent's workspace. Ship
    every observer with an explicit `tools:` line.
  - **A report to the observed agent is advisory.** It arrives as a mid-run message and the agent
    may refuse it — the probe worker did, on the grounds that an observer message is not user
    consent. On a *fan-out* pairing the routing differs: reports go to the coordinating agent, not
    to the worker.
  - **Delivery races the observed agent.** `Report queued for <agent>` is an acceptance receipt,
    not proof of delivery; a report queued after the observed agent's last turn is never seen.

  Digest shape is now recorded from an observer's own transcript rather than from strings in the
  binary: per-turn `<{agentName}-activity>` blocks carrying assistant text, `<tool-call name="…">`
  with full JSON arguments, and the matching `<tool-result>`.

---

## [Unreleased] — git hooks

### Fixed

- **`pre-push` warned on every push in any repo whose remote is an SSH host alias (#136).** The
  hook has a branch that fails open *silently* for the ordinary case of a repo `gh` cannot map to
  a GitHub host — a non-GitHub remote, or the common multi-account setup using
  `git@github-alias:owner/repo.git`. That branch matched on the string `no GitHub remote`, which
  `gh` has never emitted. What it actually says is "none of the git remotes configured for this
  repository point to a known GitHub host". So the silent branch was unreachable and every push
  printed the catch-all `gh error (exit 1)` warning instead. Pushing always worked — fail-open is
  correct — but a warning that fires on literally every push trains people to ignore hook output,
  which is the part that matters.

  Both wordings are now matched, so a future rewording in either direction stays silent rather
  than becoming noise again. A genuine `gh` failure still warns; the silent branch stays narrow
  on purpose.

  The issue diagnosed a second cause — that `2>/dev/null` discarded the message before it could
  be matched. That was true of 2.2.12 but not of the current hook: `_gh_with_timeout` already
  merges the child's stderr into its own stdout, so the text does arrive. Implementing the
  suggested patch as written would have added a stderr capture that collects nothing and quietly
  re-broken the match.

  **Why it shipped:** the regression test stubbed `gh` emitting the literal string
  `no GitHub remote`, a message `gh` does not produce. It asserted the right behaviour against a
  fabricated wire format and stayed green while production was broken. The stub now carries the
  real text, with the legacy wording kept as a separate case.

---

## [Unreleased] — merge automation

### Added

- **`docs-sync` blocks a pull request that leaves a documentation surface unanswered.** Auto-merge
  is now enabled on the repository, which removes the pause where somebody used to notice the docs
  had not been updated — so the check has to exist or the habit does not.

  The cheaper version of this check would not have worked. #129 *did* change
  `docs/guides/statusline.md`, and its first commit still had no changelog entry, a README
  describing the superseded ccusage bar, and an untouched configurator — which writes its own
  `statusline.toml`, so the new option did not exist at all for anyone setting the statusline up
  through the wizard. "Did any documentation change?" passes on that commit. So `docs-sync` asks
  per surface instead: any change under `scripts/` or `plugins/` needs a `CHANGELOG.md` entry, and
  `.github/docs-map` names, per code glob, the surfaces that must move with it. Both can be waived
  from the pull request body — `Docs: <path> — <reason>`, at least 20 characters — because a waiver
  should cost more than the edit it avoids, and never be silent.

  The map is deliberately small and holds only entries with a demonstrated omission behind them.
  `README.md` is left out on purpose: almost no code change needs it, and a rule that is usually
  wrong gets switched off within a week. It lives in the new pull request template instead.

- **`.github/PULL_REQUEST_TEMPLATE.md`** — the surfaces `docs-sync` deliberately does not enforce,
  as a checklist, plus the waiver syntax.

### Changed

- **Auto-merge is enabled on the repository. The `main` ruleset exists but is `disabled`, so no
  check is required and nothing blocks a merge.** It carries the six contexts — `pytest` and
  `bats` on both runners, `Hook bundle version check`, `docs-sync` — ready to switch on once the
  problem below is solved.

  It was active briefly and had to be suspended. **Required status checks in a ruleset apply to
  direct pushes, not only to merges**, and a freshly created commit has no check runs, so the
  push is rejected:

      remote: error: GH013: Repository rule violations found for refs/heads/main.
      remote: - 6 of 6 required status checks are expected.

  `auto-bump-versions.yml` pushes its version bump straight to `main`, so every merge broke the
  release automation. Its retry loop reports the rejection as *"origin/main moved underneath us"*,
  which reads like a race and hides the cause — read the `remote:` lines, not the summary. The
  first blocked run left `tcs-git-helpers` with a CHANGELOG documenting 2.2.21 against a manifest
  carrying 2.2.20, the inconsistency `check-changelog-version-sync.sh` reports (#93).

  Rulesets cannot be scoped to merges: they evaluate ref updates, and a merge is one. The only
  levers are which branches, and who is exempt. Of the bypass actors this repository accepts,
  only `RepositoryRole: admin` is available — GitHub refuses the GitHub Actions integration
  ("must be part of the ruleset source or owner organization") with no app installation to name
  instead. **A personal access token would not fix this honestly**: it acts as its owner, an
  admin, so the bypass would cover every merge that owner makes — the checks would stop applying
  to the case they exist for, and auto-merge would again have nothing to wait for. A GitHub App
  is the one option that exempts only the bump push. Until then the ruleset stays off, no bypass
  actor is stored (one left behind would silently reopen that hole the moment somebody re-enables
  it), and merges wait on `gh pr checks` rather than on enforcement.

  `strict_required_status_checks_policy` is off in the stored config, so a branch will not have
  to be rebased onto the tip of `main` — that setting turns every parallel pull request into a
  rebase queue and buys little here.

- **`docs-sync` still runs on every pull request and still fails when a surface is unanswered.**
  With the ruleset off it does not *block* the merge, so it is a red job to read rather than a
  gate. That is a weaker guarantee than intended and is worth remembering before relying on it.

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
