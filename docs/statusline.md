# Statusline

Claude Code supports a custom status line — a bar at the bottom of the terminal that updates after each assistant message. This project ships three variants and an interactive configurator.

## Quick setup

```bash
./scripts/configure-statusline.sh
```

The wizard checks your environment, lets you pick a variant and installation scope (global or per-repo), and writes the config.

---

## Variants

### Standard

Single-line, placeholder-based statusline. Lightweight, no external dependencies beyond `jq`.

```
📁 ~/C/p/my-project ⎇ main*  🤖 Opus 4.6 (The Startup)  🧠 ⣿⣿⡇⠀⠀ 50%  🕐 14m  💰 $1.23  ? for shortcuts
```

**Script:** `the-custom-startup-statusline-standard.sh`
**Dependencies:** `jq`
**Config key:** `format` (placeholder string)

Customize by editing the `format` key in `statusline.toml`:

```toml
format = "<path> <branch>  <model>  <context>  <session>  <help>"
```

Available placeholders:

| Placeholder | Output | Example |
|---|---|---|
| `<path>` | Abbreviated directory | `📁 ~/C/p/project` |
| `<branch>` | Git branch, `*` if dirty | `⎇ main*` |
| `<model>` | Model and output style | `🤖 Opus 4.6 (The Startup)` |
| `<context>` | Braille context bar + % | `🧠 ⣿⣿⡇⠀⠀ 50%` |
| `<session>` | Duration and cost | `🕐 14m  💰 $1.23` |
| `<lines>` | Lines added/removed | `+156/-23` |
| `<spec>` | Active spec ID | `📋 005` |
| `<help>` | Help hint | `? for shortcuts` |

---

### Enhanced

Two-line statusline with richer git context, a token budget bar (via [ccusage](https://github.com/ryoppippi/ccusage)), and clickable OSC 8 hyperlinks to the remote repository.

```
[Opus 4.6] | 📁 my-project | 🔗 my-project | 🌿 main +2~1
🧠 ██████░░░░ 62%  |  ⏱ 14m 30s  |  💰 ██░░░░░░░░ 9% $1.23  |  ⏳ 137m left
```

**Script:** `the-custom-startup-statusline-enhanced.sh`
**Dependencies:** `jq`, `git`, `bun` + `ccusage` (for token budget bar)

#### Line 1 — identity

| Segment | Description |
|---|---|
| `[Opus 4.6]` | Current model |
| `📁 my-project` | Current directory (basename) |
| `🔗 my-project` | Clickable hyperlink to remote repo (OSC 8) |
| `🌿 main +2~1` | Git branch, staged (+) and modified (~) file counts |

#### Line 2 — metrics

| Segment | Description |
|---|---|
| `🧠 ██████░░░░ 62%` | Context window usage bar |
| `⏱ 14m 30s` | Session duration |
| `💰 ██░░░░░░░░ 9% $1.23` | Budget bar + block cost |
| `⏳ 137m left` | Estimated time remaining in billing block |

#### Token budget bar

The budget bar tracks how much of your plan's token allowance has been used in the current 5-hour billing window. It uses `inputTokens + outputTokens` from the active [ccusage](https://github.com/ryoppippi/ccusage) block — cache read tokens are excluded because they don't represent new content generation and would distort the percentage.

Token limits per 5-hour window (configurable):

| Plan | Limit |
|---|---|
| Pro ($20/mo) | ~44,000 tokens |
| Max 5x ($100/mo) | ~88,000 tokens |
| Max 20x ($200/mo) | ~220,000 tokens |

Set your plan in `statusline.toml`:

```toml
plan = "pro"   # pro | max5x | max20x | api | auto
```

Or override the limit directly:

```toml
token_limit = 44000
```

The bar can also show session cost instead of tokens — set `budget_mode = "cost"` in `statusline.toml`.

---

### Starship

Uses your existing [Starship](https://starship.rs/) prompt as the status line, extended with Claude-specific data (model, context, session, cost, duration). One config, two contexts.

**Script:** `the-custom-startup-statusline-starship.sh`
**Dependencies:** `starship`, `jq`
**Setup guide:** [`statusline-starship.md`](statusline-starship.md)

---

## Configuration

All variants share a single config file: `statusline.toml`.

**Global** (applies to all sessions):
```
~/.config/the-agentic-startup/statusline.toml
```

**Per-repo** (overrides global for a specific project):
```
<repo>/.claude/statusline.toml
```

The per-repo file only needs the keys you want to override — everything else falls through to the global config.

### Full reference

```toml
# Subscription plan — drives token limit and cost thresholds
# auto | pro | max5x | max20x | api
plan          = "auto"
fallback_plan = "pro"

# Manual token limit override (skips plan lookup)
# token_limit = 44000

# Budget bar mode
# "token" — tokens used vs plan limit  (enhanced default)
# "cost"  — session cost vs threshold  (standard default)
budget_mode = "token"

# Format string (standard variant only)
format = "<path> <branch>  <model>  <context>  <session>  <help>"

# Cache TTLs in seconds
ccusage_cache_ttl = 60   # billing block data
git_cache_ttl     = 15   # branch / dirty state

# Display toggles (enhanced variant)
show_budget_bar  = true
show_context_bar = true
show_duration    = true
show_git         = true
show_remote_url  = true

[thresholds.context]
warn   = 70   # % — yellow
danger = 90   # % — red

[thresholds.budget]
warn   = 70   # % — yellow
danger = 90   # % — red

# Explicit cost thresholds (optional — overrides plan defaults)
[thresholds.cost]
# warn   = 2.00
# danger = 5.00
```

### Color thresholds

Both bars use the same color scheme:

| Color | Meaning |
|---|---|
| 🟢 Green | Below warn threshold |
| 🟡 Yellow | At or above warn |
| 🔴 Red | At or above danger |

---

## Per-repo installation

Each repository can have its own statusline script and config. Useful when different projects need different plans, layouts, or variants.

Run the configurator from inside the repo and choose **Repo** scope:

```bash
cd /path/to/your-repo
./scripts/configure-statusline.sh --repo
```

This installs the script and config to `<repo>/.claude/` and updates `<repo>/.claude/settings.json`. The global config is unaffected.

---

## Switching variants

Re-run the configurator at any time:

```bash
./scripts/configure-statusline.sh
```

It detects the existing configuration and asks before overwriting.

---

## Caching

The enhanced variant caches slow operations to stay under the 50ms performance target:

| Cache | TTL | Stores |
|---|---|---|
| Git | 15s | Branch name, staged/modified counts, remote URL |
| ccusage | 60s | Active block tokens, cost, remaining minutes |

Cache files live in `/tmp/tcs-statusline-*`. They are keyed by directory path so different repos have independent caches. Adjust TTLs in `statusline.toml`.

---

## Testing

Pipe mock JSON to any script to verify output without running a full Claude session:

```bash
echo '{
  "model": {"display_name": "Opus 4.6"},
  "workspace": {"current_dir": "/home/user/my-project"},
  "context_window": {"used_percentage": 42, "context_window_size": 200000,
    "current_usage": {"input_tokens": 84000, "cache_read_input_tokens": 0,
                      "cache_creation_input_tokens": 0}},
  "cost": {"total_cost_usd": 1.23, "total_duration_ms": 870000,
           "total_lines_added": 156, "total_lines_removed": 23},
  "output_style": {"name": "start:The Startup"}
}' | ./scripts/the-custom-startup-statusline-enhanced.sh
```
