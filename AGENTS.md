# AGENTS.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Is

**The Custom Agentic Startup** is a spec-driven development framework for Claude Code, distributed as marketplace plugins. It provides workflow skills, specialized agents, hooks and output styles.

## Repository Structure

`tests/test_agents_md_tree.py` checks this tree against the filesystem in both directions: every entry must exist, and every plugin, skill and agent must be named.

```
the-custom-startup/
├── plugins/
│   ├── tcs-workflow/             # Core workflow orchestration plugin
│   │   ├── .claude-plugin/       # Plugin manifest (plugin.json)
│   │   ├── agents/               # Review and TDD gates the implement loop dispatches:
│   │   │                         #   spec-compliance-reviewer, code-quality-reviewer, tdd-guardian
│   │   ├── skills/               # 23 skills (user-invocable + autonomous)
│   │   │                         # Core: analyze, brainstorm, constitution, debug,
│   │   │                         #   document, guide, implement, parallel-agents, pickup,
│   │   │                         #   receive-review, refactor, review, test,
│   │   │                         #   validate, verify
│   │   │                         # implement dispatches to implement-direct /
│   │   │                         #   implement-incremental by decomposition tier
│   │   │                         # XDD: xdd, xdd-meta, xdd-plan, xdd-prd, xdd-sdd, xdd-tdd
│   │   ├── output-styles/        # the-startup, the-scaleup
│   │   ├── evals/                # claude plugin eval suites
│   │   └── README.md             # Detailed plugin documentation
│   │
│   ├── tcs-team/                 # Specialized agent library plugin
│   │   ├── agents/
│   │   │   ├── the-chief.md      # Complexity assessment, routing
│   │   │   ├── the-analyst/      # research-product
│   │   │   ├── the-architect/    # design-system, record-decision, review-security,
│   │   │   │                     #   review-robustness, review-compatibility
│   │   │   ├── the-developer/    # build-feature, optimize-performance
│   │   │   ├── the-devops/       # build-platform, monitor-production
│   │   │   ├── the-designer/     # research-user, design-interaction, design-visual
│   │   │   └── the-tester/       # test-strategy
│   │   └── skills/               # Domain skills the agents load:
│   │                             #   api-contract-design, architecture-selection,
│   │                             #   code-quality-review, domain-modeling,
│   │                             #   feature-prioritization, frontend-patterns,
│   │                             #   pattern-detection, performance-analysis,
│   │                             #   platform-operations, project-discovery,
│   │                             #   requirements-elicitation, security-assessment,
│   │                             #   technical-writing, test-practices, user-research
│   │
│   ├── tcs-helper/               # Authoring, memory and session tooling (optional)
│   │   ├── .claude-plugin/       # Plugin manifest (plugin.json)
│   │   ├── hooks/hooks.json      # UserPromptSubmit, SessionStart, PreCompact, PostToolUse
│   │   ├── scripts/              # Python hook scripts; shared code in scripts/lib/
│   │   ├── templates/            # CLAUDE.md + memory templates (stacks: ts, go, python, cf, convex)
│   │   ├── evals/                # claude plugin eval suites
│   │   └── skills/
│   │       ├── skill-author/     # Create, audit, convert Claude Code skills (PICS, TDD Iron Law)
│   │       ├── agent-author/     # Create, audit Claude Code subagents
│   │       ├── prompt-author/    # Write, audit, port prompts a model reads (API, briefs, AGENTS.md)
│   │       ├── skill-evaluate/   # Evaluate a skill before importing or using
│   │       ├── skill-import/     # Fetch + install a single skill from any GitHub repo
│   │       ├── rule-enforcer/    # Turn a recurring rule into a hook
│   │       ├── memory-setup/     # Provision docs/ai/memory/ + CLAUDE.md hierarchy in new repos
│   │       ├── memory-add/       # Capture session learnings → route to correct memory file
│   │       ├── memory-sync/      # Keep @imports and memory index in sync
│   │       ├── memory-cleanup/   # Archive resolved issues, prune stale entries
│   │       ├── memory-promote/   # Promote domain patterns to reusable skills
│   │       ├── memory-claude-md-optimize/ # Audit, score, migrate CLAUDE.md → Memory Bank
│   │       ├── context-bridge/   # Checkpoint a session before /clear or /compact
│   │       ├── observability-setup/ # Turn session recording on or off per repo
│   │       ├── claude-docs/      # Fetch and cache current Claude Code docs
│   │       ├── doc-product/      # Plan, write and reader-test user-facing docs
│   │       ├── finish-branch/    # Branch completion workflow
│   │       └── git-worktree/     # Git worktree management
│   │
│   ├── tcs-patterns/             # Domain pattern skills plugin (optional, selective install)
│   │   ├── .claude-plugin/       # Plugin manifest (plugin.json)
│   │   ├── skills/               # patterns-setup (installer), pattern (catalogue reader)
│   │   └── templates/patterns/   # catalogue, installed per repo as .claude/skills/tcs-<name>:
│   │                             # Architecture: ddd, hexagonal, functional, event-driven,
│   │                             #               event-sourcing
│   │                             # API & Types: api-design, typescript-strict
│   │                             # Security: secure-oauth-oidc, bff-entry-points
│   │                             # Testing: testing, mutation-testing, frontend-testing, react-testing, test-design-reviewer
│   │                             # Platforms: node-service, python-project, go-idiomatic
│   │                             # DevOps: twelve-factor (→ tcs-team:the-devops:build-platform)
│   │                             #         observability (→ tcs-team:the-devops:monitor-production)
│   │                             # Integrations: mcp-server, obsidian-plugin
│   │
│   ├── tcs-git-helpers/          # Git hooks: branch protection, commit checks, audit (optional)
│   │   ├── hooks/hooks.json
│   │   └── skills/               # git-setup (installer), git-audit (branch and override audit)
│   │
│   └── tcs-issues/               # GitHub issue lifecycle on a Projects (v2) board (optional)
│       ├── hooks/hooks.json      # Deny issue reads that skip comments; note after issue lists
│       └── skills/               # issue, link-issue (sub-issues)
│
├── scripts/
│   ├── ci/                                         # CI checks (docs-sync, changelog/version sync)
│   ├── dev/test.sh                                 # Provision .venv and run pytest + bats
│   ├── observability/                              # Session recording and report tooling
│   ├── the-custom-startup-statusline-standard.sh   # Standard (single-line) statusline
│   ├── the-custom-startup-statusline-enhanced.sh   # Enhanced statusline with budget bar
│   ├── the-custom-startup-statusline-lib.sh        # Shared statusline library
│   ├── the-custom-startup-statusline-starship.sh   # Starship-compatible statusline
│   ├── the-custom-startup-configure-statusline.sh  # Statusline installer/configurator
│   ├── export-spec.sh                              # Export spec to clipboard/file
│   ├── import-spec.sh                              # Import spec from file
│   └── statusline.toml                             # Statusline configuration template
│
├── docs/
│   ├── about/                    # Concepts, philosophy, principles, sources
│   ├── ai/memory/                # Memory bank (routing rules in CLAUDE.md)
│   ├── getting-started/          # Index, installation, quick-start, workflow
│   ├── guides/                   # Multi-AI workflow, statusline, tcs-patterns
│   ├── reference/                # Agents, plugins, skills, output-styles, XDD
│   ├── templates/                # Multi-AI prompt templates (PRD, brainstorm, research, etc.)
│   └── XDD/                      # Spec directories, ADRs, ideas
│
├── tests/                        # Repo-level pytest suites
├── .github/workflows/            # Tests, auto-bump, release
├── install.sh                    # Interactive install wizard
├── uninstall.sh                  # Interactive uninstall wizard
└── README.md                     # User-facing documentation
```

