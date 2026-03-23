# Installation

## Recommended: Install Script

The easiest way to install is via the interactive install script — it sets up the plugins, statusline, multi-AI templates, and startup configuration in one step:

```bash
curl -fsSL https://raw.githubusercontent.com/MMoMM-org/the-custom-startup/main/install.sh | bash
```

The wizard guides you through: install target (global / repo / custom path) · which plugins (start / team / both) · output style · multi-AI templates · statusline variant.

To uninstall:

```bash
curl -fsSL https://raw.githubusercontent.com/MMoMM-org/the-custom-startup/main/uninstall.sh | bash
```

---

## Manual Installation via Claude Code Marketplace

If you prefer to install via the Claude Code plugin marketplace, start `claude` and run:

```bash
/plugin marketplace add MMoMM-org/the-custom-startup
/plugin install start@the-custom-startup   # core workflow
/plugin install team@the-custom-startup    # specialist agents (optional)
```

Marketplace installation only installs the plugins. The following extras are **not** set up automatically and need to be configured manually.

### Statusline

Download a statusline script from [`scripts/`](../scripts/) and configure it. See [statusline.md](statusline.md) for full setup instructions including configuration options and the `statusline.toml` format.

### Startup Configuration

Create `.claude/startup.toml` in your project (or `~/.claude/startup.toml` for a global default) to configure spec paths and other options. The install script generates this file automatically; for the expected format and available keys see [workflow.md](workflow.md).

### Output Style

Set your preferred output style once inside Claude:

```bash
/output-style "start:The Startup"   # high-energy, fast execution
/output-style "start:The ScaleUp"   # calm confidence, educational
```

See [output-styles.md](output-styles.md) for a comparison of both styles.

### Multi-AI Templates

Download prompt templates from [`docs/templates/`](templates/) manually if you want to use the multi-AI workflow. See [multi-ai-workflow.md](multi-ai-workflow.md) for how to use them.
