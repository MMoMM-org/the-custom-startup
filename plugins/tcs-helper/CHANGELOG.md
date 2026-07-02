# Changelog

## [4.3.0] - 2026-07-02

### Added

- **`rule-enforcer` batch/extraction mode — sweep `CLAUDE.md` + memory files and mechanize the enforceable rules in one pass.** The skill now has two entry modes. The existing interactive flow (describe one rule → 4-question triage → hand-off) is unchanged; a new batch mode is reached via `/rule-enforcer --scan` (or `--from-file <path>`). Batch mode scans the repo+project rule sources (root `CLAUDE.md`, nested `**/CLAUDE.md`, `docs/ai/memory/*.md`, transitive `@`-imports; `~/.claude/` global set is opt-in via `--scope global`), extracts the deterministically-enforceable rules, classifies each non-interactively against the existing `mechanism-matrix.md` (which stays the single source of truth), deduplicates against already-installed `tcs-git-helpers` hooks, and presents **one consolidated proposal table** plus a "left as guidance" list for judgment-only rules. A single confirm then hands each accepted rule to the existing author skills — no new writer, the Step 8 hand-off (and its slug-validation gates) is reused verbatim.
  - **Design:** Q1 (recurrence) is skipped and Q2/Q3/Q4 are inferred, documented as a batch-only exception in `docs/XDD/adr/0001`. Inspired by the aihero.dev "turn your CLAUDE.md into hooks" prompt, generalized across the full mechanism matrix (7 intervention points + CI + pre-push) with dedup and a single-confirm UX.
  - **New reference files:** `scan-sources.md` (source set + `@`-import policy + exclusions), `extraction-heuristics.md` (enforceable-vs-judgment filter, Q3 bucket cues, Q4 defaults, and the 7 canonical Q3 bare labels), `installed-enforcement-catalog.md` (dedup hint layer; live `.githooks/` + `hooks.json` inspection is authoritative).
  - **Safety:** slug-validation gate now also guards attacker-influenced scanned text; `--from-file` paths are confined (no `..`, no out-of-repo absolutes); personal `~/.claude/` content is paraphrased, never pasted into committed artifacts.
  - **Tests:** `test_batch_q3_labels.sh` (label↔matrix-heading drift guard), `test_batch_parity.sh` (batch inference == interactive mechanism, matrix read at runtime), `test_batch_security.sh` (slug gate + path confinement + doc-contract). All green; interactive self-tests unchanged.
- **`memory-claude-md-optimize` now points at batch mode.** When the optimizer detects `always/never/must` directives that look mechanically enforceable, it counts them and its report suggests running `/rule-enforcer --scan` after the optimization applies — a one-directional pointer (no back-call), so the optimizer relocates content and rule-enforcer mechanizes it, each authoritative on its own domain.

## [4.2.0] - 2026-06-30

### Added

- **`TCS Dark` theme, shipped natively via the plugin `themes/` directory.** Claude Code loads custom themes from each enabled plugin's `themes/<slug>.json` (auto-discovered, no `plugin.json` entry needed) in addition to `~/.claude/themes/`, since v2.1.118. Installing `tcs-helper` now adds **TCS Dark** to every user's `/theme` picker, and updates propagate via `/plugin marketplace update` — no per-machine file copying.
  - **What it is:** `base: "dark"` with four `overrides` — `claude: #0a84ff` (Apple blue accent, replacing the default warm clay/orange used for the response bullet, spinner, and "Claude" branding), `success: #34c759`, `error: #ff3b30`, `warning: #ff9f0a` (Apple system green/red/orange). Background, text, and syntax highlighting inherit unchanged from the dark base.
  - **Discovery:** verified against the installed binary (v2.1.195) — plugin theme loading confirmed (`join(plugin, "themes")` iteration, `themes` registered as a plugin component), so distribution no longer depends on the Docker-home template mechanism.
  - **Note:** a newly added theme file appears in the `/theme` picker only after a Claude Code **restart** (the theme index is built at startup); editing an already-loaded theme hot-reloads into the active session.

## [4.1.4] - 2026-06-03

### Fixed

