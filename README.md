```
████████ ██   ██ ███████
   ██    ██   ██ ██
   ██    ███████ █████
   ██    ██   ██ ██
   ██    ██   ██ ███████

 ██████ ██    ██ ███████ ████████  ██████  ███    ███
██      ██    ██ ██         ██    ██    ██ ████  ████
██      ██    ██ ███████    ██    ██    ██ ██ ████ ██
██      ██    ██      ██    ██    ██    ██ ██  ██  ██
 ██████  ██████  ███████    ██     ██████  ██      ██

███████ ████████  █████  ██████  ████████ ██   ██ ██████
██         ██    ██   ██ ██   ██    ██    ██   ██ ██   ██
███████    ██    ███████ ██████     ██    ██   ██ ██████
     ██    ██    ██   ██ ██   ██    ██    ██   ██ ██
███████    ██    ██   ██ ██   ██    ██     █████  ██
```

> A customized fork of [the-startup](https://github.com/rsmdt/the-startup) by [@rsmdt](https://github.com/rsmdt).
> See [What's different](#whats-different) for changes made in this fork.

---

## What is The Agentic Startup?

**The Agentic Startup** is a multi-agent AI framework that makes Claude Code work like a startup team. Create comprehensive specifications before coding, then execute with parallel specialist agents — expert developers, architects, and engineers working together to turn your ideas into shipped code.

10 slash commands across 3 phases. Specify first, then build with confidence.

---

## Quick Start

```bash
curl -fsSL https://raw.githubusercontent.com/MMoMM-org/the-custom-startup/main/install.sh | bash
```

The interactive wizard guides you through: install target · plugins · output style · statusline.

After installation:

```bash
/specify Add user authentication with OAuth support
/implement 001
```

→ Full workflow: [docs/workflow.md](docs/workflow.md)

---

## What's different

This fork extends the original with:

- **Interactive install wizard** — global / repo / other path, plugin selection, output style, statusline with conflict detection, confirm before writing anything
- **3 statusline variants** — standard, enhanced (token budget bar via ccusage), Starship bridge — each configurable via `statusline.toml`
- **Configurable specs directory** — `.claude/startup.toml` tells skills and scripts where your specs live; fallback chain keeps backward compatibility
- **Multi-AI workflow** — export specs as prompts for Claude.ai or Perplexity, import results back as PRD/SDD
- **Script naming consistency** — all statusline scripts share the `the-custom-startup-*` prefix

---

## Documentation

→ [docs/index.md](docs/index.md) — full documentation index
