# AGENTS.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Is

**The Custom Agentic Startup** is a spec-driven development framework for Claude Code, distributed as marketplace plugins. It provides workflow commands, autonomous skills, specialized agents, and output styles to transform how you build software.

## Repository Structure

```
the-custom-startup/
├── plugins/
│   ├── tcs-workflow/             # Core workflow orchestration plugin
│   │   ├── .claude-plugin/       # Plugin manifest (plugin.json)
│   │   ├── agents/               # Workflow agents (e.g., the-chief)
│   │   ├── skills/               # 20 skills (user-invocable + autonomous)
│   │   │   │                     # Core: analyze, brainstorm, constitution, debug,
│   │   │   │                     #   document, guide, implement, parallel-agents,
│   │   │   │                     #   receive-review, refactor, review, test,
│   │   │   │                     #   validate, verify
│   │   │   │                     # XDD: xdd, xdd-meta, xdd-plan, xdd-prd, xdd-sdd, xdd-tdd
│   │   ├── output-styles/        # The Startup, The ScaleUp output styles
│   │   └── README.md             # Detailed plugin documentation
│   │
│   ├── tcs-team/                 # Specialized agent library plugin
│   │   ├── agents/               # 8 roles with 15 agents (13 activity + the-chief + the-meta-agent)
│   │   │   ├── the-chief.md      # Complexity assessment, routing
│   │   │   ├── the-analyst/      # research-product
│   │   │   ├── the-architect/    # design-system, review-security, review-robustness, review-compatibility
│   │   │   ├── the-developer/    # build-feature, optimize-performance
│   │   │   ├── the-devops/       # build-platform, monitor-production
│   │   │   ├── the-designer/     # research-user, design-interaction, design-visual
│   │   │   ├── the-tester/       # test-strategy
│   │   │   └── the-meta-agent.md # Agent design and generation
│   │   └── skills/               # Domain skills (cross-cutting, design, development, infrastructure, quality)
│   │
│   ├── tcs-helper/               # Skill authoring + memory system plugin (optional)
│   │   ├── .claude-plugin/       # Plugin manifest (plugin.json, v2.0.0)
│   │   ├── hooks/hooks.json      # 4 hook events: UserPromptSubmit, SessionStart, PreCompact, PostToolUse
│   │   ├── scripts/              # Python hook scripts + lib/reflect_utils.py
│   │   ├── templates/            # 19 CLAUDE.md + memory templates (stacks: ts, go, python, cf, convex)
│   │   └── skills/
│   │       ├── skill-author/     # Create, audit, convert Claude Code skills (PICS, TDD Iron Law)
│   │       ├── skill-evaluate/   # Evaluate a skill before importing or using
│   │       ├── skill-import/     # Fetch + install a single skill from any GitHub repo
│   │       ├── memory-add/       # Capture session learnings → route to correct memory file
│   │       ├── memory-sync/      # Keep @imports and memory index in sync
│   │       ├── memory-cleanup/   # Archive resolved issues, prune stale entries
│   │       ├── memory-promote/   # Promote domain patterns to reusable skills
│   │       ├── setup/            # Provision docs/ai/memory/ + CLAUDE.md hierarchy in new repos
│   │       ├── docs/             # Generate and maintain project documentation
│   │       ├── finish-branch/    # Branch completion workflow
│   │       └── git-worktree/     # Git worktree management
│   │
│   └── tcs-patterns/             # Domain pattern skills plugin (optional, selective install)
│       ├── .claude-plugin/       # Plugin manifest (plugin.json)
│       └── skills/               # 17 pattern skills:
│           │                     # Architecture: ddd, hexagonal, functional, event-driven
│           │                     # API & Types: api-design, typescript-strict
│           │                     # Testing: testing, mutation-testing, frontend-testing, react-testing, test-design-reviewer
│           │                     # Platforms: node-service, python-project, go-idiomatic
│           │                     # DevOps: twelve-factor (→ tcs-team:the-devops:build-platform)
│           │                     # Integrations: mcp-server, obsidian-plugin
│
├── scripts/
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
│   ├── getting-started/          # Index, installation, quick-start, workflow
│   ├── guides/                   # Multi-AI workflow, statusline, tcs-patterns
│   ├── reference/                # Agents, plugins, skills, output-styles, XDD
│   ├── templates/                # Multi-AI prompt templates (PRD, brainstorm, research, etc.)
│   └── XDD/                      # Spec directories, ADRs, ideas
│
├── install.sh                    # Interactive install wizard
├── uninstall.sh                  # Interactive uninstall wizard
└── README.md                     # User-facing documentation
```

