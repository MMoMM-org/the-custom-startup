Original from https://www.reddit.com/r/ClaudeCode/comments/1r81675/use_your_starship_prompt_as_the_claude_code

# Use Your Starship Prompt as the Claude Code Status Line

Claude Code has a customizable status line (a bar at the bottom of the terminal that updates after each assistant message.) By default it's blank. You can point it at any shell script that reads JSON from stdin and prints text to stdout.

There is a lot of stuff out there on how to use and customize status lines, not going into detail here.

Since I am using Starship https://starship.rs/ (which you should too), I wanted to have the same status line in CC.

## WHY?

Same config, same look, extended with Claude-specific data like context window usage, model name, and session name.

After trying a few plugins and stuff I was unable to understand, I did it from scratch. It is simple, transparent, and builds upon what you already have. No plugins, no extra tooling, only a small bridge script and a few lines of TOML.

I let CC generate this article and steps, based on the work performed. I have read the article fully and made numerous changes and updates. You can use this as a starting point for CC to have one build for you..

## Why Starship
I am using it.

Starship is a cross-shell prompt written in Rust. It works with bash, zsh, fish, PowerShell, and others. You configure it once in `~/.config/starship.toml` and it renders the same prompt everywhere.

What makes it popular:

- **Fast**. Written in Rust, renders in single-digit milliseconds. No perceptible lag when you hit Enter.

- **One config for all shells.** TOML-based configuration that works identically across bash, zsh, fish, and others. Switch shells without rewriting your prompt.

- **Batteries included.** Built-in modules for git status, language versions (Go, Python, Node, Rust, etc.), Kubernetes context, AWS profile, Docker, and dozens more. Each activates automatically when relevant — enter a Go project and the Go version appears, leave and it disappears.

- **Extensible with custom commands.** The `[custom.name]` and `[env_var.NAME]` modules let you display anything — environment variables, shell command output, or computed values. This is the mechanism we use for Claude Code integration.

- **Minimal by default.** Shows only what's relevant to your current directory and environment. No clutter.

## How the Claude Code Status Line Works

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

Full schema is in the status line docs. https://code.claude.com/docs/en/statusline

## The Approach

The idea is simple:

A bridge script reads the Claude Code JSON, exports relevant fields as environment variables, then calls `starship prompt`.

Starship's `[env_var.NAME]` modules pick up those variables and render them alongside your existing prompt modules.

The `env_var` modules only render when the variable is set, so your normal shell prompt is unaffected.

No separate starship config needed. Your existing `~/.config/starship.toml` serves double duty.

### Step 1: The Bridge Script

Create `~/.claude/statusline.sh`:

```
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

- `CLAUDE_CONTEXT` formats the percentage as 35%

- Calls `starship prompt` with `STARSHIP_SHELL=` (empty) to suppress shell-specific prompt escape wrappers like zsh's `%{...%}` — Claude Code needs raw ANSI output

Make it executable:

```
chmod +x ~/.claude/statusline.sh
```

**Prerequisite:** `jq` must be installed (`brew install jq` on macOS, `apt install jq` on Debian/Ubuntu).

### Step 2: Add env_var Modules to Starship

Add these modules to your `~/.config/starship.toml`:

```
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

```
format = """$directory$git_branch$git_status$all${env_var.CLAUDE_MODEL}${env_var.CLAUDE_CONTEXT}${env_var.CLAUDE_SESSION}"""
```

Append them at the end so they appear after your existing prompt modules.

#### Why env_var Instead of custom Commands

Starship offers two ways to display dynamic data:

- `[custom.name]` — runs a shell command, captures its stdout. Each module spawns a subprocess.

- `[env_var.NAME]` — reads an environment variable directly. No subprocess.

Since the bridge script already exports the values as env vars, `env_var` is the right choice. It's faster (no subshell overhead per module) and simpler (no `when` conditions, `shell` config, or command strings). The modules are automatically invisible in your normal shell prompt because the variables aren't set outside the bridge script.

### Step 3: Configure Claude Code

Add the status line to `~/.claude/settings.json`:

```
{
  "statusLine": {
    "type": "command",
    "command": "~/.claude/statusline.sh"
  }
}
```

The status line updates after each assistant message. Changes to the script or starship config take effect on the next update.

#### The Result

Your Claude Code status line now renders your full starship prompt — directory, git branch, git status, kubernetes context, language versions, whatever you have configured — plus the Claude-specific additions at the end:

```
my-project on  main [$!?] 󰠳 k3d-local ()
❯ [Opus 4.6] 35% my-session-name
```

The same `starship.toml` powers both your shell prompt and your Claude Code status line. One config, two contexts.

#### Extending It

You can expose more fields from the JSON payload. The bridge script has access to everything Claude Code sends. Some ideas:

**Add cost tracking:**

```
export CLAUDE_COST=$(printf '$%.2f' "$(echo "$input" | jq -r '.cost.total_cost_usd // 0')")
```

```
[env_var.CLAUDE_COST]
variable = "CLAUDE_COST"
format = "[$env_value]($style) "
style = "yellow"
```

**Add session duration:**

```
DURATION_MS=$(echo "$input" | jq -r '.cost.total_duration_ms // 0')
MINS=$((DURATION_MS / 60000))
SECS=$(((DURATION_MS % 60000) / 1000))
export CLAUDE_DURATION="${MINS}m${SECS}s"
```

```
[env_var.CLAUDE_DURATION]
variable = "CLAUDE_DURATION"
format = "[$env_value]($style)"
style = "dimmed white"
```

**Add lines changed:**

```
ADDED=$(echo "$input" | jq -r '.cost.total_lines_added // 0')
REMOVED=$(echo "$input" | jq -r '.cost.total_lines_removed // 0')
export CLAUDE_LINES="+${ADDED}/-${REMOVED}"
```

```
[env_var.CLAUDE_LINES]
variable = "CLAUDE_LINES"
format = "[$env_value]($style)"
style = "green"
```

Add the corresponding `${env_var.NAME}` references to your format string and they'll appear in the status line.

## Tips

- **Test without Claude Code.** Pipe mock JSON to the script to verify output:

```
echo '{"model":{"display_name":"Opus"},"session_name":"test","context_window":{"used_percentage":42}}' | ~/.claude/statusline.sh
```

- **Keep it fast**. The status line runs after every assistant message. Starship itself is fast, but if your config has expensive custom commands, they add up. `env_var` modules have zero overhead.

- `STARSHIP_SHELL=` **is the key trick.** Without it, starship wraps ANSI color codes in shell-specific escape sequences `(%{...%}` for zsh, `\[...\]` for bash) meant for prompt rendering. Claude Code's status line is not a shell prompt — it needs raw ANSI output. Setting `STARSHIP_SHELL` to an empty string disables these wrappers.

- **Separate config (optional)**. If you want a different layout for the status line than your shell prompt, use `STARSHIP_CONFIG=~/.config/starship-statusline.toml` starship prompt in the bridge script instead. This lets you have a compact single-line status line while keeping a multi-line shell prompt.