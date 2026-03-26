---
name: setup
description: One-shot project onboarding for TCS repos. Detects tech stack, generates docs/ai/memory/ structure and lean CLAUDE.md files, installs memory hooks. Run once in a new repo or to add memory structure to an existing one.
user-invocable: true
argument-hint: ""
allowed-tools: Read, Write, Edit, Bash
---

# setup

Provision the TCS memory system for this repo.

## Workflow

### Step 1 — Detect stack and existing state (code)

```bash
# Stack detection — check for manifest files
[ -f package.json ] && echo "node"
[ -f go.mod ] && echo "go"
[ -f pyproject.toml ] || [ -f setup.py ] && echo "python"
# Check Cloudflare / Convex specifics
grep -l "cloudflare" package.json 2>/dev/null && echo "cloudflare"
grep -l "convex" package.json 2>/dev/null && echo "convex"
# CI detection
[ -d .github/workflows ] && echo "github-actions"
# Existing structure
[ -f CLAUDE.md ] && echo "has-claude-md"
[ -d docs/ai/memory ] && echo "has-memory-structure"
```

### Step 2 — Preview structure (AI — show before acting)

> "I'll create the following structure:
>
> docs/ai/memory/
>   memory.md (index)
>   general.md, tools.md, domain.md, decisions.md, context.md, troubleshooting.md
>
> CLAUDE.md (will ADD memory section — existing content preserved)
> src/CLAUDE.md, test/CLAUDE.md, docs/CLAUDE.md, docs/ai/CLAUDE.md
>
> Stack detected: TypeScript — will apply typescript.md overrides to src/CLAUDE.md
>
> Proceed? [yes/no]"

### Step 3 — Generate memory structure (code)

```bash
# Create directories
mkdir -p docs/ai/memory

# Copy category templates
TMPL="${CLAUDE_PLUGIN_ROOT}/templates"
for cat in general tools domain decisions context troubleshooting; do
  cp "$TMPL/memory-${cat}.md" "docs/ai/memory/${cat}.md"
done
cp "$TMPL/memory-index.md" "docs/ai/memory/memory.md"
# Replace placeholder with actual repo name
REPO_NAME=$(basename "$(pwd)")
sed -i.bak "s/\[Repo Name\]/${REPO_NAME}/g" docs/ai/memory/*.md
rm -f docs/ai/memory/*.bak
```

### Step 4 — Generate CLAUDE.md files (code + AI for existing CLAUDE.md)

For each of: root, src/, test/, docs/, docs/ai/
- If file doesn't exist: copy from template and apply stack overrides
- If file exists: Read it, add memory section non-destructively (don't overwrite existing content)
  - Check if `@docs/ai/memory/memory.md` already present — skip if so
  - Check if Routing Rules section exists — skip if so
  - Add both sections after existing content

Stack override application: read `templates/stacks/<detected-stack>.md` and append to `src/CLAUDE.md`.

### Step 5 — Install hooks (code)

```bash
SETTINGS="${HOME}/.claude/settings.json"
HOOKS="${CLAUDE_PLUGIN_ROOT}/hooks/hooks.json"
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/merge_hooks.py" "$HOOKS" "$SETTINGS" --set-cleanup-period
```

Report which hooks were added vs already present.

### Step 6 — Optional extras (AI — AskUserQuestion)

> "Setup complete! Optional additions:
> 1. Create docs/adr/ for Architecture Decision Records
> 2. Add format-on-save hook for TypeScript (biome)
> Skip optional steps? [yes/no/select]"

### Step 7 — Summary

Show:
- Files created/modified
- Hooks installed
- YOLO=true usage instructions
- "Run /memory-add to capture learnings, /memory-sync to verify structure"

## Always
- Non-destructive: never overwrite existing CLAUDE.md content
- Idempotent: running twice produces no duplicates
- Report every file created/modified

## Never
- Overwrite existing @imports or custom sections in CLAUDE.md
- Install hooks without user confirmation (the preview in Step 2 covers this)
