# Sources and Attribution

This document records the origins of The Custom Startup's components and acknowledges the work this project builds on.

It has a second job: making it cheap to check those origins for improvements. Every source below carries the date we adopted it, the upstream revision we last reconciled against, and whether it is still worth watching.

---

## Sync Status

| Source | Adopted | Last reconciled | Status |
|---|---|---|---|
| [rsmdt/the-startup](https://github.com/rsmdt/the-startup) | 2026-02-28 (`d36ee90`, v3.4) | 2026-08-31 — `principles.md` only, from their April 2026 rewrite | **monitored** |
| [citypaul/.dotfiles](https://github.com/citypaul/.dotfiles) | 2026-03-27 | 2026-08-31 — defect fixes from PR #184 (`331a637`) | **monitored** |
| [obra/superpowers](https://github.com/obra/superpowers) | 2026-03-27 (~v5.0.6) | never | **monitored** |
| [BayramAnnakov/claude-reflect](https://github.com/BayramAnnakov/claude-reflect) | 2026-03-26 | n/a | historical |
| [centminmod/my-claude-code-setup](https://github.com/centminmod/my-claude-code-setup) | 2026-03-26 | n/a | historical |
| [mksglu/context-mode](https://github.com/mksglu/context-mode) | 2026-03-27 (spec-005) | n/a | historical |
| [Bande-a-Bonnot/Boucle-framework](https://github.com/Bande-a-Bonnot/Boucle-framework) | 2026-05-09 | never | **monitored** |
| [lasso-security/mcp-gateway](https://github.com/lasso-security/mcp-gateway) | reference only | n/a | historical |
| [agiletec-inc/airis-mcp-gateway](https://github.com/agiletec-inc/airis-mcp-gateway) | reference only | n/a | historical |
| [dsebastien/claude-epic-status-line](https://github.com/dsebastien/claude-epic-status-line) | reviewed 2026-09-04, nothing ported yet | 2026-09-04 — first review (#72) | **monitored** |

**monitored** — actively developed, and the parts we adapted still move. Check on each sweep.
**historical** — attribution stands, but there is nothing left to pull. Reasons are recorded per source below. Skip these on a sweep.

---

## Base Fork

**The Custom Startup is forked from [rsmdt/the-startup](https://github.com/rsmdt/the-startup)** by [@rsmdt](https://github.com/rsmdt).

**Adopted:** 2026-02-28, at commit `d36ee90` (upstream v3.4) — the last upstream-authored commit in our history.
**Status:** monitored. Upstream is at v3.8.0 and still active.

The following concepts and structures were derived from that repository:

- **Spec-driven workflow concept** — the principle that every feature begins with a written specification before any code is written
- **Activity-based agent architecture** — organizing agents by what they *do* (activities) rather than by role alone
- **Slash command lifecycle** — the `specify → validate → implement → review` progression as the primary development loop
- **Output styles system** — the mechanism for defining and activating named output personalities

The Custom Startup extends these foundations with a full plugin architecture, an expanded agent library, the XDD specification system, and the tcs-patterns skill collection.

**Reconciled so far:** `docs/about/principles.md` was rewritten on 2026-08-31 from upstream's April 2026 re-grounding (`8a43e17`, `520e0f0`), with corrections where upstream had itself gone stale. The `skill-author` / `agent-author` reference files were separately re-grounded in that same upstream revision earlier — see `plugins/tcs-helper/CHANGELOG.md`.

---

## tcs-patterns Plugin — Skill Origins

The `tcs-patterns` plugin contains 19 domain pattern skills across three origin categories.

### citypaul-derived (14 skills)

**Repository:** [citypaul/.dotfiles](https://github.com/citypaul/.dotfiles)
**Adopted:** 2026-03-27
**Status:** monitored. Upstream ships roughly 50 skills now and has touched all ten of ours since our port.

These skills were ported from citypaul's Claude Code skills collection and converted to PICS format (the structured skill format used throughout The Custom Startup):

- `ddd`
- `frontend-testing`
- `functional`
- `hexagonal`
- `mutation-testing`
- `react-testing`
- `test-design-reviewer`
- `testing`
- `twelve-factor`
- `typescript-strict`
- `secure-oauth-oidc` — ported 2026-09-03 from `b270db1`; upstream `SKILL.md` restructured into PICS, all five references carried across with TCS cross-links added
- `observability` — ported 2026-09-03 from `b270db1`; SLO, error-budget and alerting content deliberately left behind, since `tcs-team:the-devops:monitor-production` owns it. Three of four upstream resources carried across; `slo-alerting.md` was not
- `event-sourcing` — ported 2026-09-03 from `c6dd90f` (the skill's own last upstream change is `8f1ebbc`, the #229 audit sweep). All nine upstream resources carried across. Trimmed where `tcs-patterns:event-driven` already owned the ground — event naming, envelope fields, correlation and causation IDs, handler idempotency — which the port defers to rather than restates. Knock-on edits in the same PR: `event-driven` lost its own event-sourcing and event-store sections to a boundary pointer and gained a Boundaries table, `ddd` and `hexagonal` name the new owner
- `bff-entry-points` — ported 2026-09-03 from `c6dd90f` (the skill's own last upstream change is `8f1ebbc`, the #229 audit sweep). All six upstream references carried across. Upstream's companion `bff-design` was declined in ADR 0002 — whether to have a BFF at all is an architecture decision belonging to `tcs-team:the-architect:design-system` — so only the entry-point half is here. Cross-references to upstream skills TCS does not have (`structure-codebase`, `codebase-design`, `cli-design`) were dropped rather than renamed, and their requirements restated without naming a skill. Knock-on edit: `secure-oauth-oidc` no longer declares the browser session layer unguided

Porting to PICS format involved restructuring content into progressive disclosure sections, adding frontmatter trigger terms, and aligning with the skill conventions used in this project. The underlying knowledge and guidance originates with citypaul's work.

**Reconciled so far:** on 2026-08-31, defect fixes from upstream PR #184 (`331a637`) were applied to `testing`, `frontend-testing`, and `ddd`; then `hexagonal` was reconciled against Cockburn's own write-up (#187, `08d046a`), `ddd` gained invariant-first aggregate design (#168), and `mutation-testing` adopted the PR-readiness gate (#212). Still outstanding: honest E2E evidence (#210) and the #229 audit sweep.

**New upstream skills:** nine were evaluated on 2026-08-31 — four accepted for porting (`observability`, `event-sourcing`, `secure-oauth-oidc`, `bff-entry-points`), one merged into `ddd` rather than added (`ubiquitous-language`), four declined. Reasoning in [ADR 0002](../XDD/adr/0002-citypaul-skill-absorption-verdicts.md) so the next sweep does not re-evaluate them from zero.

**Port progress:** complete. `secure-oauth-oidc` (#95), `observability` (#96), `event-sourcing` (#97) and `bff-entry-points` (#98) all landed 2026-09-03, one pull request each — the original argument for batching them was to spare the plugin repeated version bumps, and that stopped mattering once the auto-bump race in #93 was fixed. All four skills accepted in ADR 0002 are now ported.

### TCS-native (5 skills)

These skills were created specifically for The Custom Startup and have no upstream source:

- `api-design`
- `event-driven`
- `go-idiomatic`
- `node-service`
- `python-project`

### Integration skills (2 skills)

Full SKILL.md implementations for specific platform targets, created for this project:

- `mcp-server`
- `obsidian-plugin`

---

## Agent Architecture

The 15 agents across 8 roles in the `tcs-team` plugin are TCS-native — none are ported from an external source.

The activity-based organization pattern (grouping agents by what they do rather than mapping one-to-one to job titles) draws on published research into LLM multi-agent collaboration and the patterns established by leading agent frameworks. Key references include:

- *Multi-Agent Collaboration Mechanisms* (2025) — research on specialization and task decomposition in LLM agent systems
- Industry framework patterns from CrewAI, AutoGen, and LangGraph

These influenced the structural approach; the agent definitions, prompts, and role boundaries are original to this project.

> Note: this framing is historical. Current design rationale is grounded in Anthropic primary sources — see [principles.md](principles.md) § 2.4.

---

## Output Styles

The `the-startup` and `the-scaleup` output styles were developed for this fork and are not derived from upstream sources.

---

## Memory Bank — Source Influences

The Memory Bank system in `tcs-helper` draws on several community approaches to Claude Code memory management.

### claude-reflect

**Repository:** [BayramAnnakov/claude-reflect](https://github.com/BayramAnnakov/claude-reflect)
**Adopted:** 2026-03-26
**Status:** historical — the repository's last push was 2026-03-16, before we adopted it, and there have been no commits since. Nothing will arrive.

Foundation for the Memory Bank capture layer. The two-stage self-learning hooks (detect corrections → queue → route to destinations) and the learning destinations model (global CLAUDE.md, project CLAUDE.md, CLAUDE.local.md) directly informed the TCS global/project/repo routing table. The `reflect-skills` session analysis — identifying repeating patterns and generating skill files — provides the promotion mechanism used by `/memory-promote`.

### John Conneely Memory System

**Article:** [How I Finally Sorted My Claude Code Memory](https://www.youngleaders.tech/p/how-i-finally-sorted-my-claude-code-memory)
**Adopted:** 2026-03-26
**Status:** historical — a published article, not a moving target.

The memory category taxonomy (general conventions, tools integrations, domain knowledge) is applied across TCS scopes instead of a single global bucket. The MEMORY.md index-only pattern was adopted as a design constraint; its companion size budget has since been restated in bytes, because memory entries are single long lines and a line count says nothing about their cost. The principle that routing rules belong in CLAUDE.md, not in MEMORY.md, directly informed the TCS approach.

### centminmod/my-claude-code-setup

**Repository:** [centminmod/my-claude-code-setup](https://github.com/centminmod/my-claude-code-setup)
**Adopted:** 2026-03-26
**Status:** historical — the repository is active, but essentially all of it is version churn in its own `session-metrics` tool. The parts we adapted have not moved.

The memory bank architecture (per-concern files: activeContext, patterns, decisions, troubleshooting) informed the repo-level typed memory directory at `docs/ai/memory/`. The cleanup-context workflow (token reduction, archive resolved issues) forms the core of `/memory-cleanup`. Stack-aware CLAUDE.md templates (Cloudflare Workers, Convex) provided the pattern reused in `/setup`.

### citypaul/.dotfiles (philosophy)

**Repository:** [citypaul/.dotfiles](https://github.com/citypaul/.dotfiles)
**Status:** monitored — see the pattern-skill entry above.

Beyond the pattern skills (listed above), the philosophy-first CLAUDE.md approach (~100 lines core, skills on demand) justified keeping all CLAUDE.md files lean and delegating detail to skills and memory docs. The setup command concept (detect stack, generate CLAUDE.md + hooks) directly inspired `/setup`.

---

## TDD Discipline — Source Influences

### obra/superpowers

**Repository:** [obra/superpowers](https://github.com/obra/superpowers) by Jesse Vincent
**Adopted:** 2026-03-27, around upstream v5.0.6
**Status:** monitored. Upstream is at v6.3.0 — a major version with changes to skills we derived from, including safety-relevant ones.

The TDD RED-GREEN-REFACTOR iron law and the rejected-rationalizations table are embedded into the `xdd-tdd` skill and the TDD/SDD integration design. The verification-before-completion discipline (evidence-before-claims) is implemented as the `/verify` gate. The receiving-code-review rigor pattern forms the basis of `/receive-review`. Dispatching-parallel-agents patterns were absorbed into `/parallel-agents`. Systematic-debugging anti-shortcut rules strengthen `/debug`. Related lineage: `/finish-branch`, `/git-worktree`, and `/brainstorm`.

**Reconciled so far:** nothing. This is the largest outstanding gap.

---

## Git Safety Hooks — Source Influences

### Boucle-framework

**Repository:** [Bande-a-Bonnot/Boucle-framework](https://github.com/Bande-a-Bonnot/Boucle-framework)
**Adopted:** 2026-05-09 (patterns only, re-implemented rather than vendored)
**Status:** monitored — the hooks we drew on are still the closest prior art for `tcs-git-helpers`.

Three tools under `tools/` are prior art for the `tcs-git-helpers` hook set: `git-safe` (destructive-operation prevention over a regex set covering `--no-verify`, `reset --hard`, `clean -f`, `branch -D`, `stash drop/clear`, `reflog expire`), `branch-guard` (protected-branch commit blocking driven by a `.branch-guard` config), and `worktree-guard` (exit-time data-loss prevention via four `git cherry` checks). `worktree-guard` also confirmed that `PreToolUse:ExitWorktree` is the blockable event for worktree guards.

---

## Satori — Source Influences

### context-mode

**Repository:** [mksglu/context-mode](https://github.com/mksglu/context-mode) by Mert Koseoglu
**Adopted:** 2026-03-27 (spec-005, implemented)
**Status:** historical — the repository is busy, but the commit stream is almost entirely automated install-stats updates. The architectural idea we took has not changed.

The MCP server concept — capturing tool outputs in a structured database and serving compact summaries instead of replaying full outputs — is the architectural basis for Satori's context capture layer. The reported 90-98% context reduction motivated offloading session data to a context server.

### MCP Gateway patterns

**Repositories:** [lasso-security/mcp-gateway](https://github.com/lasso-security/mcp-gateway), [agiletec-inc/airis-mcp-gateway](https://github.com/agiletec-inc/airis-mcp-gateway)
**Status:** historical — reference architecture only, never a code dependency. `lasso-security/mcp-gateway` has been inactive since 2026-01-22.

The gateway design — composing multiple downstream MCP servers behind a single endpoint — provided the reference architecture for Satori's server routing layer.

---

## Running a Sweep

Checking sources for improvements should not require git archaeology. The procedure:

```bash
# 1. Upstream activity since our adoption date (from the Sync Status table)
gh api "/repos/<owner>/<repo>/commits?since=<YYYY-MM-DD>T00:00:00Z&per_page=100" --paginate \
  --jq '.[] | "\(.commit.author.date[0:10]) \(.commit.message|split("\n")[0])"'

# 2. Per-file history, to see whether a specific thing we ported has moved
gh api "/repos/<owner>/<repo>/commits?path=<path/to/FILE.md>&since=<YYYY-MM-DD>T00:00:00Z" \
  --jq '.[] | "\(.commit.author.date[0:10]) \(.commit.message|split("\n")[0])"'

# 3. The patch for a specific commit, scoped to files we care about
gh api "/repos/<owner>/<repo>/commits/<sha>" \
  --jq '.files[] | select(.filename|test("<pattern>")) | "===== \(.filename)\n\(.patch)"'

# 4. Current upstream file content, to diff against ours
gh api "/repos/<owner>/<repo>/contents/<path>" --jq '.content' | base64 -d
```

Two rules learned the hard way:

- **Do not adopt a claim because upstream states it.** Upstream drifts too. The 2026-08-31 sweep found stale model pricing (3× off) and a closed bug listed as open in a document we were about to import.
- **Record what was deliberately *not* adopted, and why** — otherwise the next sweep re-litigates it from zero.

## Statusline — Source Influences

### dsebastien/claude-epic-status-line

- **Reviewed:** 2026-09-04 at `master` (pushed 2026-08-26), MIT
- **Ported:** nothing yet — the review produced #129, #130 and #131 under #72
- **Why it is here anyway:** three specific mechanisms were taken as *design input* for those
  issues and will carry code if they land, so the lineage is recorded before rather than after.

What the review found worth taking:

| Mechanism | Where it would land | Issue |
|---|---|---|
| `extra_usage` from `api.anthropic.com/api/oauth/usage` — credit consumption against the monthly limit, which neither the stdin payload nor ccusage exposes | a new opt-in segment | #129 |
| One `jq` pass extracting every field as `@tsv`, with `-` sentinels so an empty field cannot shift the positional `read` | `read_input` | #130 |
| Per-uid cache directory created `mode 700`, with symlink and ownership checks that disable caching rather than redirect it | the cache helpers | #131 |

Deliberately **not** taken: their `CESL_*` environment-variable configuration with three-tier
precedence — `statusline.toml` already covers that ground and switching would be churn without
gain. Their percentage clamping and post-failure negative caching were arrived at independently
here (#118, and the existing ccusage cache), so those are convergent rather than adopted.

One convergence worth noting: their `stat -c %Y || stat -f %m` puts the GNU form first, which is
the same ordering #118 landed on after the BSD-first form was found to pollute stdout on GNU.

---

### Sweep log

| Date | Scope | Outcome |
|---|---|---|
| 2026-09-04 | dsebastien/claude-epic-status-line (#72) | Reviewed on request rather than as part of a sweep. Nothing ported; three adoption candidates filed as #129, #130, #131. |
| 2026-08-31 | All eight sources | Three found still worth monitoring, five retired to historical. Tracked as epic #73 with twelve child issues. Landed: `tcs-patterns` defect fixes (#74), `principles.md` rewrite (#75), this file (#78). |

---

## Why Attribution Matters

Keeping this document up to date serves a practical purpose: it makes the lineage of each component visible, which makes it straightforward to check upstream sources for improvements and to give proper credit when sharing or redistributing.

If you port, adapt, or extend components from another source, add it here — with the adoption date and the upstream revision. A source without those is a source nobody can cheaply re-check.