- **`doc-product` default persona: removed a self-referential question that produced spurious `partial` findings.** The `config-explorer` persona's non-required `setting-impact` question read *"For that same setting, what happens if I leave it at its default?"* — referring back to the setting chosen in the preceding `setting-purpose` question. But the review harness runs every `persona × question` tuple as an **independent, stateless** `claude -p` call (the reader is explicitly told it has no context beyond the document corpus and never sees another question or its answer). So *"that same setting"* had no antecedent at runtime: the reader guessed which setting was meant and hedged, yielding a `partial` regardless of documentation quality — a false gap that was a persona artifact, not a doc problem. The question now re-establishes its subject independently (*"Pick the most prominent configuration option in the document. If you leave it at its default value, what happens?"*). Added a **self-contained-question** authoring rule to the persona file's Usage Notes so overrides and future questions don't reintroduce cross-question references.

## [4.1.3] - 2026-06-03

### Fixed

- **`doc-product` review mode no longer reports a vacuous `PASS` on Linux.** On systems where `/usr/bin/awk` is **mawk** (Debian/Ubuntu default), the persona parser in `scripts/lib-personas.sh` matched nothing: every indentation pattern used POSIX `{n}` interval regexes (`[[:space:]]{2}`, `{6}`, …), which mawk silently ignores. The work plan came out empty and `scripts/run-review.sh` emitted `{"outcome":"PASS","pages_tested":[],"tuples":[]}` with exit 0 — a dangerous false green where authors believed their docs passed a reader test that never ran. (macOS One True AWK supports intervals, so the bug never reproduced locally.) Three-part fix:
  - **Zero-coverage guard (`run-review.sh`):** an unfiltered run (`--page`/`--since` absent) that produces an empty work plan now exits `2` with a loud error instead of `PASS`. A zero-coverage run can never be a silent pass again.
  - **mawk-portable parser (`lib-personas.sh`):** all 44 `[[:space:]]{n}` interval patterns replaced with literal-space anchors (`/^  -/`, `/^      /`), since YAML indentation is fixed-width. Behaviour is identical on One True AWK; now also correct on mawk.
  - **awk-capability prereq probe (`run-review.sh`):** a functional self-test parses the bundled persona set before any work; if the local awk cannot parse it, the run fails fast (exit 2) with an actionable message rather than proceeding to a zero-coverage run.
  - Regression tests added: static interval-free guard (`lib-personas.test.sh` S5, with negative control), zero-coverage refusal (`run-review.test.sh` S8), and broken-awk prereq refusal (S9). `run-review.sh` exit code `2` is now documented in `modes/review.md`.

## [4.1.0] - 2026-05-11

### Added

