# Starship Statusline Integration

> **Source:** [Reddit r/ClaudeCode — Use Your Starship Prompt as the Claude Code Status Line](https://www.reddit.com/r/ClaudeCode/comments/1r81675/use_your_starship_prompt_as_the_claude_code/)
> The full original post is preserved at [`statusline-starship-reddit.md`](statusline-starship-reddit.md).

Use your existing [Starship](https://starship.rs/) prompt as the Claude Code status line — same config, same look, extended with Claude-specific data.

## How it works

A small bridge script reads the Claude Code JSON payload, exports relevant fields as environment variables, then calls `starship prompt`. Starship's `env_var` modules pick up those variables and render them alongside your existing prompt modules.

Your normal shell prompt is unaffected — the `env_var` modules are invisible when the variables are not set (i.e. outside Claude Code).

## Requirements

- [Starship](https://starship.rs/) installed and configured
- `jq` (`brew install jq` / `apt install jq`)

## Quick setup

### Step 1 — Install the bridge script

Run the configurator and choose **Starship**:

```bash
./scripts/configure-statusline.sh
```

Or install manually — copy `scripts/the-custom-startup-statusline-starship.sh` to a permanent location and make it executable:

```bash
cp scripts/the-custom-startup-statusline-starship.sh \
   ~/.config/the-agentic-startup/the-custom-startup-statusline-starship.sh
chmod +x ~/.config/the-agentic-startup/the-custom-startup-statusline-starship.sh
```

### Step 2 — Point Claude Code at the script

Add to `~/.claude/settings.json`:

```json
{
  "statusLine": {
    "type": "command",
    "command": "~/.config/the-agentic-startup/the-custom-startup-statusline-starship.sh"
  }
}
```

### Step 3 — Add env_var modules to `~/.config/starship.toml`

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

### Step 4 — Reference the modules in your format string

Append the Claude modules at the end of your existing `format`:

```toml
format = """
$directory$git_branch$git_status$all\
${env_var.CLAUDE_MODEL}${env_var.CLAUDE_CONTEXT}\
${env_var.CLAUDE_SESSION}${env_var.CLAUDE_COST}${env_var.CLAUDE_DURATION}
"""
```

Only add the modules you want. Each is independently optional.

## What you get

```
my-project on  main [$!?]
❯ [Opus 4.6] 42%  my-session  $1.23  14m 30s
```

The same `starship.toml` powers both your shell prompt and your Claude Code status line.

## Variables exported by the bridge script

| Variable | Content | Example |
|---|---|---|
| `CLAUDE_MODEL` | Model display name | `Opus 4.6` |
| `CLAUDE_CONTEXT` | Context usage percentage | `42%` |
| `CLAUDE_SESSION` | Session name or ID prefix | `my-session` |
| `CLAUDE_COST` | Session cost | `$1.23` |
| `CLAUDE_DURATION` | Session duration | `14m 30s` |
| `CLAUDE_LINES` | Lines added/removed | `+156/-23` |

## Optional: separate config for the statusline

If you want a different layout in Claude Code than in your shell (e.g. single-line compact vs. multi-line), point the bridge script at a dedicated Starship config. Edit the `STARSHIP_CONFIG_FILE` variable at the top of the bridge script:

```bash
STARSHIP_CONFIG_FILE="$HOME/.config/starship-statusline.toml"
```

Then create that file with only the modules and format you want for the statusline.

## Why env_var instead of custom commands

Starship's `[custom.name]` modules spawn a subprocess per module. `[env_var.NAME]` modules read an environment variable directly — no subshell, no overhead. Since the bridge script already exports the values, `env_var` is the right choice.

## Key implementation detail: STARSHIP_SHELL=

The bridge script calls `starship prompt` with `STARSHIP_SHELL=` (empty string). Without this, Starship wraps ANSI color codes in shell-specific escape sequences (`%{...%}` for zsh, `\[...\]` for bash) intended for prompt rendering. Claude Code's status line needs raw ANSI output, not shell prompt sequences. The empty `STARSHIP_SHELL` disables these wrappers.

## Testing without Claude Code

Pipe mock JSON to verify output:

```bash
echo '{"model":{"display_name":"Opus 4.6"},"session_name":"test","context_window":{"used_percentage":42},"cost":{"total_cost_usd":1.23,"total_duration_ms":870000}}' \
  | ~/.config/the-agentic-startup/the-custom-startup-statusline-starship.sh
```
