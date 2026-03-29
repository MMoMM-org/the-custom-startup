@AGENTS.md

## Testing Skills During Development

When developing new skills in `plugins/tcs-helper/skills/`, they are not automatically available in Claude Code sessions. To make a skill available for testing:

1. Copy the skill directory to **both** locations:
   ```bash
   # Plugin cache (runtime)
   cp -r plugins/tcs-helper/skills/<skill-name> \
     ~/.claude/plugins/cache/the-custom-startup/tcs-helper/2.0.0/skills/

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
  ~/.claude/plugins/cache/the-custom-startup/tcs-helper/2.0.0/skills/<skill-name>/
cp -r plugins/tcs-helper/skills/<skill-name>/* \
  ~/.claude/plugins/marketplaces/the-custom-startup/plugins/tcs-helper/skills/<skill-name>/
```