- **`context-bridge` skill + `SessionStart` hook integration.** Bridges session continuity across `/clear` and `/compact` resets.
  - **Skill (`tcs-helper:context-bridge`)** — invoked by the user before running `/clear` or `/compact`. Introspects current session state (open TODOs, branch, in-flight specs under `docs/XDD/specs/`, recently active files, recent decisions, next steps), classifies whether `/clear` or `/compact` better fits the planned next work, and writes a structured Markdown checkpoint to `.claude/.session-checkpoint.md` (repo-local, gitignored). The skill announces the recommended slash command but does not invoke it — the user runs it.
  - **Hook (`scripts/session_start_context_bridge.py`)** — registered as a second `SessionStart` handler alongside the existing `session_start_reminder.py`. Fires after every session start; acts only when `source` is `clear` or `compact`. Reads the checkpoint, prints it to stdout (Claude Code injects it as additional context for the new session's first response), then renames the file to `.session-checkpoint.consumed-<timestamp>.md` so it cannot be re-injected on subsequent session starts. Silent no-op when no checkpoint exists or when source is `startup`/`resume`.
  - **Why:** large multi-turn sessions accumulate noise that compaction can mask, and `/clear` discards everything — losing the user's place. The bridge lets the user reset context aggressively without losing the thread.
  - **Discovery:** verified against the official Claude Code hooks reference (https://code.claude.com/docs/en/hooks.md) — `SessionStart` payload includes `source ∈ {startup, resume, clear, compact}`, and stdout from the hook is injected as additional context for the new session.

## [4.0.0] - 2026-05-11

### Changed (BREAKING)

- **`setup` → `memory-setup` rename.** The skill that provisions the memory bank (`docs/ai/memory/` + CLAUDE.md hierarchy) is renamed for two reasons:
  - It collided with `tcs-git-helpers:setup` (bare name `setup` in the `/` menu was ambiguous).
  - The new name slots into the existing `memory-*` skill family (`memory-add`, `memory-cleanup`, `memory-promote`, `memory-sync`, `memory-claude-md-optimize`).

  Source directory renamed (`plugins/tcs-helper/skills/setup/` → `skills/memory-setup/`). Frontmatter `name:` field, persona announcement string, and the two consumer templates (`templates/claude-root.md`, `templates/stacks/generic.md`) updated to reference the new name.

  **User-visible impact:** anyone who scripted `/tcs-helper:setup` must update to `/tcs-helper:memory-setup`. The skill's behaviour, output, and templates are unchanged — name only.

## [3.5.0] - 2026-05-07

### Added

- **`doc-product`: root README `## Documentation` section management** — `plan` and `write` modes now refresh a `## Documentation` section in the consumer repo's root `README.md` via the new shared script `scripts/update-readme-docs-section.sh`. Closes the discoverability gap dogfood feedback identified — visitors landing on a project's GitHub README now see a single top-level entry into the docs tree instead of having to track down scattered in-flow links.

  **Behaviour:**
  - Section is delimited by HTML marker comments (`<!-- doc-product:documentation:start -->` / `<!-- doc-product:documentation:end -->`) so subsequent runs replace the block content idempotently without touching surrounding README content.
  - Hand-written `## Documentation` sections **without** markers are detected and **left alone** — the script emits a warning suggesting the author wrap their section in markers if they want auto-refresh.
  - Insertion: before `## License` if present, otherwise appended.
  - Page ordering: canonical (`installation`, `setup`, `configuration`, `usage`, `template-syntax`, `instructions-json`, `troubleshooting`, `faq`) then remaining pages alphabetically.
  - Excluded: `README.md` (in-tree index), `CLAUDE.md`, `AGENTS.md`, `CONSTITUTION.md` — AI/project metadata, not user-facing pages.
  - Bullet text: H1 page title + (optional) one-sentence summary extracted from a `> blockquote` immediately following the H1. No blockquote → bullet is just the title link.
  - Missing root README → notice + skip (does **not** create one).
  - In-flow `[…](docs/foo.md)` references in surrounding prose are **untouched** — only the marker block and the section heading are managed.

  Wired into `plan` Step 7 (Final Report renumbered to Step 8) and `write` Step 10 (Final Report renumbered to Step 11). 33 new tests in `tests/update-readme-docs-section.test.sh` covering INSERT / UPDATE / APPEND / WARN / no-README / no-docs paths plus idempotency, dry-run, ordering, and bad-argument handling. Total doc-product suite: 404 passing (was 371).

## [3.4.2] - 2026-05-07

### Changed

- **`doc-product` SKILL.md: enriched mode-selection menu** — when `/doc-product` is invoked without a mode (or with an unrecognised mode), the receptionist's `AskUserQuestion` previously listed only bare option labels (`plan / write / extract / review`). Users had to read the mode files to know what each one did. The Mode menu is now a documented table under `Workflow / 1. Parse Mode`, with concrete one-line descriptions per mode plus the intended `plan → write → extract → review` flow. The receptionist pattern is preserved — descriptors are user-facing data, not mode logic.

### Fixed

- **`doc-product` review mode: `claude -p --output-format json` wrapper unwrapping** — `scripts/reader-test.sh` ran `jq -e '.found'` against the outer wrapper object instead of the nested model payload. `claude -p --output-format json` returns `{"type":"result","subtype":"success","result":"<inner-JSON-as-string>",...}` where the model's `.found`/`.answer`/etc. live inside `.result` as a stringified payload. The pre-fix script saw `.found` missing on the wrapper and routed every tuple through the `unparseable_response` branch — a uniform failure across every `/doc-product review` run against real `claude`. Fix: unwrap via `try (.result | fromjson) catch empty`, validate the inner has `.found`, and emit the inner JSON. The existing test stubs were also updated to emit the realistic wrapper shape (they previously emitted flat JSON, which masked the bug). New scenario S8 covers the wrapper-without-`.result` subtype path (e.g. `error_max_turns`).

### Changed (breaking — slash command rename)

- **3.4.1 rename reverted; `docs` skill renamed to `claude-docs` instead** — the 3.4.1 rename targeted the wrong skill. The `claude-docs` name belongs on the Claude-Code-documentation fetcher (formerly `/docs`), not on the user-facing-doc-authoring skill. Two corrective renames:
  1. **`claude-docs` (the doc-authoring skill from 3.4.1) → `doc-product`** — restores the spec-010 name. The skill directory, `name:` frontmatter, active-skill announcement (`tcs-helper:claude-docs` → `tcs-helper:doc-product`), all `/claude-docs {plan|write|extract|review}` invocations across mode files, gap-report template, personas-default header, `lib-personas.sh` comment, and `write-mode.test.sh` assertions are reverted to `doc-product`.
  2. **`docs` (the doc fetcher) → `claude-docs`** — the slot is now occupied by the skill that actually fetches Claude Code documentation. Updates: skill directory (`plugins/tcs-helper/skills/docs/` → `plugins/tcs-helper/skills/claude-docs/`), `name:` frontmatter, `tcs-helper:docs` → `tcs-helper:claude-docs`, and the `/docs {topic} --refresh` example in the cache header → `/claude-docs {topic} --refresh`.

  The cache output directory `docs/ai/external/claude/` is **unchanged**. Spec ID `010-doc-product-skill` remains as a historical reference. Previous `/claude-docs {plan|write|extract|review}` invocation is gone — use `/doc-product {plan|write|extract|review}`. Previous `/docs` is gone — use `/claude-docs`.

## [3.4.1] - 2026-05-07

### Changed (breaking — slash command rename)

- **Skill renamed `doc-product` → `claude-docs`** — initial dogfood feedback from Marcus: the v1 slash command `/doc-product` was unintuitive in TCS / MiYo contexts. Renamed throughout: skill directory (`plugins/tcs-helper/skills/doc-product/` → `plugins/tcs-helper/skills/claude-docs/`), `name:` frontmatter field, active-skill announcement (`tcs-helper:doc-product` → `tcs-helper:claude-docs`), all `/doc-product {plan|write|extract|review}` slash command invocations across the four mode files, the gap-report template, the personas-default header, the `lib-personas.sh` reference, the `write-mode.test.sh` test assertions, and "the doc-product skill" prose in error messages and template intros. Spec ID `010-doc-product-skill` preserved as a historical reference (the spec name is stable; only the skill identity changed). The output directory `docs/` is **unchanged** — the skill still writes user-facing documentation to a target repo's `docs/` tree.

  All 369 test assertions across 13 test files green. The previous `/doc-product` invocation is no longer available; users invoke `/claude-docs {plan|write|extract|review}` instead.

## [3.4.0] - 2026-05-07

### Added

- **`doc-product` skill — Phases 1–4 functional** — Mode-router skill (`/doc-product {plan|write|extract|review}`) for authoring and reviewing user-facing documentation. Implements all four modes per spec-010: `plan` (repo analysis + `docs/` skeleton), `write` (section-by-section drafting via discover → document → review), `extract` (settings → configuration page from TS / JSON Schema / Pydantic sources), `review` (persona-driven reader testing via `claude -p` subprocess). Includes built-in persona library, four skeleton templates, configuration + gap-report templates, and Bash parsers per source type. Phase 5 (dogfood) outstanding.

## [3.3.0] - 2026-05-06

### Added

- **`doc-product` skill scaffold (Phase 1 of spec-010)** — Skill skeleton with mode-router SKILL.md and TODO stubs for the four mode files. Routes `/doc-product {plan|write|extract|review}` via case-insensitive leading-token match with AskUserQuestion fallback. Mode bodies progressively disclosed.

## [3.2.0] - 2026-04-25

### Changed

- **`agent-author` conventions overhauled** — re-grounded in `rsmdt/the-startup` `docs/PRINCIPLES.md` (April 2026) and the actual ICMDA layout used by all `tcs-team` agents. Replaces the earlier Perplexity-based PICS draft. Updates: conventions.md (ICMDA + frontmatter schema + tool/model/color tables), description-patterns.md (first-50-char rule, third-person, `<example>` blocks), output-formats.md (typed-table per archetype), anti-patterns.md (PRINCIPLES § 4.5 list), canonical-agent.md (full ICMDA reviewer example), audit-output.md (ICMDA-aware audit checklist), SKILL.md (Mechanism Check as Step 1).
- **`skill-author` Mechanism Check** — symmetric Step 1 added before mode selection. Walks the load-bearing question from PRINCIPLES § 5.2 ("should output remain visible in parent conversation?"). Recommends handoff to `agent-author` if a subagent is the right mechanism instead of a skill.

### Added

- **Shared `decision-tree.md`** — identical content in both `agent-author/reference/` and `skill-author/reference/`. Sourced from PRINCIPLES § 5.2 sequential decision tree + worked examples + common confusions. Sync header in both files.
- **`agent-author/evals/pressure-scenarios.md`** — three persisted pressure-test scenarios (lazy spec, wrong mechanism, lazy audit) with expected behaviors, failure modes to watch, and 2026-04-25 baseline PASS verdicts. Per PRINCIPLES § 2.7 evaluation-first authoring; re-run after any non-trivial skill change.

## [3.1.0] - 2026-04-25

### Added

- **`agent-author` skill** — Authoring assistant for Claude Code subagents (mirrors `skill-author` for skills). Supports Create / Audit / Modernize modes. Enforces TCS opinions: `sonnet` as default model (rejects `inherit`), action-oriented descriptions with `Use PROACTIVELY`/`MUST BE USED` triggers, minimum tool sets per archetype, and fixed output formats. Includes reference docs (conventions, description-patterns, decision-tree, output-formats, anti-patterns) and annotated examples.

## [3.0.3] - 2026-04-11

### Fixed

- **`post_commit_reminder.py` JSON schema** — The PostToolUse(Bash) hook was emitting `{"hookSpecificOutput": "text"}` (string), which Claude Code rejects with "JSON validation failed". Fixed to emit the required object shape `{"hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext": "text"}}`. Triggered after every `git commit` (non-amend). Tests updated accordingly (17/17 pass).

## [3.0.0] - 2026-03-30

### Breaking Changes

- **Removed `merge_hooks.py`** — Claude Code natively loads `hooks/hooks.json` from enabled plugins. The merge script and its 13 tests are deleted. The `/setup` skill no longer calls it.

### Added

- **CJK correction patterns** — 13 patterns ported from claude-reflect v3.1.0 (Japanese 8, Chinese 3, Korean 2)
- **False positive filtering** — Non-correction phrases ("no problem", "don't worry") are filtered out
- **Code block exclusion** — Correction keywords inside ``` code blocks are ignored
- **Confidence tuning** — Context-aware scoring: short text boost, long text penalty, multi-pattern boost (cap 0.95)
- **Tool error detection** — PostToolUse hook captures persistent tool errors (seen 2+ times), categorized by type (module_not_found, connection_refused, etc.)
- **Cross-category deduplication** — `find_duplicates()` checks all 6 Memory Bank files using Jaccard similarity
- **Semantic AI validation** (optional) — `semantic_detector.py` validates low-confidence items via `claude -p`. Disabled by default; enable by ensuring `TCS_SEMANTIC_VALIDATION` is not `false`.
- **Contradiction detection** — Flags conflicting entries during `/memory-add`, with keyword-based fallback when claude CLI unavailable
- **Test suite expansion** — 31 → 160 tests (5x increase)
- **conftest.py** — Shared pytest fixtures for all test files

### Changed

- **Hook input contract** — Scripts now read `cwd` from JSON stdin instead of `${PWD}` CLI argument. Fallback to `os.getcwd()` when `cwd` absent.
- **hooks.json** — Removed `"${PWD}"` from all hook commands
- **detect_learning()** — Refactored into 8-step pipeline with CJK-aware length calculation
- **`/memory-add` skill** — Added tool error auto-routing to troubleshooting.md, cross-category dedup, optional semantic validation, contradiction detection

## [2.1.1] - Previous

- Initial TCS fork of claude-reflect with Memory Bank integration
