# tcs-helper Plugin

Helper tools for The Custom Agentic Startup — skill authoring, agent discovery, and plugin development utilities.

This plugin is **optional**. Install it if you want to create or maintain skills and agents for Claude Code plugins.

## Skills

### `tcs-helper:skill-author`

Guided workflow for creating, auditing, and converting Claude Code skills. Covers the full lifecycle: duplicate detection, PICS structure, model selection, agent discovery, verification, and deployment.

→ Invocable as `/skill-author`

### `tcs-helper:memory-claude-md-optimize`

Audits, scores, and migrates flat CLAUDE.md files into the structured Memory Bank system. Replaces eager @-imports with descriptive references, categorizes content into 6 memory categories, and measures context window savings. Non-destructive with backups and user review before applying.

→ Invocable as `/memory-claude-md-optimize [--dry-run] [--scope global|project|repo]`

## Scripts

### `skills/skill-author/find-agents.sh`

Discovers all installed Claude Code agents across `~/.claude/agents/` and plugin caches. Returns agent names and descriptions for use by `skill-author` when determining whether a skill should delegate to an agent.

```bash
find ~/.claude/plugins/cache -path "*/tcs-helper/skills/skill-author/find-agents.sh" -type f 2>/dev/null | head -1 | xargs bash
# or directly if version is known:
~/.claude/plugins/cache/the-custom-startup/tcs-helper/x.y.z/skills/skill-author/find-agents.sh
```

## Attribution

The `skill-author` skill incorporates patterns and techniques from [obra/superpowers](https://github.com/obra/superpowers) — specifically the TDD-for-skills approach, Claude Search Optimization (CSO) guidelines, token efficiency techniques, and rationalization-proofing patterns. Used under MIT License.

## Installation

The install wizard (`install.sh`) offers `tcs-helper` as an optional third plugin. To install manually:

```bash
/plugin marketplace add MMoMM-org/the-custom-startup
/plugin install helper@the-custom-startup
```
