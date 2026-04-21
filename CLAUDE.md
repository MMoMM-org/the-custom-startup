# the-custom-startup

@~/Kouzou/standards/general.md

## Core Philosophy
TCS plugin ecosystem — Claude Code plugins, skills, agents, and workflow tooling.

@AGENTS.md

## Memory & Context
@docs/ai/memory/memory.md

## Routing Rules
<!-- Run /memory-add to capture learnings. Routing reference: docs/ai/memory/routing-reference.md -->
- Personal/workflow corrections → global (~/.claude/includes/)
- Repo conventions/style → docs/ai/memory/general.md
- Tool/CI/build knowledge → docs/ai/memory/tools.md
- Domain/business rules → docs/ai/memory/domain.md
- Architectural decisions → docs/ai/memory/decisions.md
- Current focus/blockers → docs/ai/memory/context.md
- Bugs/fixes → docs/ai/memory/troubleshooting.md

## Testing Skills During Development

When developing new skills in `plugins/tcs-helper/skills/`, they are not automatically available in Claude Code sessions. To make a skill available for testing:

1. Copy the skill directory to **both** locations:
   ```bash
   # Plugin cache (runtime)
   cp -r plugins/tcs-helper/skills/<skill-name> \
     ~/.claude/plugins/cache/the-custom-startup/tcs-helper/*/skills/

   # Marketplace source (discovery index)
   cp -r plugins/tcs-helper/skills/<skill-name> \
     ~/.claude/plugins/marketplaces/the-custom-startup/plugins/tcs-helper/skills/
   ```
2. Start a **new Claude Code session** — skills are indexed at startup.
3. The skill should appear in the `/` menu and be invocable.

Both locations are required. Cache-only does not work — Claude Code validates against the marketplace source.

After testing, sync any changes back:
```bash
cp -r plugins/tcs-helper/skills/<skill-name>/* \
  ~/.claude/plugins/cache/the-custom-startup/tcs-helper/*/skills/<skill-name>/
cp -r plugins/tcs-helper/skills/<skill-name>/* \
  ~/.claude/plugins/marketplaces/the-custom-startup/plugins/tcs-helper/skills/<skill-name>/
```