## Key Concepts

### Plugin Architecture

Each plugin lives in `plugins/[name]/` with:
- `.claude-plugin/plugin.json` - Plugin manifest defining name, version, components
- `skills/` - User-invocable and autonomous skills (SKILL.md files with trigger terms)
- `agents/` - Agent definitions (tcs-workflow, tcs-team)
- `hooks/hooks.json` - Hook registrations (tcs-helper, tcs-patterns, tcs-git-helpers)
- `output-styles/` - Output style definitions (tcs-workflow)

**Skill invocation**: plugin skills are namespaced by their plugin, as the repo's own files invoke
them: `Skill(tcs-workflow:validate)`, `/tcs-helper:skill-author`. The tcs-team domain skills are
loaded by its agents.

### Skill Structure

Skills use progressive disclosure to minimize context usage:
```
skills/[skill-name]/
├── SKILL.md           # Core logic (always loaded)
├── reference/         # Advanced protocols (loaded when needed)
├── templates/         # Document templates
├── examples/          # Real-world scenarios
└── validation.md      # Quality checklists
```

For full skill conventions, PICS structure, and transformation checklist, see the `skill-author` skill (`plugins/tcs-helper/skills/skill-author/reference/conventions.md`).

### Agent Structure (Team Plugin)

Agents are organized by role with activity-based specializations:
```
agents/the-[role]/
├── [activity-1].md    # e.g., the-architect/design-system.md
├── [activity-2].md    # e.g., the-architect/review-security.md
└── ...
```

Each agent markdown file defines:
- Purpose and trigger conditions
- Tool access permissions
- Activation examples
- Integration with other agents

