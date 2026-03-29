---
name: setup
description: "Use when setting up a new TCS repo, adding the memory system to an existing project, or re-running onboarding to repair a missing docs/ai/memory/ structure or CLAUDE.md hierarchy."
user-invocable: true
argument-hint: ""
allowed-tools: Read, Write, Edit, Bash
---

## Persona

**Active skill: tcs-helper:setup**

Provision the TCS memory system for this repo.

## Interface

```
State {
  stack: string[]          // detected from manifest files
  hasClaudeMd: boolean
  hasMemoryStructure: boolean
  ciSystem: string | null
}
```

## Constraints

**Always:**
- Non-destructive: preserve existing CLAUDE.md content.
- Idempotent: running twice produces no duplicates.
- Report every file created or modified.

**Never:**
- Overwrite existing @imports or custom sections in CLAUDE.md.
- Install hooks without user confirmation — the preview in Step 2 covers this.

## Workflow

### 1. Detect stack and existing state

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

### 2. Preview structure

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

### 3. Generate memory structure

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

### 4. Generate CLAUDE.md files

For each of: root, src/, test/, docs/, docs/ai/
- If file doesn't exist: copy from template and apply stack overrides
- If file exists: Read it, add memory section non-destructively (don't overwrite existing content)
  - Check if `@docs/ai/memory/memory.md` already present — skip if so
  - Check if Routing Rules section exists — skip if so
  - Add both sections after existing content

Stack override application: read `templates/stacks/<detected-stack>.md` and append to `src/CLAUDE.md`.

### 5. Install hooks

```bash
HOOKS="${CLAUDE_PLUGIN_ROOT}/hooks/hooks.json"
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/merge_hooks.py" "$HOOKS" --scope r --set-cleanup-period \
  || echo "WARNING: hook installation failed — run manually after setup"
```

Report which hooks were added vs already present.

### 6. Optional extras

> "Setup complete! Optional additions:
> 1. Create docs/adr/ for Architecture Decision Records
> 2. Add format-on-save hook for TypeScript (biome)
> 3. Install tcs-patterns domain pattern skills — run: /plugin install tcs-patterns@the-custom-startup
>    Includes: ddd, hexagonal, functional, event-driven, api-design, typescript-strict,
>    mutation-testing, frontend-testing, react-testing, node-service, python-project,
>    go-idiomatic, twelve-factor, mcp-server, obsidian-plugin
> Skip optional steps? [yes/no/select]"

### 7. Summary

Show:
- Files created/modified
- Hooks installed
- YOLO=true usage instructions
- "Run /memory-add to capture learnings, /memory-sync to verify structure"


