# Plugins

The Agentic Startup is distributed as two Claude Code marketplace plugins.

---

## start plugin (`start@the-startup`)

Core workflow orchestration. Provides the 10 user-invocable slash commands, 5 autonomous skills, and 2 output styles.

**Install:**
```bash
/plugin install start@the-startup
```

### Skills

| Category | Skills |
|----------|--------|
| Build | `/specify`, `/validate`, `/implement` |
| Quality | `/test`, `/review` |
| Maintain | `/document`, `/analyze`, `/refactor`, `/debug` |
| Setup | `/constitution` |

**User-invocable:** the 10 above — you trigger them directly.
**Autonomous:** `specify-requirements`, `specify-solution`, `specify-plan`, `specify-meta`, `brainstorm` — loaded by orchestrator skills behind the scenes.

→ Full reference: [`plugins/start/README.md`](../plugins/start/README.md)

### Output Styles

Two output styles ship with the start plugin:

- **The Startup** — high energy, delivery-focused, demo day mentality
- **The ScaleUp** — calm confidence, educational insights, engineering depth

Switch anytime: `/output-style start:The Startup`

→ See [output-styles.md](output-styles.md) for comparison.

---

## team plugin (`team@the-startup`) — optional

Specialized agent library. 8 roles, 15 activity-based agents. Used by the output styles (via Agent tool) and directly by you for complex multi-domain work.

**Install:**
```bash
/plugin install team@the-startup
```

Enable experimental multi-agent collaboration (Agent Teams):
```json
// ~/.claude/settings.json or .claude/settings.json
{
  "env": { "CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS": "1" }
}
```
The installer can configure this for you.

### Agent Roster

| Role | Activity Agents |
|------|----------------|
| **the-chief** | Complexity assessment, routing, parallel orchestration |
| **the-analyst** | `research-product` — market analysis, requirements, prioritization |
| **the-architect** | `design-system`, `review-security`, `review-robustness`, `review-compatibility` |
| **the-developer** | `build-feature`, `optimize-performance` |
| **the-devops** | `build-platform`, `monitor-production` |
| **the-designer** | `research-user`, `design-interaction`, `design-visual` |
| **the-tester** | `test-strategy` |
| **the-meta-agent** | Agent design, validation, generation |

Each agent is scoped to a specific activity — not a broad role. This follows the activity-based architecture pattern: agents specialize in *what they do*, not *who they are*.

→ Full reference: [`plugins/team/README.md`](../plugins/team/README.md)

→ Design principles: [philosophy.md](philosophy.md)

---

## Installing from this fork

```bash
# Add the marketplace for this fork
/plugin marketplace add MMoMM-org/the-custom-startup

# Then install
/plugin install start@the-custom-startup
/plugin install team@the-custom-startup
```

Or use the interactive installer:
```bash
curl -fsSL https://raw.githubusercontent.com/MMoMM-org/the-custom-startup/main/install.sh | bash
```
