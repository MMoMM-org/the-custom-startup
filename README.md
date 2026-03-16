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

 █████  ██████  ███████ ███   ██ ████████ ██  ██████
██   ██ ██      ██      ████  ██    ██    ██ ██
███████ ██  ███ █████   ██ ██ ██    ██    ██ ██
██   ██ ██   ██ ██      ██  ████    ██    ██ ██
██   ██  ██████ ███████ ██   ███    ██    ██  ██████

███████ ████████  █████  ██████  ████████ ██   ██ ██████
██         ██    ██   ██ ██   ██    ██    ██   ██ ██   ██
███████    ██    ███████ ██████     ██    ██   ██ ██████
     ██    ██    ██   ██ ██   ██    ██    ██   ██ ██
███████    ██    ██   ██ ██   ██    ██     █████  ██
```

> A customized fork of [the-startup](https://github.com/rsmdt/the-startup) by [@rsmdt](https://github.com/rsmdt).
> See [What's different](#whats-different) for changes made in this fork.

---

## What is The Custom Agentic Startup?

**The Custom Agentic Startup** is a fork of [the-startup](https://github.com/rsmdt/the-startup) — a multi-agent AI framework that makes Claude Code work like a startup team. Create comprehensive specifications before coding, then execute with parallel specialist agents — expert developers, architects, and engineers working together to turn your ideas into shipped code.

10 slash commands across 3 phases. Specify first, then build with confidence.

This fork adds an interactive install wizard, three statusline variants with a live token budget bar, multi-AI workflow support, and configurable spec paths. See [What's different](#whats-different) for details.

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

---

## License

Original work © [Rudolf Schmidt](https://github.com/rsmdt) — MIT License. See [LICENSE](LICENSE) for the full original license text.

New parts added in this fork (install wizard, statusline scripts, multi-AI workflow, export/import scripts) © Marcus Breiden — MIT License.

Starship statusline integration based on an idea from [Reddit r/ClaudeCode](https://www.reddit.com/r/ClaudeCode/comments/1r81675/use_your_starship_prompt_as_the_claude_code/).
