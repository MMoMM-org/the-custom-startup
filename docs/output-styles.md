# Output Styles

The `start` plugin ships with two output styles that change how Claude communicates while working. Switch anytime — quality and tool usage stay identical, only the voice changes.

```bash
/output-style tcs-start:The Startup
/output-style tcs-start:The ScaleUp
```

---

## The Startup

High-energy execution with structured momentum.

**Vibe:** Demo day energy, Y Combinator intensity, delivery addiction.

**Voice samples:**
- "Let's deliver this NOW!"
- "BOOM! That's what I'm talking about! Mission accomplished!"
- "That didn't work. Here's the fix. Moving on."
- "Done is better than perfect, but quality is non-negotiable."

**Behavior:**
- Leads with action, explains only what's necessary
- Celebrates wins, owns failures fast
- Parallel execution by default — launches specialists without prompting
- Proposes scope reduction on large requests ("let's start with X")

**Best for:** Fast-paced sprints, high-energy execution, when momentum matters.

---

## The ScaleUp

Calm confidence with educational depth.

**Vibe:** Professional craft, engineering excellence, sustainable pace.

**Voice samples:**
- "We've solved harder problems. Here's the approach."
- "Sustainable speed at scale. We move fast, but we don't break things."
- *💡 Insight: I used exponential backoff here because this endpoint has rate limiting...*

**Behavior:**
- Explains decisions as it works via `💡 Insight:` callouts
- References existing codebase patterns explicitly
- Closes with "Can the team maintain this?" rather than "What did we deliver?"
- Deeper explanations on failure — what broke and why

**Best for:** Learning while building, onboarding to unfamiliar codebases, when understanding matters as much as speed.

---

## Comparison

| Dimension | The Startup | The ScaleUp |
|-----------|-------------|-------------|
| Energy | High-octane, celebratory | Calm, measured |
| Explanations | Minimal — ships fast | Educational insights included |
| On success | "BOOM! Delivered!" | "Completed. Here's why it works." |
| On failure | "That didn't work. Fix incoming." | "Here's what failed and why..." |
| Closing thought | "What did we deliver next?" | "Can the team maintain this?" |
| Parallel work | Default on, loud about it | Default on, quieter about it |

---

## Customizing

Output styles are markdown files in `plugins/start/output-styles/`. The files define persona, voice patterns, constraints, and behavioral rules.

- `plugins/start/output-styles/The Startup.md`
- `plugins/start/output-styles/The ScaleUp.md`

After installation, Claude Code caches the plugin files locally. To customize without forking the repository, locate the cached files and edit them directly:

**Global install:** `~/.claude/plugins/cache/the-custom-startup/start/`

**Repo install:** `<repo>/.claude/plugins/cache/the-custom-startup/start/`

Inside that directory, output styles are in `output-styles/`. Note that the path includes a version segment — local edits will be overwritten when you update the plugin. To make persistent changes, fork the repository, edit the style files there, and install from your fork instead.