For agent conventions, see the `agent-author` skill (`plugins/tcs-helper/skills/agent-author/reference/conventions.md`).

## Development Workflow

### Running the Test Suite

```bash
./scripts/dev/test.sh          # pytest + bats
./scripts/dev/test.sh pytest   # python suites only
./scripts/dev/test.sh bats     # bats suites only
./scripts/dev/test.sh setup    # provision .venv and stop
```

The script provisions everything into `.venv/` on first run — `pytest` and
`PyYAML` from `requirements-dev.txt`, and `bats` (a bash program, so it comes
via npm and gets symlinked into `.venv/bin`). Re-runs skip provisioning.

Both suites also run in CI on every pull request (`.github/workflows/tests.yml`).

To run a single suite directly, activate the venv first — several bats files
shell out to `python3` for YAML validation and need it on `PATH`:

```bash
source .venv/bin/activate
bats plugins/tcs-git-helpers/tests/bats/lib_pattern_match.bats
pytest tests/tcs-helper/test_capture_learning.py
```

In the Docker dev container, `.venv/` is a bind mount shared with the macOS
host, so a venv built on one side has an interpreter path that does not exist
on the other. `test.sh` detects that and rebuilds in place instead of failing
with `bad interpreter`.

### Testing Changes Locally

Copy the changed skill into the plugin cache and the marketplace source, then run
`/reload-plugins`. The steps are in CLAUDE.md, "Testing Skills During Development". Those copies
are throwaway: never release by copying.

### Editing Skills

1. Skills are markdown files (`SKILL.md`) - edit directly
2. Skills activate on the `description` in their YAML frontmatter
3. Keep `SKILL.md` under 500 lines; move advanced content to `reference/` (loaded on demand)
4. Audit every skill change with `/tcs-helper:skill-author` before committing

### Invoking Skills as Commands

The `tcs-workflow` plugin has no separate `commands/` directory — skills serve as the user-invocable
entry points. Each skill in `plugins/tcs-workflow/skills/[name]/SKILL.md` is invoked as
`/tcs-workflow:[name]` (e.g. `/tcs-workflow:xdd`).

To add a new workflow entry point, add a skill directory under `plugins/tcs-workflow/skills/`.

### Editing Agents

1. Agents are markdown files in `plugins/tcs-team/agents/[role]/` or `plugins/tcs-workflow/agents/`
2. A team agent's name follows `tcs-team:[role]:[activity]`
3. Agents define specialized Task tool prompts for subagent delegation

### Editing Output Styles

1. Output styles are markdown files in `plugins/[plugin]/output-styles/`
2. Define personality, voice, and behavioral patterns
3. Activated via `/output-style [plugin]:[style-name]`

## Important Patterns

### Spec-Driven Development

The primary workflow: `/xdd` → `/validate` → `/implement` → `/review`

Specifications live in `docs/XDD/specs/[NNN]-[name]/`:
- `requirements.md` - What to build
- `solution.md` - How to build it
- `plan/` - Execution sequence (README.md manifest + phase-N.md files)

### Constitution Enforcement

Optional `CONSTITUTION.md` at project root defines checkable rules:
- L1 (Must) - Blocking with autofix
- L2 (Should) - Blocking, manual fix
- L3 (May) - Advisory only

## File Naming Conventions

| Type | Location | Naming |
|------|----------|--------|
| Skills | `plugins/*/skills/*/SKILL.md` | directory is skill name |
| Agents | `plugins/tcs-team/agents/the-*/` | `the-[role]/[activity].md` |
| Output Styles | `plugins/*/output-styles/*.md` | lowercase-kebab (e.g., `the-startup.md`) |
| Specs | `docs/XDD/specs/[NNN]-*/` | 3-digit ID prefix |

## Publishing

The repository is a Claude Code marketplace. Publishing happens via:
1. Push to `main` branch
2. GitHub Actions workflow creates release
3. Users install via `./install.sh` or `/plugin marketplace add MMoMM-org/the-custom-startup`

Plugin versions are bumped on merge by `.github/workflows/auto-bump-versions.yml`: a patch bump for every merged commit that touched the plugin since its version was last raised. What is owed is read from `main`'s history, not from the triggering push, so a run that never happened is caught up by the next one (or by Run workflow). A breaking or feature release is requested by writing the next-major or next-minor heading (e.g. `## [2.0.0] - <date>` against a 1.4.x manifest) at the top of the plugin's `CHANGELOG.md`; never hand-edit `plugin.json`. On a pull request, a CHANGELOG version beyond one patch, the next minor or the next major ahead of the manifest fails `scripts/ci/check-changelog-version-sync.sh`; a pre-release or non-canonical heading (`2.0.0-rc1`, `2.00.0`) requests nothing and gets the patch bump.
