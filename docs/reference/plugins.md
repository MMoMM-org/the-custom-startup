# Plugins

The Custom Agentic Startup is distributed as six Claude Code marketplace plugins. The [interactive install script](../getting-started/installation.md) lets you choose which plugins to install, or you can install individual plugins manually using the commands below.

---

## tcs-workflow

```
/plugin install tcs-workflow@the-custom-startup
```

The core workflow plugin. It gives you a spec-driven, test-verified development lifecycle through 20 skills covering everything from specification and validation through implementation, review, and documentation. All other TCS plugins integrate with and extend the workflow that tcs-workflow defines.

20 skills — full reference: [skills.md](skills.md)

Two output styles ship with tcs-workflow:

| Style | Voice | Best for |
|-------|-------|----------|
| **The Startup** | High-energy, fast | Sprints, execution |
| **The ScaleUp** | Calm, educational | Learning, onboarding |

Switch anytime: `/output-style tcs-workflow:the-startup`

---

## tcs-team

```
/plugin install tcs-team@the-custom-startup
```

Adds 15 activity-based agents across 8 specialist roles. They activate automatically when tcs-workflow skills delegate work that requires a specialist — you do not invoke them directly. Each agent brings focused expertise, tooling permissions, and decision protocols for its domain.

15 agents across 8 roles — full reference: [agents.md](agents.md)

| Role | Agents | Focus |
|------|--------|-------|
| **The Chief** | 1 | Complexity assessment, routing, parallel coordination |
| **The Analyst** | 1 | Requirements, prioritization, product research |
| **The Architect** | 4 | System design, security, robustness, compatibility |
| **The Developer** | 2 | Feature implementation, performance optimization |
| **The Tester** | 1 | Test strategy, load testing, coverage |
| **The Designer** | 3 | User research, interaction design, accessibility |
| **The DevOps** | 2 | Infrastructure, CI/CD, monitoring |
| **The Meta Agent** | 1 | Agent design and generation |

---

## tcs-helper

```
/plugin install tcs-helper@the-custom-startup
```

