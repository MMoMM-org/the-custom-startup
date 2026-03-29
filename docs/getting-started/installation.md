# Installation

## Understanding Scopes

Claude Code configuration operates at three levels. The install wizard asks which level you want:

| Scope | Location | Applies to |
|---|---|---|
| **Global** | `~/.claude/` | All Claude Code sessions on this machine |
| **Project** | A dedicated project directory (e.g., `~/projects/myproject/`) | All repos that reference this project via `@` includes in their CLAUDE.md |
| **Repo** | The repo root | Only this repository |

Plugins always install globally (Claude Code marketplace requirement), but you can enable or disable them at any scope. The install wizard handles this for you.

> **Note:** "Project" scope is *not* the repo level — it is a separate directory for cross-repo configuration. A repo opts into a project by including its CLAUDE.md via `@` reference (e.g., `@~/projects/myproject/CLAUDE.md`).

---

## Recommended: Install Script

The easiest way to install is via the interactive install wizard — it sets up the plugins, statusline, multi-AI templates, startup configuration, and optionally Satori in one step:

```bash
curl -fsSL https://raw.githubusercontent.com/MMoMM-org/the-custom-startup/main/install.sh | bash
```

The wizard lets you choose:

- **Install target** — global (all Claude sessions), current repo, or a custom path
- **Plugins** — tcs-workflow only, tcs-team only, both (recommended), or all four including tcs-helper and tcs-patterns
- **Output style** — The Startup (high-energy, delivery-focused) or The ScaleUp (structured, process-oriented)
- **Specs directory** — the directory name where specification files (PRDs, SDDs, plans) will be stored, written to `.claude/startup.toml`
- **Satori** *(optional)* — MCP gateway for session context capture and context reduction. Builds the submodule, registers the MCP server, and optionally installs context-capture hooks.
- **Multi-AI templates** — prompt templates and utility scripts for working with Claude.ai, Perplexity, and the spec export/import workflow
- **Statusline** — optional shell prompt integration showing current workflow context

To uninstall:

```bash
curl -fsSL https://raw.githubusercontent.com/MMoMM-org/the-custom-startup/main/uninstall.sh | bash
```

---

## Manual Installation via Claude Code Marketplace

If you prefer to install via the Claude Code plugin marketplace, start `claude` and run:

```bash
/plugin marketplace add MMoMM-org/the-custom-startup
/plugin install tcs-workflow@the-custom-startup    # core workflow — required
/plugin install tcs-team@the-custom-startup        # specialist agents — optional
/plugin install tcs-helper@the-custom-startup      # skill authoring tools — optional
/plugin install tcs-patterns@the-custom-startup    # domain pattern skills — optional
```

`tcs-workflow` is the only required plugin. The others extend it:

| Plugin | Purpose | Required |
|---|---|---|
| `tcs-workflow@the-custom-startup` | Core workflow orchestration, XDD spec skills, output styles | Yes |
| `tcs-team@the-custom-startup` | 8 specialist agent roles (analyst, architect, developer, etc.) | No |
| `tcs-helper@the-custom-startup` | Skill authoring, Memory Bank, git workflows, project onboarding | No |
| `tcs-patterns@the-custom-startup` | Domain pattern skills (DDD, hexagonal, testing, TypeScript, and more) — see [tcs-patterns guide](../guides/tcs-patterns.md) | No |

Marketplace installation only installs the plugins. The following extras are **not** set up automatically and need to be configured manually.

### Statusline

Download a statusline script from [`scripts/`](../../scripts/) and configure it. See [statusline.md](../statusline.md) for full setup instructions including configuration options and the `statusline.toml` format.

### Startup Configuration

Create `.claude/startup.toml` in your project (or `~/.claude/startup.toml` for a global default) to configure spec paths and other options. The install script generates this file automatically; for the expected format and available keys see [workflow.md](../workflow.md).

### Output Style

Set your preferred output style once inside Claude:

```bash
/output-style "tcs-workflow:The Startup"   # high-energy, delivery-focused
/output-style "tcs-workflow:The ScaleUp"   # structured, process-oriented
```

See [output-styles.md](../output-styles.md) for a comparison of both styles.

### Multi-AI Templates

Download prompt templates from [`docs/templates/`](../templates/) manually if you want to use the multi-AI workflow. See [multi-ai-workflow.md](../multi-ai-workflow.md) for how to use them.

### Memory Bank (requires tcs-helper)

To use the Memory Bank, run `/setup` inside Claude Code in any repo you want to provision. This creates the `docs/ai/memory/` directory structure, generates scope-appropriate CLAUDE.md files, and installs the learning-capture hooks. The install script does **not** do this automatically — `/setup` is a per-repo operation.

See [concepts — Memory Bank](../about/concepts.md#memory-bank) for details on scopes, categories, and the promotion lifecycle.
