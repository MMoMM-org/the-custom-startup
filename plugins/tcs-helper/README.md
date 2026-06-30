# tcs-helper Plugin

Helper tools for The Custom Agentic Startup — memory system, skill authoring, and project onboarding.

See [CHANGELOG.md](CHANGELOG.md) for version history. Hooks load natively from `hooks/hooks.json` via Claude Code's plugin system — no manual installation step.

## Skills

### Memory Bank

| Skill | Description |
|-------|-------------|
| `/memory-setup` | Provision `docs/ai/memory/` + CLAUDE.md hierarchy in a new repo |
| `/memory-add` | Capture session learnings and route to the correct scope and category file |
| `/memory-sync` | Keep `@imports` and memory index in sync |
| `/memory-cleanup` | Archive resolved issues, prune stale entries |
| `/memory-promote` | Promote domain patterns from memory files to reusable skills |
| `/memory-claude-md-optimize` | Audit, score, and migrate flat CLAUDE.md into Memory Bank |

### Skill & Agent Authoring

| Skill | Description |
|-------|-------------|
| `/skill-author` | Create, audit, or convert Claude Code skills |
| `/agent-author` | Create, audit, or fix Claude Code subagents |
| `/skill-evaluate` | Evaluate skill quality before importing |
| `/skill-import` | Fetch a single skill from any GitHub repo |
| `/rule-enforcer` | Triage a recurrence rule via 4 questions and route to the right enforcement mechanism (CI / git hook / Claude hook / Memory). |

### Git Workflow

| Skill | Description |
|-------|-------------|
| `/git-worktree` | Manage git worktrees for parallel branch work |
| `/finish-branch` | Branch completion — merge, PR, keep, or discard |

### Documentation

| Skill | Description |
|-------|-------------|
| `/claude-docs` | Fetch and cache current Claude Code documentation |
| `/doc-product` | Author and review user-facing docs (plan, write, extract, review modes) |

### Session Continuity

| Skill | Description |
|-------|-------------|
| `/context-bridge` | Snapshot session state before `/clear` or `/compact` so the SessionStart hook can auto-restore continuity in the next session |

## Themes

| Theme | Base | Description |
|-------|------|-------------|
| `TCS Dark` | `dark` | Apple-palette accent — blue `claude` highlight (response bullet, spinner, branding) plus system green/red/orange status colors. Background, text, and syntax highlighting inherit from the dark base. |

Themes ship in `themes/<slug>.json` and are **auto-discovered** by Claude Code when the plugin is enabled (no `plugin.json` entry needed). Select via `/theme` — a newly added theme appears in the picker after the next Claude Code restart.

## Hooks

Hooks are **natively loaded** by Claude Code from `hooks/hooks.json` when the plugin is enabled. No installation step required.

| Event | Script | Purpose |
|-------|--------|---------|
| `UserPromptSubmit` | `capture_learning.py` | Detect corrections/learnings via regex (English + CJK), queue them |
| `SessionStart` | `session_start_reminder.py` | Show pending queue count at session open |
| `SessionStart` | `session_start_context_bridge.py` | Restore `/context-bridge` checkpoint when `source` is `clear` or `compact` |
| `PreCompact` | `check_learnings.py` | Back up queue before context compaction |
| `PostToolUse(Bash)` | `post_commit_reminder.py` | Remind to run `/memory-add` after git commit; capture persistent tool errors |

### Pattern Detection

`detect_learning()` uses an 8-step pipeline:
1. Minimum length gate (< 5 chars rejected)
2. Code block exclusion
3. Explicit patterns (`remember:`) — confidence 1.0
4. Guardrail patterns (`don't X unless`) — confidence 0.85
5. Correction patterns (English + 13 CJK patterns) — confidence 0.65-0.85
6. Positive patterns (`perfect!`, `exactly right`) — confidence 0.70
7. False positive filter (non-correction phrases, positive context detection)
8. Confidence adjustment (length, multi-pattern boost, cap 0.95)

### Optional: Semantic Validation

`scripts/lib/semantic_detector.py` provides optional AI-powered validation via `claude -p`:
- Validates low-confidence items (< 0.7) before persisting
- Detects contradictions between new and existing learnings
- Controlled via `TCS_SEMANTIC_VALIDATION=false` env var
- Falls back gracefully when `claude` CLI is unavailable

## Scripts

| Script | Purpose |
|--------|---------|
| `scripts/lib/reflect_utils.py` | Core library — pattern detection, queue I/O, dedup |
| `scripts/lib/semantic_detector.py` | Optional AI validation + contradiction detection |
| `scripts/extract_session_learnings.py` | Extract user messages from Claude session JSONL files |

## Tests

```bash
source venv/bin/activate && python3 -m pytest tests/tcs-helper/ -v
# 168 tests, ~2s
```

## Attribution

Learning capture patterns ported from [claude-reflect v3.1.0](https://github.com/BayramAnnakov/claude-reflect) by Bayram Annakov. The `skill-author` skill incorporates patterns from [obra/superpowers](https://github.com/obra/superpowers). Both used under MIT License.

## Installation

```bash
/plugin marketplace add MMoMM-org/the-custom-startup
/plugin install helper@the-custom-startup
```