Optional. Provides skill authoring tools, the **[Memory Bank](../about/concepts.md#memory-bank)** for structured learning and context minimization, and git workflow helpers. Install this plugin when you want to build on the framework, author new skills, or add persistent project knowledge to your repos.

**Skill authoring:**

| Skill | What it does |
|-------|-------------|
| `/skill-author` | Create, audit, or convert Claude Code skills — PICS structure, model selection, agent discovery, TDD Iron Law, verification |
| `/skill-evaluate` | Evaluate a skill's quality before importing or using |
| `/skill-import` | Fetch and install a single skill from any GitHub repo without installing the full plugin |

**Memory Bank:**

| Skill | What it does |
|-------|-------------|
| `/setup` | Provision `docs/ai/memory/` + CLAUDE.md hierarchy in a new repo; installs hooks |
| `/memory-add` | Capture session learnings and route them to the correct scope and category file |
| `/memory-sync` | Keep `@imports` and the memory index in sync |
| `/memory-cleanup` | Archive resolved issues, prune stale entries |
| `/memory-promote` | Promote domain patterns from memory files to reusable skills |
| `/memory-claude-md-optimize` | Audit, score, and migrate flat CLAUDE.md files into Memory Bank; replace @-imports with descriptive references |

**Git workflow:**

| Skill | What it does |
|-------|-------------|
| `/git-worktree` | Manage git worktrees for isolated parallel branch work |
| `/finish-branch` | Branch completion workflow — merge, PR, keep, or discard |
| `/docs` | Fetch and cache current Claude Code documentation on demand |

**Hooks (natively loaded from `hooks/hooks.json` when plugin is enabled):**

| Event | Hook | Purpose |
|-------|------|---------|
| `UserPromptSubmit` | `capture_learning.py` | Detect corrections and learnings (English + CJK), queue them |
| `SessionStart` | `session_start_reminder.py` | Show pending queue count at session open |
| `PreCompact` | `check_learnings.py` | Back up queue before context compaction |
| `PostToolUse(Bash)` | `post_commit_reminder.py` | Remind to run `/memory-add` after git commit; capture persistent tool errors |

**Themes (auto-discovered from `themes/` when plugin is enabled):**

| Theme | What it does |
|-------|-------------|
| `TCS Dark` | Dark base with an Apple-palette accent — blue `claude` highlight (response bullet, spinner, branding) plus system green/red/orange status colors. Select via `/theme`; a newly added theme appears after the next Claude Code restart. |

---

## tcs-patterns

```
/plugin install tcs-patterns@the-custom-startup
```

Optional. 21 pattern skills covering architecture, security, API design, testing, language platforms, DevOps, and integrations. Install selectively — each skill activates on trigger terms and provides interactive, opinionated guidance for its domain without requiring the whole plugin. You can install the full plugin and only use the skills relevant to your stack.

21 skills — full reference: [../guides/tcs-patterns.md](../guides/tcs-patterns.md)

| Category | Skills |
|----------|--------|
| **Architecture** | `ddd` · `hexagonal` · `functional` · `event-driven` · `event-sourcing` |
| **API & Types** | `api-design` · `typescript-strict` |
| **Security** | `secure-oauth-oidc` · `bff-entry-points` |
| **Testing** | `testing` · `mutation-testing` · `frontend-testing` · `react-testing` · `test-design-reviewer` |
| **Platforms** | `node-service` · `python-project` · `go-idiomatic` |
| **DevOps** | `twelve-factor` · `observability` |
| **Integrations** | `mcp-server` · `obsidian-plugin` |

Invoke any skill by name: `/ddd`, `/hexagonal`, `/typescript-strict`, etc.

---

## tcs-git-helpers

```
/plugin install tcs-git-helpers@the-custom-startup
```

Optional. Machine-enforces the recurring git mistakes Claude makes across repos — pushes to closed PRs, branching off unfinished work, squash-merge resume, destructive operations, and worktree-exit data loss. It runs invisibly through hooks; you notice it only on a denial or the SessionStart brief.

| Skill | What it does |
|-------|-------------|
| `/git-setup` | Per-repo install — writes `.githooks/`, sets `core.hooksPath`, detects and aborts on Husky/lefthook/pre-commit/simple-git-hooks conflicts |
| `/git-audit` | Per-repo health check — branch state, stale branches, override audit; `--cleanup` to delete stale branches, `--overrides` to review the consumption log |

| Event | Hooks | Purpose |
|-------|-------|---------|
| `PreToolUse` | Bash / Edit / Write / ExitWorktree | Deny 14+ destructive patterns, closed-PR pushes, squash-merge resume, unfinished-branch creation, and worktree exit with uncommitted work |
| `PostToolUse` | git / gh nudges | Soft reminders after `git checkout -b`, `gh pr create`, `gh pr merge`, `git rebase`, `git stash pop` |
| `SessionStart` | branch brief | One-line awareness brief — branch, dirty/clean, ahead/behind, stale-merged count |

Optional setup flags: `--with-branch-protection` (GitHub single-coder preset) · `--with-gha` (PR-title check workflow).

---

## tcs-issues

```
/plugin install tcs-issues@the-custom-startup
```

Optional. GitHub issue lifecycle plus native sub-issue (parent/child) management. Complements `/pickup` — which reads the GitHub Projects board — by writing to it: creating issues onto the board and linking the issue graph. Requires an authenticated `gh` CLI.

| Skill | What it does |
|-------|-------------|
| `/issue` | Create, list, close, and comment on issues. New issues are placed on the repo's Project (v2) board with a status and labels. Confirms before every write. |
| `/link-issue` | Link / unlink native sub-issues (parent ↔ child) and list an issue's children and parent epic, via the GitHub GraphQL sub-issue API. |
