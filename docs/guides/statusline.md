# Statusline

Claude Code supports a custom status line — a bar at the bottom of the terminal that updates after each assistant message. This project ships four variants and an interactive configurator.

Jump to: [Standard](#standard) · [Enhanced](#enhanced) · [Configuration](#configuration) · [Starship](#starship)

## Quick setup

**Interactive wizard (recommended):**

```bash
./scripts/the-custom-startup-configure-statusline.sh
```

The wizard checks your environment, lets you pick a variant and installation scope (global or per-repo), and writes the config.

**Or install directly from GitHub:**

```bash
curl -fsSL https://raw.githubusercontent.com/MMoMM-org/the-custom-startup/main/scripts/the-custom-startup-configure-statusline.sh | bash
```

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

```
💰 ██░░░░░░░░  9% $0.42    ← green: below warn threshold (70%)
💰 ███████░░░ 74% $1.91    ← yellow: at or above warn
💰 ██████████ 95% $2.55    ← red: at or above danger threshold (90%)
```

Token limits per 5-hour window (configurable):

| Plan | Limit |
|---|---|
| Pro ($20/mo) | ~28,450 tokens |
| Max 5x ($100/mo) | ~57,000 tokens |
| Max 20x ($200/mo) | ~142,500 tokens |

These values are estimates. The Pro limit was measured (`inputTokens + outputTokens` vs `/usage`); Max 5x and Max 20x are extrapolated proportionally and have not been independently verified. If the bar seems off, override the limit in `statusline.toml`:

```toml
# Calibrate: take your raw token count from ccusage and divide by the /usage percentage.
# Example: 9,388 tokens at 33% → token_limit = 28450
token_limit = 28450
```

Set your plan in `statusline.toml`:

```toml
plan = "pro"   # pro | max5x | max20x | api | auto
```

The bar can also show session cost instead of tokens — set `budget_mode = "cost"` in `statusline.toml`. Cost thresholds are also estimates and vary by usage pattern.

---

## Configuration

All variants share a single config file: `statusline.toml`.

**Global** (applies to all sessions):
```
~/.config/the-custom-startup/statusline.toml
```

**Per-repo** (overrides global for a specific project):
```
<repo>/.claude/statusline.toml
```

The per-repo file only needs the keys you want to override — everything else falls through to the global config.

**Script locations** (after installation):

| Install scope | Scripts | Config |
|---|---|---|
| Global | `~/.config/the-custom-startup/` | `~/.config/the-custom-startup/statusline.toml` |
| Per-repo | `<repo>/.claude/` | `<repo>/.claude/statusline.toml` |

### Full reference

```toml
# Subscription plan — drives token limit and cost thresholds
# auto | pro | max5x | max20x | api
plan          = "auto"
fallback_plan = "pro"

# Manual token limit override (skips plan lookup)
# All plan limits are estimates — override here if the bar seems off.
# Calibrate: raw_tokens / (/usage percent / 100)  e.g. 9388 / 0.33 = 28450
# token_limit = 28450

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
| Green | Below warn threshold |
| Yellow | At or above warn |
| Red | At or above danger |

---

## Starship

> Based on an idea from [r/ClaudeCode — Use Your Starship Prompt as the Claude Code Status Line](https://www.reddit.com/r/ClaudeCode/comments/1r81675/use_your_starship_prompt_as_the_claude_code/). This project's version extends the original approach with additional variables, the configurator, and `statusline.toml` support.

Uses your existing [Starship](https://starship.rs/) prompt as the status line, extended with Claude-specific data (model, context, session, cost, duration). One config, two contexts.

**Script:** `the-custom-startup-statusline-starship.sh`
**Dependencies:** `starship`, `jq`

A small bridge script reads the Claude Code JSON payload, exports relevant fields as environment variables, then calls `starship prompt`. Starship's `env_var` modules pick up those variables and render them alongside your existing prompt modules.

Your normal shell prompt is unaffected — the `env_var` modules are invisible when the variables are not set (i.e. outside Claude Code).

#### Requirements

- [Starship](https://starship.rs/) installed and configured
- `jq` (`brew install jq` / `apt install jq`)

#### Quick setup

**Step 1 — Install the bridge script**

Run the configurator and choose **Starship**:

```bash
./scripts/the-custom-startup-configure-statusline.sh
```

Or install manually — copy `scripts/the-custom-startup-statusline-starship.sh` to a permanent location and make it executable:

```bash
cp scripts/the-custom-startup-statusline-starship.sh \
   ~/.config/the-custom-startup/the-custom-startup-statusline-starship.sh
chmod +x ~/.config/the-custom-startup/the-custom-startup-statusline-starship.sh
```

**Step 2 — Point Claude Code at the script**

Add to `~/.claude/settings.json`:

```json
{
  "statusLine": {
    "type": "command",
    "command": "~/.config/the-custom-startup/the-custom-startup-statusline-starship.sh"
  }
}
```

**Step 3 — Add env_var modules to `~/.config/starship.toml`**

These modules only render inside Claude Code (when the variables are set):

```toml
# Claude Code — model and context
[env_var.CLAUDE_MODEL]
variable = "CLAUDE_MODEL"
format   = "[\\[$env_value\\]]($style) "
style    = "bold cyan"

[env_var.CLAUDE_CONTEXT]
variable = "CLAUDE_CONTEXT"
format   = "[$env_value]($style) "
style    = "yellow"

# Session name (/rename) or first 8 chars of session ID
[env_var.CLAUDE_SESSION]
variable = "CLAUDE_SESSION"
format   = "[$env_value]($style) "
style    = "purple"

# Session cost
[env_var.CLAUDE_COST]
variable = "CLAUDE_COST"
format   = "[$env_value]($style) "
style    = "green"

# Session duration
[env_var.CLAUDE_DURATION]
variable = "CLAUDE_DURATION"
format   = "[$env_value]($style)"
style    = "dimmed white"
```

**Step 4 — Reference the modules in your format string**

Append the Claude modules at the end of your existing `format`:

```toml
format = """
$directory$git_branch$git_status$all\
${env_var.CLAUDE_MODEL}${env_var.CLAUDE_CONTEXT}\
${env_var.CLAUDE_SESSION}${env_var.CLAUDE_COST}${env_var.CLAUDE_DURATION}
"""
```

Only add the modules you want. Each is independently optional.

#### What you get

```
my-project on  main [$!?]
❯ [Opus 4.6] 42%  my-session  $1.23  14m 30s
```

The same `starship.toml` powers both your shell prompt and your Claude Code status line.

#### Variables exported by the bridge script

| Variable | Content | Example |
|---|---|---|
| `CLAUDE_MODEL` | Model display name | `Opus 4.6` |
| `CLAUDE_CONTEXT` | Context usage percentage | `42%` |
| `CLAUDE_SESSION` | Session name or ID prefix | `my-session` |
| `CLAUDE_COST` | Session cost | `$1.23` |
| `CLAUDE_DURATION` | Session duration | `14m 30s` |
| `CLAUDE_LINES` | Lines added/removed | `+156/-23` |

#### Optional: separate config for the statusline

If you want a different layout in Claude Code than in your shell (e.g. single-line compact vs. multi-line), point the bridge script at a dedicated Starship config. Edit the `STARSHIP_CONFIG_FILE` variable at the top of the bridge script:

```bash
STARSHIP_CONFIG_FILE="$HOME/.config/starship-statusline.toml"
```

Then create that file with only the modules and format you want for the statusline.

#### Why env_var instead of custom commands

Starship's `[custom.name]` modules spawn a subprocess per module. `[env_var.NAME]` modules read an environment variable directly — no subshell, no overhead. Since the bridge script already exports the values, `env_var` is the right choice.

#### Key implementation detail: STARSHIP_SHELL=

The bridge script calls `starship prompt` with `STARSHIP_SHELL=` (empty string). Without this, Starship wraps ANSI color codes in shell-specific escape sequences (`%{...%}` for zsh, `\[...\]` for bash) intended for prompt rendering. Claude Code's status line needs raw ANSI output, not shell prompt sequences. The empty `STARSHIP_SHELL` disables these wrappers.

#### Testing without Claude Code

Pipe mock JSON to verify output:

```bash
echo '{"model":{"display_name":"Opus 4.6"},"session_name":"test","context_window":{"used_percentage":42},"cost":{"total_cost_usd":1.23,"total_duration_ms":870000}}' \
  | ~/.config/the-custom-startup/the-custom-startup-statusline-starship.sh
```

---

### Original Reddit approach (DIY reference)

> Original post: [r/ClaudeCode — Use Your Starship Prompt as the Claude Code Status Line](https://www.reddit.com/r/ClaudeCode/comments/1r81675/use_your_starship_prompt_as_the_claude_code/)

If you prefer a minimal hand-rolled setup without the configurator, the original Reddit post walks through creating a bridge script from scratch. The core technique is identical — export env vars from the JSON payload, call `starship prompt` — but with a smaller default variable set (model, context, session only). The post also covers how to extend it step by step with cost, duration, and lines-changed tracking.

The shipped Starship variant above already includes all of these extensions and adds `statusline.toml` support, so the Reddit approach is mainly useful as a learning reference or if you want full control over a hand-crafted script.

---

## Per-repo installation

Each repository can have its own statusline script and config. Useful when different projects need different plans, layouts, or variants.

Run the configurator from inside the repo and choose **Repo** scope:

```bash
cd /path/to/your-repo
./scripts/the-custom-startup-configure-statusline.sh --repo
```

This installs the script and config to `<repo>/.claude/` and updates `<repo>/.claude/settings.json`. The global config is unaffected.

---

## Switching variants

Re-run the configurator at any time:

```bash
./scripts/the-custom-startup-configure-statusline.sh
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
  "output_style": {"name": "tcs-workflow:The Startup"}
}' | ./scripts/the-custom-startup-statusline-enhanced.sh
```
