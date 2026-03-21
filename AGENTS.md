# AGENTS.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Is

**The Custom Agentic Startup** is a spec-driven development framework for Claude Code, distributed as marketplace plugins. It provides workflow commands, autonomous skills, specialized agents, and output styles to transform how you build software.

## Repository Structure

```
the-custom-startup/
├── plugins/
│   ├── start/                    # Core workflow orchestration plugin
│   │   ├── .claude-plugin/       # Plugin manifest (plugin.json)
│   │   ├── skills/               # 16 skills (12 user-invocable + 4 autonomous)
│   │   ├── output-styles/        # The Startup, The ScaleUp output styles
│   │   └── README.md             # Detailed plugin documentation
│   │
│   └── team/                     # Specialized agent library plugin
│       ├── agents/               # 8 roles with 15 agents (13 activity + the-chief + the-meta-agent)
│       │   ├── the-chief.md      # Complexity assessment, routing
│       │   ├── the-analyst/      # research-product
│       │   ├── the-architect/    # design-system, review-security, review-robustness, review-compatibility
│       │   ├── the-developer/    # build-feature, optimize-performance
│       │   ├── the-devops/       # build-platform, monitor-production
│       │   ├── the-designer/     # research-user, design-interaction, design-visual
│       │   ├── the-tester/       # test-strategy
│       │   └── the-meta-agent.md # Agent design and generation
│       └── skills/               # Domain skills (cross-cutting, design, development, infrastructure, quality)
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
│   ├── PHILOSOPHY.md             # Activity-based architecture rationale
│   ├── PRINCIPLES.md             # Core development principles
│   ├── multi-ai-workflow.md      # Using Claude.ai + Perplexity alongside Claude Code
│   ├── workflow.md               # Full spec-driven workflow reference
│   ├── skills.md                 # Skills reference
│   ├── agents.md                 # Agents reference
│   ├── plugins.md                # Plugins reference
│   ├── statusline.md             # Statusline setup guide
│   └── templates/                # Multi-AI prompt templates (PRD, brainstorm, research, etc.)
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

**Skill namespacing**: Claude Code automatically prefixes skills with the plugin name from
`plugin.json`. A skill named `brainstorm` in the `start` plugin is invocable as `start:brainstorm`.
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

For full skill conventions, PICS structure, and transformation checklist, see the `writing-skills` skill (`plugins/start/skills/writing-skills/reference/conventions.md`).

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
claude plugin install ./plugins/start
claude plugin install ./plugins/team

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

The `start` plugin has no separate `commands/` directory — skills serve as the user-invocable
entry points. Each skill in `plugins/start/skills/[name]/SKILL.md` is accessible as
`/start:[name]` (e.g. `/start:specify`, `/start:implement`).

To add a new workflow entry point, add a skill directory under `plugins/start/skills/`.

### Editing Agents

1. Agents are markdown files in `plugins/team/agents/[role]/`
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

The primary workflow: `/start:specify` → `/start:validate` → `/start:implement` → `/start:review`

Specifications live in `.start/specs/[NNN]-[name]/` (legacy: `docs/specs/`):
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
| Agents | `plugins/team/agents/the-*/` | `the-[role]/[activity].md` |
| Output Styles | `plugins/*/output-styles/*.md` | lowercase-kebab (e.g., `the-startup.md`) |
| Specs | `.start/specs/[NNN]-*/` | 3-digit ID prefix |

## Publishing

The repository is a Claude Code marketplace. Publishing happens via:
1. Push to `main` branch
2. GitHub Actions workflow creates release
3. Users install via `./install.sh` or `/plugin marketplace add MMoMM-org/the-custom-startup`