## Key Concepts

### Plugin Architecture

Each plugin lives in `plugins/[name]/` with:
- `.claude-plugin/plugin.json` - Plugin manifest defining name, version, components
- `skills/` - User-invocable and autonomous skills (SKILL.md files with trigger terms)
- `output-styles/` - Output style definitions
- `agents/` - Agent definitions (team plugin only)

**Skill invocation**: Skills are invoked by their name directly (e.g., `/brainstorm`, `/implement`).
Plugin-name prefixing (`tcs-workflow:brainstorm`) only applies to commands, not skills.
The team plugin's domain skills are agent-internal and not user-invocable directly.

### Skill Structure

Skills use progressive disclosure to minimize context usage:
```
skills/[skill-name]/
├── SKILL.md           # Core logic (~7-24 KB, always loaded)
├── reference/         # Advanced protocols (loaded when needed)
├── templates/         # Document templates
├── examples/          # Real-world scenarios
└── validation.md      # Quality checklists
```

For full skill conventions, PICS structure, and transformation checklist, see the `writing-skills` skill (`plugins/tcs-workflow/skills/writing-skills/reference/conventions.md`).

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

## Development Workflow

### Testing Changes Locally

```bash
# The plugins are directories - test by installing from local path
claude plugin install ./plugins/tcs-workflow
claude plugin install ./plugins/tcs-team

# Or use the main installer to test full installation
./install.sh

# Uninstall to reset (interactive wizard)
./uninstall.sh
```

### Editing Skills

1. Skills are markdown files (`SKILL.md`) - edit directly
2. Skills activate on trigger terms defined in their YAML frontmatter
3. Keep `SKILL.md` under ~25 KB for context efficiency
4. Move advanced content to `reference/` directory (loaded on demand)

### Invoking Skills as Commands

The `tcs-workflow` plugin has no separate `commands/` directory — skills serve as the user-invocable
entry points. Each skill in `plugins/tcs-workflow/skills/[name]/SKILL.md` is accessible as
`/[name]` (e.g. `/xdd`, `/implement`).

To add a new workflow entry point, add a skill directory under `plugins/tcs-workflow/skills/`.

### Editing Agents

1. Agents are markdown files in `plugins/tcs-team/agents/[role]/`
2. Agent name matches `[role]:[activity]` pattern
3. Agents define specialized Task tool prompts for subagent delegation

### Editing Output Styles

1. Output styles are markdown files in `plugins/[plugin]/output-styles/`
2. Define personality, voice, and behavioral patterns
3. Activated via `/output-style [plugin]:[style-name]`

## Important Patterns

### Progressive Disclosure

Skills load minimal context initially, then progressively load:
- `reference/` - Advanced protocols when complexity increases
- `templates/` - Document templates when creating artifacts
- `examples/` - Real-world scenarios when pattern matching

### Spec-Driven Development

The primary workflow: `/xdd` → `/validate` → `/implement` → `/review`

Specifications live in `docs/XDD/specs/[NNN]-[name]/`:
- `requirements.md` - What to build
- `solution.md` - How to build it
- `plan/` - Execution sequence (README.md manifest + phase-N.md files)

### Knowledge Capture

Discovered patterns, interfaces, and domain rules are automatically documented in:
- `docs/patterns/` - Technical patterns
- `docs/interfaces/` - External integrations
- `docs/domain/` - Business rules

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


