# Statusline

Claude Code supports a custom status line — a bar at the bottom of the terminal that updates after each assistant message. This project ships four variants and an interactive configurator.

Jump to: [Standard](#standard) · [Enhanced](#enhanced) · [Starship](#starship) · [Starship Reddit](#starship-reddit-variant) · [Configuration](#configuration)

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

### Starship

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

### Starship Reddit Variant

> Original post: [r/ClaudeCode — Use Your Starship Prompt as the Claude Code Status Line](https://www.reddit.com/r/ClaudeCode/comments/1r81675/use_your_starship_prompt_as_the_claude_code/)

This variant documents the minimal DIY approach from the original Reddit post — a hand-crafted bridge script placed at `~/.claude/statusline.sh`, without the configurator. It covers a smaller default variable set and includes the author's notes on extending it with cost, duration, and lines-changed tracking.

#### How Claude Code's status line works

Claude Code's status line runs a shell command you configure in `~/.claude/settings.json`. After each assistant message, it pipes a JSON payload to your command's stdin containing session data: model name, context window usage, session ID, cost, token counts, and more.

Your command reads the JSON, does whatever processing it needs, and prints text to stdout. Claude Code displays that text at the bottom of the terminal.

The key fields in the JSON payload:

| Field | Description |
|---|---|
| `model.display_name` | Current model (e.g. "Opus 4.6") |
| `context_window.used_percentage` | How full the context window is |
| `session_name` | Name set via /rename (if set) |
| `session_id` | Unique session UUID |
| `cost.total_cost_usd` | Session cost so far |
| `cost.total_duration_ms` | Wall-clock time since session start |

Full schema: https://code.claude.com/docs/en/statusline

#### Step 1: The bridge script

Create `~/.claude/statusline.sh`:

```bash
#!/bin/bash
input=$(cat)

export CLAUDE_MODEL=$(echo "$input" | jq -r '.model.display_name // "?"')
export CLAUDE_SESSION=$(echo "$input" | jq -r '.session_name // empty // .session_id[:8]')
export CLAUDE_CONTEXT=$(printf '%s%%' "$(echo "$input" | jq -r '.context_window.used_percentage // 0' | cut -d. -f1)")

STARSHIP_SHELL= starship prompt
```

What it does:

- Reads the JSON payload from stdin
- Extracts three fields into environment variables using `jq`
- `CLAUDE_SESSION` prefers the session name (set via `/rename`), falls back to the first 8 characters of the session ID
- `CLAUDE_CONTEXT` formats the percentage as `35%`
- Calls `starship prompt` with `STARSHIP_SHELL=` (empty) to suppress shell-specific prompt escape wrappers like zsh's `%{...%}` — Claude Code needs raw ANSI output

Make it executable:

```bash
chmod +x ~/.claude/statusline.sh
```

**Prerequisite:** `jq` must be installed (`brew install jq` on macOS, `apt install jq` on Debian/Ubuntu).

#### Step 2: Add env_var modules to Starship

Add these modules to your `~/.config/starship.toml`:

```toml
# Claude Code statusline — env_var modules (no subshells, only visible when set)
[env_var.CLAUDE_MODEL]
variable = "CLAUDE_MODEL"
format = "[\\[$env_value\\]]($style) "
style = "bold cyan"

[env_var.CLAUDE_CONTEXT]
variable = "CLAUDE_CONTEXT"
format = "[$env_value]($style) "
style = "peach"

[env_var.CLAUDE_SESSION]
variable = "CLAUDE_SESSION"
format = "[$env_value]($style)"
style = "purple"
```

Then reference them in your `format` string:

```toml
format = """$directory$git_branch$git_status$all${env_var.CLAUDE_MODEL}${env_var.CLAUDE_CONTEXT}${env_var.CLAUDE_SESSION}"""
```

Append them at the end so they appear after your existing prompt modules.

#### Why env_var instead of custom commands

Starship offers two ways to display dynamic data:

- `[custom.name]` — runs a shell command, captures its stdout. Each module spawns a subprocess.
- `[env_var.NAME]` — reads an environment variable directly. No subprocess.

Since the bridge script already exports the values as env vars, `env_var` is the right choice. It's faster (no subshell overhead per module) and simpler (no `when` conditions, `shell` config, or command strings). The modules are automatically invisible in your normal shell prompt because the variables aren't set outside the bridge script.

#### Step 3: Configure Claude Code

Add the status line to `~/.claude/settings.json`:

```json
{
  "statusLine": {
    "type": "command",
    "command": "~/.claude/statusline.sh"
  }
}
```

The status line updates after each assistant message. Changes to the script or starship config take effect on the next update.

#### The result

```
my-project on  main [$!?] 󰠳 k3d-local ()
❯ [Opus 4.6] 35% my-session-name
```

The same `starship.toml` powers both your shell prompt and your Claude Code status line. One config, two contexts.

#### Extending the bridge script

You can expose more fields from the JSON payload. The bridge script has access to everything Claude Code sends.

**Add cost tracking:**

```bash
export CLAUDE_COST=$(printf '$%.2f' "$(echo "$input" | jq -r '.cost.total_cost_usd // 0')")
```

```toml
[env_var.CLAUDE_COST]
variable = "CLAUDE_COST"
format = "[$env_value]($style) "
style = "yellow"
```

**Add session duration:**

```bash
DURATION_MS=$(echo "$input" | jq -r '.cost.total_duration_ms // 0')
MINS=$((DURATION_MS / 60000))
SECS=$(((DURATION_MS % 60000) / 1000))
export CLAUDE_DURATION="${MINS}m${SECS}s"
```

```toml
[env_var.CLAUDE_DURATION]
variable = "CLAUDE_DURATION"
format = "[$env_value]($style)"
style = "dimmed white"
```

**Add lines changed:**

```bash
ADDED=$(echo "$input" | jq -r '.cost.total_lines_added // 0')
REMOVED=$(echo "$input" | jq -r '.cost.total_lines_removed // 0')
export CLAUDE_LINES="+${ADDED}/-${REMOVED}"
```

```toml
[env_var.CLAUDE_LINES]
variable = "CLAUDE_LINES"
format = "[$env_value]($style)"
style = "green"
```

Add the corresponding `${env_var.NAME}` references to your format string and they'll appear in the status line.

#### Tips

- **Test without Claude Code.** Pipe mock JSON to the script to verify output:

```bash
echo '{"model":{"display_name":"Opus"},"session_name":"test","context_window":{"used_percentage":42}}' | ~/.claude/statusline.sh
```

- **Keep it fast.** The status line runs after every assistant message. Starship itself is fast, but if your config has expensive custom commands, they add up. `env_var` modules have zero overhead.

- `STARSHIP_SHELL=` **is the key trick.** Without it, starship wraps ANSI color codes in shell-specific escape sequences (`%{...%}` for zsh, `\[...\]` for bash) meant for prompt rendering. Claude Code's status line is not a shell prompt — it needs raw ANSI output. Setting `STARSHIP_SHELL` to an empty string disables these wrappers.

- **Separate config (optional).** If you want a different layout for the status line than your shell prompt, use `STARSHIP_CONFIG=~/.config/starship-statusline.toml starship prompt` in the bridge script instead. This lets you have a compact single-line status line while keeping a multi-line shell prompt.

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
