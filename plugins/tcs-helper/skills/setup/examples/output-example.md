# /tcs-helper:setup — Example Output

## Input
Running setup on a new TypeScript repo at `/Volumes/Moon/Coding/my-api/` with no existing
`docs/ai/memory/` structure and no CLAUDE.md.

## Output

```
🚀 tcs-helper:setup — Provisioning memory hierarchy for my-api

Detecting stack... TypeScript (found tsconfig.json + package.json)

Creating docs/ai/memory/:
  ✓ docs/ai/memory/general.md        (from templates/memory-general.md)
  ✓ docs/ai/memory/tools.md          (from templates/memory-tools.md)
  ✓ docs/ai/memory/domain.md         (from templates/memory-domain.md)
  ✓ docs/ai/memory/decisions.md      (from templates/memory-decisions.md)
  ✓ docs/ai/memory/context.md        (from templates/memory-context.md)
  ✓ docs/ai/memory/troubleshooting.md(from templates/memory-troubleshooting.md)
  ✓ docs/ai/memory/memory.md         (index file)

Creating CLAUDE.md:
  ✓ CLAUDE.md (from templates/stacks/typescript.md — strict mode, import order, no any)

Hooks (native — loaded automatically when plugin is enabled):
  ✓ UserPromptSubmit — queue capture hook active
  ✓ SessionStart — pending learnings reminder active
  ✓ PreCompact — auto-backup hook active
  ✓ PostToolUse (Bash) — post-commit reminder active

Done. Memory hierarchy provisioned. Start a session and corrections will be captured automatically.
Run /memory-add to process the queue, /memory-sync to keep imports fresh.
```
