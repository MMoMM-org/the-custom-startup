---
title: "doc-product: User-Facing Documentation Co-Authoring Skill"
status: draft
version: "1.0"
---

# Product Requirements Document

## Validation Checklist

### CRITICAL GATES (Must Pass)

- [ ] All required sections are complete
- [ ] No [NEEDS CLARIFICATION] markers remain
- [ ] Problem statement is specific and measurable
- [ ] Every feature has testable acceptance criteria (Gherkin format)
- [ ] No contradictions between sections

### QUALITY CHECKS (Should Pass)

- [ ] Problem is validated by evidence (not assumptions)
- [ ] Context → Problem → Solution flow makes sense
- [ ] Every persona has at least one user journey
- [ ] All MoSCoW categories addressed (Must/Should/Could/Won't)
- [ ] Every metric has corresponding tracking events
- [ ] No feature redundancy (check for duplicates)
- [ ] No technical implementation details included
- [ ] A new team member could understand this PRD

---

## Output Schema

### PRD Status Report

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| specId | string | Yes | Spec identifier (NNN-name format) |
| title | string | Yes | Feature title |
| status | enum: `DRAFT`, `IN_REVIEW`, `COMPLETE` | Yes | Document readiness |
| sections | SectionStatus[] | Yes | Status of each PRD section |
| clarificationsRemaining | number | Yes | Count of `[NEEDS CLARIFICATION]` markers |
| acceptanceCriteria | number | Yes | Total testable acceptance criteria defined |
| openQuestions | string[] | No | Unresolved items requiring stakeholder input |

### SectionStatus

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| name | string | Yes | Section name |
| status | enum: `COMPLETE`, `NEEDS_CLARIFICATION`, `IN_PROGRESS` | Yes | Current state |
| detail | string | No | What clarification is needed or what's in progress |

---

## Product Overview

### Vision
A skill that turns user-facing documentation from an afterthought into a first-class, automatable artifact — so every TCS plugin (and any plugin built with TCS heuristics) ships with a discoverable, navigable, reader-tested `docs/` tree instead of a 200-line README graveyard.

### Problem Statement
Plugin authors today produce user documentation in three failure modes:

1. **Single-README dumping ground** — `miyo-tomo`'s 198-line README is the canonical example: installation, configuration, troubleshooting, examples and edge cases all stacked into one scrolling file. Users can't find what they need; authors can't keep it consistent as features evolve.
2. **Manual config sync rot** — settings interfaces evolve in source code (`src/settings.ts`, `pyproject.toml`, Pydantic models) but the configuration documentation drifts out of sync because there is no automated bridge from source to docs.
3. **Author-blind review** — authors review their own docs from inside their own mental model. They cannot see the gaps a first-time user hits because they already know the answers. There is no automated reader-perspective check.

The consequence: plugin adoption stalls at the documentation barrier, support load on authors increases, and the same "how do I configure X?" question reaches the author repeatedly via every available channel.

`miyo-kado`, after several iterations, demonstrates a better pattern (separated `docs/installation.md`, `docs/configuration.md`, `docs/troubleshooting.md`, etc.) but reaching that state was manual and serial. There is no skill or tooling that helps an author start, iterate, and verify user-facing docs as a coherent workflow.

### Value Proposition
The skill compresses three high-friction documentation tasks into automatable workflow steps:

1. **Skeleton planning** — given a repo, propose a `docs/` tree based on what the project actually is (Obsidian plugin, Python CLI, TCS plugin, …) so the author starts from a working layout rather than a blank directory.
2. **Configuration extraction** — read the source-of-truth (TS interface, JSON Schema, Pydantic model, plugin manifest) and generate the configuration reference automatically, so docs and source can never drift again.
3. **Reader testing as a quality gate** — spawn fresh `claude -p` instances acting as user personas, ask them to perform realistic tasks against the docs alone, and aggregate the gaps into a structured report. This catches blind spots authors cannot catch themselves.

The skill is unique in TCS because it is the first to use **headless Claude (`claude -p`) as a primitive** — exploiting OS-level process isolation for true context-free reader simulation, with no cost or token-budget impact on the parent conversation.

## User Personas

### Primary Persona: TCS Plugin Author
- **Demographics:** Solo developer or small-team lead, intermediate-to-senior technical expertise, comfortable in Markdown and a primary language (TypeScript or Python), often building Obsidian plugins, CLI tools, or TCS plugins themselves. Marcus is the n=1 reference user for v1.
- **Goals:**
  - Ship plugins where new users succeed at installation, configuration, and first-task without reaching out for help.
  - Keep configuration documentation in sync with source automatically.
  - Receive concrete, actionable feedback on documentation gaps — not just a vague "improve the docs" sense.
  - Spend cognitive budget on the actual product, not on documentation scaffolding decisions.
- **Pain Points:**
  - Starting a `docs/` tree from scratch — what pages should even exist?
  - Manual sync between code-level settings and documentation prose.
  - No way to test docs from a non-author point of view; reading one's own doc is unreliable.
  - Existing tools (e.g. typedoc, Sphinx) generate API/code docs, not user-facing prose.

### Secondary Persona: End User of the Plugin (the doc *reader*)
- **Demographics:** Variable — could be a non-developer Obsidian power user, a sysadmin running a Python CLI, or a fellow plugin author integrating with a TCS plugin. Defined here because the skill optimises for *their* successful task completion even though they never invoke the skill themselves.
- **Goals:**
  - Install and configure a plugin without reaching the author.
  - Find configuration semantics and defaults quickly, by topic.
  - Recover from common errors using the troubleshooting page rather than a forum search.
- **Pain Points (currently):**
  - Docs that mix install / config / troubleshooting / FAQ in one scrolling README.
  - Configuration tables that show types but not defaults or "why-it-matters".
  - Troubleshooting sections written from the author's debugging mental model rather than the user's symptom.

## User Journey Maps

### Primary User Journey: Plugin Author Bringing a Repo's Docs to Quality
1. **Awareness:** Author finishes a feature and realises the README has grown unwieldy, or a user asks "where do I find configuration X?". They invoke `/doc-product` (or it auto-triggers from a brainstorm/spec context).
2. **Consideration:** Author runs `plan` mode to see what `docs/` tree the skill proposes, compares to the current state, decides what to keep, what to extract from the README.
3. **Adoption:** Author commits to the proposed skeleton, then runs `extract` mode to auto-generate `configuration.md` from the source settings interface, and `write` mode for the prose pages (installation, troubleshooting, etc.) section by section.
4. **Usage:** Author runs `review` mode (the reader test). The gap report identifies which persona could not complete which task. Author iterates on the affected pages and re-runs `review` until the gap report is clean.
5. **Retention:** As features evolve, author re-runs `extract` (auto-sync of config docs) and `review` (regression detection of doc quality) — both fast enough to integrate into a release checklist or pre-merge hook.

### Secondary User Journey: End User Reaching a Plugin's Docs
The End User persona never invokes the skill, but is the journey the skill optimises for. The doc set must support this path:

1. **Awareness:** User installs the plugin, encounters a question (configuration, error, missing feature) and lands in the repo's `README.md` or `docs/` tree.
2. **Consideration:** Top-level `README.md` orients them ("for installation, see `docs/installation.md`; for configuration, see `docs/configuration.md`") rather than presenting a wall of mixed content.
3. **Adoption:** User navigates to the relevant `docs/<page>.md`, finds the answer in a section whose heading matches their question, without scroll-hunting.
4. **Usage:** User completes the task (install, configure a setting, recover from an error) without leaving the docs.
5. **Retention:** When the user returns later with a new question, the same predictable structure means they know where to look.

A successful `review` mode run by the author = high probability that an End User on this journey reaches step 4 without escalating to support.

### Tertiary User Journey: TCS Workflow Author Adding doc-product as a Quality Gate
A TCS workflow author (Marcus or future contributor) integrates `doc-product:review` as an optional step in `/xdd-plan` or `/implement`, so any feature that reaches "done" must also pass a reader test on the affected docs page before being marked complete. This is a future composition, not part of v1.

---

## Feature Requirements

### Must Have Features

#### Feature 1: `plan` mode — Repo-aware docs/ skeleton proposal
- **User Story:** As a plugin author, I want the skill to analyse my repo and propose a `docs/` tree appropriate for the project type, so I start from a working skeleton instead of a blank directory.
- **Acceptance Criteria (Gherkin Format):**
  - [ ] Given an Obsidian plugin repo (manifest.json present, settings interface in src/), When I invoke `plan` mode, Then the skill proposes a `docs/` tree containing at minimum: installation, configuration, usage, troubleshooting.
  - [ ] Given a Python tool repo (pyproject.toml present), When I invoke `plan` mode, Then the skill proposes the same minimum tree adapted to Python conventions (e.g. install via pip / uv).
  - [ ] Given a TCS plugin repo (plugin.json present), When I invoke `plan` mode, Then the skill proposes a tree that includes a per-component reference (commands, agents, skills) in addition to the minimum.
  - [ ] Given a repo of unknown type (no recognised manifest), When I invoke `plan` mode, Then the skill asks the author for the project type via AskUserQuestion before proposing a skeleton.
  - [ ] Given a repo that already has a `docs/` directory, When I invoke `plan` mode, Then the skill diffs proposed-vs-existing and offers Keep / Replace / Merge per page rather than overwriting silently.
  - [ ] Given the author approves the proposal, When the skill writes the skeleton, Then it creates empty placeholder Markdown files only (no fabricated content), with a TODO header in each.

#### Feature 2: `write` mode — Section-by-section page drafting
- **User Story:** As a plugin author, I want to draft a single doc page through guided dialogue, so I produce a coherent page rather than a wall of text.
- **Acceptance Criteria (Gherkin Format):**
  - [ ] Given an empty `docs/<page>.md` placeholder, When I invoke `write <page>` mode, Then the skill proposes a section structure for that page type (e.g. installation: prerequisites → install command → verify) and confirms with the author before drafting.
  - [ ] Given a confirmed structure, When the skill drafts a section, Then it asks targeted clarifying questions instead of fabricating details (matching the `doc-coauthoring` discover-then-document pattern).
  - [ ] Given a section is drafted, When the author iterates, Then the skill preserves prior approved sections and only redrafts the section under iteration.
  - [ ] Given the author has iterated 3 times on a section without substantive change, When the skill detects this, Then it asks "can anything be removed?" before continuing.

#### Feature 3: `extract` mode — Configuration reference auto-generation
- **User Story:** As a plugin author, I want configuration documentation generated from the source-of-truth settings definition, so docs and source cannot drift.
- **Acceptance Criteria (Gherkin Format):**
  - [ ] Given a TypeScript settings interface (e.g. `interface Settings { … }`), When I invoke `extract` mode, Then the skill produces `docs/configuration.md` containing every field with: name, type, default value, JSDoc comment as description, example value.
  - [ ] Given a JSON Schema file, When I invoke `extract` mode, Then the skill produces the same configuration reference structure.
  - [ ] Given a Pydantic model or dataclass, When I invoke `extract` mode, Then the skill produces the same configuration reference structure adapted to Python conventions.
  - [ ] Given the source settings file changes after extraction, When I re-run `extract` mode, Then the skill diffs the new output against the existing `configuration.md` and surfaces the changes for review rather than overwriting silently.
  - [ ] Given a settings field has no description / JSDoc / docstring, When I invoke `extract` mode, Then the skill marks that field as `[NEEDS DESCRIPTION]` rather than fabricating one.
  - [ ] Given a manifest file (manifest.json, plugin.json, pyproject.toml metadata block) is present alongside the settings source, When I invoke `extract` mode in v1, Then the skill ignores it — manifest-derived metadata (author, version, repository links) is explicitly deferred to v2.

#### Feature 4: `review` mode — Automated reader test (KILLER FEATURE)
- **User Story:** As a plugin author, I want my docs tested against persona-based reader simulations using fresh `claude -p` instances, so I get an objective gap report before users hit the gaps.
- **Acceptance Criteria (Gherkin Format):**
  - [ ] Given a `docs/` directory, When I invoke `review` mode, Then the skill runs each defined persona × question pair against the relevant doc page(s) using `claude -p` with no project context, and aggregates the results into a single gap report.
  - [ ] Given a persona × question pair, When `claude -p` returns its structured response, Then the skill records: `found: yes | partial | no`, the reader's answer, and any items the reader marked as ambiguous or guessed.
  - [ ] Given the gap report contains at least one `found: no` for a persona marked as required (e.g. "first-time-installer"), When the report is presented, Then the doc set is flagged as failing the reader-test gate.
  - [ ] Given the author wants to override default personas, When a project-local `.claude/doc-personas.md` exists, Then the skill uses that file's personas instead of the built-in defaults.
  - [ ] Given the skill is invoked in a non-interactive environment (e.g. CI), When `review` runs, Then it exits with non-zero status if any required persona reports `found: no` on any required question.
  - [ ] Given a persona is marked `required: true` and the persona's required questions are evaluated, When any single required question returns `found: partial` or `found: no`, Then the persona fails and the doc set fails the gate. Strict 100% on required questions is the v1 contract — no configurable percentage thresholds in v1.

### Should Have Features

- **Cross-page consistency check.** When `review` runs, also verify that links between docs pages resolve and that no content is duplicated across pages (e.g. "configuration" appearing in both the README and `configuration.md`).
- **Persona library extensibility.** Default personas live in the skill but can be augmented (not just replaced) by `.claude/doc-personas.md`, so projects can add domain-specific personas (e.g. "migrating-from-tool-X") on top of the defaults.
- **`plan` Mode produces an index README.** The proposed skeleton includes a top-level `docs/README.md` that links to every page, so the docs/ tree is navigable from the start.
- **Diff-aware reader testing.** When `review` is invoked with a `--since <ref>` flag, only pages changed since that ref are tested, making review fast enough for pre-commit / pre-merge use.

### Could Have Features

- **Slash invocation per mode.** Beyond `/doc-product <mode>`, support direct slash commands like `/doc-plan`, `/doc-write`, `/doc-review` for quick access. (Tradeoff: more entries in the `/` menu.)
- **HTML / static-site export.** Generate a static site (e.g. via mdbook or VitePress) from the `docs/` tree as a publishing helper.
- **Tone consistency check.** Detect tone drift between pages (imperative vs passive, formal vs friendly) and surface inconsistencies during `review`.
- **Multilingual reader testing.** Run `review` with personas in multiple languages to surface translation gaps.

### Won't Have (This Phase)

- **API / code reference generation.** This skill is for user-facing prose. API docs from JSDoc / Sphinx are out of scope — those have established tooling (typedoc, Sphinx, etc.).
- **Real human user testing recruitment.** The skill simulates readers via `claude -p`; recruiting actual humans for usability testing is a separate concern.
- **Version-aware doc snapshots.** Tracking docs across multiple plugin versions / branches (versioned doc sites) is out of v1 scope.
- **Automatic publishing to a docs hosting service.** The skill produces files; publishing pipelines (GitHub Pages, ReadTheDocs, etc.) are caller responsibility.
- **Documentation translation.** No machine-translated outputs in v1.

## Detailed Feature Specifications

### Feature: `review` mode — Reader Test Automation (most complex feature)

**Description:** The reader-test workflow spawns isolated `claude -p` processes that act as defined personas reading the docs without any project context. Each persona has one or more required questions (e.g. "How do I install this on macOS?"). The skill collects each persona × question response into a structured record, aggregates into a gap report, and decides pass/fail against per-persona thresholds.

**User Flow:**
1. Author runs `/doc-product review` (optionally with `--page <name>` or `--since <ref>` filters).
2. Skill loads the active persona set (built-in defaults, augmented or replaced by `.claude/doc-personas.md`).
3. Skill resolves which docs pages are in scope (all pages, named page, or changed-since).
4. Skill orchestrates `claude -p` invocations in parallel (one per persona × question pair, per page).
5. Each `claude -p` call receives: the doc page contents only, the persona description, the question, and the structured-output instructions.
6. Skill collects all responses, aggregates by persona, and produces a Markdown gap report **rendered inline in the parent conversation** (not persisted to disk in v1).
7. Skill prints a summary in the parent conversation: pass/fail per persona, top gaps to address. The full gap report follows as Markdown for the author to copy/act on.
8. If running in non-interactive mode, skill exits with non-zero status on fail.

**Business Rules:**
- A persona's questions are partitioned into `required` (counts toward pass/fail) and `optional` (informational only).
- Required questions must achieve `found: yes` for the persona to pass; `partial` and `no` count as fail.
- The aggregate doc set passes the gate when all `required: true` personas pass.
- Reader-test runs are stateless — no historical reports, no audit log, no `docs/.reader-test/` directory. Each run stands alone; trend tracking is deliberately out of v1 scope.

**Edge Cases:**
- Scenario: `claude -p` invocation fails or times out. → Expected: the skill records the failure as a `found: no` with reason "reader-test infrastructure error" and continues with remaining pairs; final summary distinguishes infrastructure failures from genuine doc gaps.
- Scenario: Author provides a persona with no questions. → Expected: skill rejects the configuration with a clear error, does not silently skip.
- Scenario: A doc page is empty / has only TODO header. → Expected: every persona × question reports `found: no`, with the gap report flagging the page as not yet drafted.
- Scenario: Network unavailable / no API key for `claude -p`. → Expected: skill exits with a clear error before spawning any subprocess; does not partially run.
- Scenario: Concurrent `review` runs in CI. → Expected: timestamped report files prevent collision; skill does not mutate shared state in `docs/`.

## Success Metrics

### Key Performance Indicators

Outcome-based, self-attested by the author. v1 is deliberately stateless — no telemetry, no on-disk audit logs, no historical reports. Success is judged on observable artifacts that exist regardless of the skill (the `docs/` tree itself, git history, the author's own retrospective).

- **Adoption (qualitative):** Within one quarter of v1 release, at least three TCS / MiYo repos (`miyo-tomo` mandatory as the worst-state benchmark) have had their docs migrated to a `doc-product`-generated `docs/` tree. Verifiable by inspecting each repo's `docs/` directory for the expected layout.
- **Engagement (workflow integration):** For each adopting repo, the author has integrated `extract` and `review` into their normal workflow. Verifiable indirectly via git history (commits that touch settings interfaces are followed by commits that touch `configuration.md`).
- **Quality (observable):** Running `review` on a `doc-product`-maintained repo achieves a passing reader-test (all required personas at 100% on required questions). The author re-runs as needed to confirm.
- **Self-reported value:** After three months of use, the author writes a brief retrospective (in personal notes / memory) on whether the skill saved time vs hand-authoring and whether the reader-test caught at least one real gap.

### Tracking Requirements

**Explicitly out of scope for v1.** No telemetry, no event collection, no on-disk audit logs, no `docs/.reader-test/` directory. The skill is stateless; each invocation produces output in the parent conversation only.

If trend tracking or cross-repo aggregation becomes important later, it will be a separate v2 concern (e.g. a future `tcs-helper:doc-stats` skill) and will not retroactively introduce persistence into the `doc-product` skill itself.

---

## Constraints and Assumptions

### Constraints
- **Runtime:** Skill must run within Claude Code's standard skill runtime; no daemons or persistent processes between invocations.
- **External dependencies:** `review` mode requires `claude` CLI installed and authenticated for headless `claude -p` calls; this is a hard prerequisite the skill must check before running.
- **Source-language coverage:** v1 settings extraction supports TypeScript interfaces, JSON Schema, and Pydantic / dataclass models. Other languages (Go, Rust, etc.) are out of v1.
- **Environment:** macOS / Linux primary targets; Windows compatibility through the same Claude Code interfaces but not specifically tested in v1.
- **TCS conventions:** Skill must follow `skill-author` conventions, with the architecture decisions consulted against `docs/about/skill-and-agent-design.md` (now wired into the decision-tree).
- **No auto-merge:** Per repository memory rules, the skill must not auto-commit to `main`; all generated files land in the working tree for author review.

### Assumptions
- **About users:** Authors are comfortable invoking Claude Code skills and editing Markdown; they do not need GUI tooling.
- **About the market:** No existing Claude Code skill provides reader-test-driven user-doc authoring; the closest analogue is Anthropic's `doc-coauthoring` (which targets internal docs and lacks automation).
- **About dependencies:** `claude -p` headless invocation remains a stable, available primitive in Claude Code through v1's lifetime.
- **About output:** Authors prefer the skill to surface drafts and proposals in the working tree rather than auto-committing them, consistent with TCS conventions.
- **About reader test fidelity:** A fresh `claude -p` instance is a sufficient stand-in for a real first-time user for the purposes of catching ambiguity, omitted prerequisites, and unanswered FAQ-style questions. It is not a stand-in for usability research, accessibility testing, or motor / cognitive-disability accommodation.

## Risks and Mitigations

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| `claude -p` rate-limits or costs scale poorly with persona count × page count | Medium | Medium | Default persona set kept small (≤ 4); `--since` filtering for diff-aware runs; budget warning on first invocation showing expected call count |
| Reader-test gives false positives (Claude misreads a clear doc) | Medium | Medium | Allow author to mark a specific gap as "false positive — intended" in `.claude/doc-personas.md` overrides; trend-track to surface persistent false positives for prompt tuning |
| `extract` mode misparses settings interfaces (TS unions, generics, etc.) | Medium | Medium | Fall back to `[NEEDS REVIEW]` markers rather than fabricating; provide clear "extraction not supported for this construct" output |
| Skill becomes too prescriptive about docs structure, conflicting with project preferences | Low | Medium | `plan` mode always proposes-then-confirms, never overwrites; project-local templates can override defaults |
| Author burnout — too many gates, friction outweighs value | High | Low | All four modes are independently invocable; no mode forces the others; v1 explicitly avoids making `review` a mandatory pre-merge hook |
| Reader test cost runs in CI exceed budget | Medium | Medium | `review --since` for diff-aware runs in CI; clear per-run cost estimate logged before execution |

## Open Questions

All v1-blocking clarifications resolved. Remaining items are deferrable to SDD or v2 planning:

- [ ] **(SDD)** Should `review` integrate with `/xdd-plan` or `/implement` as an optional quality gate? — design choice for v2; v1 keeps `review` independently invokable only.
- [ ] **(v2)** Manifest-derived "Plugin Metadata" section in `extract` mode.
- [ ] **(v2)** `tcs-helper:doc-stats` aggregation skill across repos.
- [ ] **(v2)** Recruit 1–2 other TCS plugin authors for usability feedback after Marcus's v1 dogfooding stabilizes.
- [ ] **(SDD)** Whether to also expose individual modes as their own slash commands (`/doc-plan`, `/doc-write`, etc.) in addition to `/doc-product <mode>` — Could-Have, design tradeoff.

---

## Supporting Research

### Competitive Analysis

| Tool | Approach | Strength | Gap doc-product fills |
|------|----------|----------|-----------------------|
| Anthropic `doc-coauthoring` skill | 3-stage workflow (context → structure → reader test) for internal docs (PRDs, RFCs) | Validated reader-test pattern (manual) | Targets internal not user-facing docs; reader test is manual, not automated |
| `typedoc` / Sphinx / mkdocstrings | API/code reference generation from source comments | Mature ecosystem, multi-format output | Generates code reference, not user-facing prose (install/config/troubleshooting) |
| Docusaurus / VitePress / mdbook | Static site generation from Markdown | Excellent presentation layer | Assume the Markdown is already authored; provide no authoring/review workflow |
| ReadMe.com, GitBook | Hosted authoring platforms | UI-driven editing, collaboration | External SaaS, not embedded in author's editor; no automated reader testing |
| LLM-driven "write me docs" prompts (ad-hoc) | Single-shot generation | Fast | Output drifts from source; no structure; no reader testing; no quality gate |

### User Research

- **n=1 case study (`miyo-tomo` → `miyo-kado` evolution):** Marcus's hands-on experience moving from a 198-line README to a structured `docs/` tree, after multiple manual iterations with Claude Code. This evolution implicitly defined the desired output of `plan` mode and the pain points that motivate `extract` and `review`.
- **Anthropic's `doc-coauthoring` skill design notes:** The "test the document with a fresh Claude (no context bleed)" pattern is the strongest validated signal for reader-test-as-quality-gate.
- **v1 scope decision:** Research is bounded to Marcus as solo author / sole user (n=1). Recruiting other TCS plugin authors for input is explicitly deferred to v2 — once v1 has matured against MiYo and TCS plugins owned by Marcus, the skill is offered to other plugin authors for validation feedback.

### Market Data

- TCS plugin ecosystem currently ships approximately 15 + plugins (tcs-team, tcs-helper, tcs-workflow, tcs-patterns, plugin-dev) with zero having a reader-test step today; potential addressable plugins for v1 adoption all have visible documentation gaps.
- The MiYo project family (`miyo-tomo`, `miyo-kado`, `miyo-hashi`, `miyo-kokoro`, `miyo-seigyo`, `miyo-shuu`, `miyo-satori`) is the immediate candidate set for skill validation, with `miyo-tomo` as the highest-value target (worst current state, biggest improvement headroom).
- No quantitative external market data — TCS is a personal/professional tooling ecosystem, not a commercial market.
