---
name: docs
description: "Fetch and cache current Claude Code documentation on demand. Use when you need to refresh knowledge on Claude Code hooks, MCP, tools, permissions, settings, agents, or skills. Checks for an MCP docs server before fetching directly."
user-invocable: true
argument-hint: "[topic: hooks | mcp | tools | permissions | settings | agents | skills | all] [--refresh]"
allowed-tools: Bash, WebFetch, Read, Write
---

# docs

Fetch and cache Claude Code documentation, keeping it locally available for up to 7 days.

## Interface

```
TopicEntry {
  name: string
  url: string
  cacheFile: string
}

State {
  topic = $ARGUMENTS          // parsed topic name; "all" fetches every topic
  refresh: boolean            // true when --refresh flag present
  cacheDir: "docs/ai/external/claude"
  cacheFile: string           // cacheDir + "/" + topic + ".md"
  mcpServer: string | null    // result of MCP check
  fresh: boolean              // cache younger than 7 days
}
```

**In scope:** Fetching and caching the seven known Claude Code documentation topics listed below.

**Out of scope:** Other Anthropic docs, third-party docs, or arbitrary URL fetching.

## Constraints

**Always:**
- Write a timestamp header to every cache file so staleness is visible at a glance.
- List available topics and exit cleanly when the topic is unknown or missing.
- Delegate to the MCP docs server when one is detected — do not duplicate the fetch.

**Never:**
- Fetch from the network when a fresh, valid cache exists (unless `--refresh` is set).
- Create `docs/ai/external/` — it is already in `.gitignore`; just write the file.

## Topics Reference

| Topic | URL |
|-------|-----|
| hooks | https://docs.anthropic.com/en/docs/claude-code/hooks |
| mcp | https://docs.anthropic.com/en/docs/claude-code/mcp |
| tools | https://docs.anthropic.com/en/docs/claude-code/tools |
| permissions | https://docs.anthropic.com/en/docs/claude-code/security |
| settings | https://docs.anthropic.com/en/docs/claude-code/settings |
| agents | https://docs.anthropic.com/en/docs/claude-code/agents |
| skills | https://docs.anthropic.com/en/docs/claude-code/skills |

## Workflow

### Step 1 — Parse arguments

Extract `topic` and `--refresh` flag from `$ARGUMENTS`:
- Strip `--refresh` from the argument string; set `refresh: true` if present.
- The remaining token is the topic name (lowercase, trimmed).
- If topic is empty or not in the Topics Reference table → print the table above and exit.

### Step 2 — Check cache

```bash
CACHE_DIR="docs/ai/external/claude"
CACHE_FILE="${CACHE_DIR}/${topic}.md"
mkdir -p "$CACHE_DIR"

# Fresh = file exists AND modified within the last 7 days
if [ -f "$CACHE_FILE" ] && [ "$(find "$CACHE_FILE" -mtime -7 2>/dev/null)" ]; then
  echo "fresh"
fi
```

If fresh and `refresh` is false: Read the cache file and present its content. Exit.

### Step 3 — MCP check

```bash
MCP_DOCS=$(claude mcp list 2>/dev/null | grep -i "docs\|documentation" | head -1)
```

If `$MCP_DOCS` is non-empty: delegate the request to that MCP docs server. Exit after delegation.

### Step 4 — Fetch and cache

For the resolved topic URL (from the Topics Reference table):
1. Use WebFetch to retrieve the page content.
2. Prepend a timestamp header block:
   ```
   <!-- Cached: YYYY-MM-DD HH:MM UTC -->
   <!-- Source: {url} -->
   <!-- Refresh with: /docs {topic} --refresh -->
   ```
3. Write the combined content to `$CACHE_FILE` using the Write tool.
4. Present the fetched content.

### Step 5 — `all` topic

When topic is `all`: iterate through every entry in the Topics Reference table sequentially, running Steps 2–4 for each. Report a summary table at the end:

```
Topic        Status        Cache File
───────────  ────────────  ─────────────────────────────────
hooks        fetched       docs/ai/external/claude/hooks.md
mcp          cached        docs/ai/external/claude/mcp.md
...
```

### Entry Point

match (topic) {
  "all"                  => steps 2–4 for each topic, then step 5 summary
  known topic, fresh     => step 2 (serve cache)
  known topic, stale     => step 3, then step 4
  unknown / empty        => list topics and exit
}
