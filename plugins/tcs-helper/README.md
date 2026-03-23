# tcs-helper Plugin

Helper tools for The Custom Agentic Startup — skill authoring, agent discovery, and plugin development utilities.

This plugin is **optional**. Install it if you want to create or maintain skills and agents for Claude Code plugins.

## Skills

### `tcs-helper:skill-author`

Guided workflow for creating, auditing, and converting Claude Code skills. Covers the full lifecycle: duplicate detection, PICS structure, model selection, agent discovery, verification, and deployment.

→ Invocable as `/tcs-helper:skill-author`

## Scripts

### `scripts/get-specs-dir.sh`

Returns the configured specs directory for the current project. Reads `.claude/startup.toml` (project-local, then global) and falls back through the standard chain.

```bash
SPECS_DIR=$(~/.claude/plugins/cache/the-custom-startup/tcs-helper/scripts/get-specs-dir.sh)
```

### `scripts/find-agents.sh`

Discovers all installed Claude Code agents across `~/.claude/agents/` and plugin caches. Returns agent names and descriptions for use by `skill-author` when determining whether a skill should delegate to an agent.

## Attribution

The `skill-author` skill incorporates patterns and techniques from [obra/superpowers](https://github.com/obra/superpowers) — specifically the TDD-for-skills approach, Claude Search Optimization (CSO) guidelines, token efficiency techniques, and rationalization-proofing patterns. Used under MIT License.

## Installation

The install wizard (`install.sh`) offers `tcs-helper` as an optional third plugin. To install manually:

```bash
/plugin install tcs-helper@the-custom-startup
```
