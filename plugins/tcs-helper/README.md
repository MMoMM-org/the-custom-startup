# tcs-helper Plugin

Helper tools for The Custom Agentic Startup — memory system, skill authoring, and project onboarding.

## Version 3.0.0

### Breaking Changes

- `merge_hooks.py` removed — hooks now load natively from `hooks/hooks.json` via Claude Code's plugin system. No manual hook installation needed.
- Hook scripts read `cwd` from JSON stdin instead of `${PWD}` CLI argument.

See [CHANGELOG.md](CHANGELOG.md) for full details.

## Skills

### Memory Bank

| Skill | Description |
|-------|-------------|
| `/setup` | Provision `docs/ai/memory/` + CLAUDE.md hierarchy in a new repo |
| `/memory-add` | Capture session learnings and route to the correct scope and category file |
| `/memory-sync` | Keep `@imports` and memory index in sync |
| `/memory-cleanup` | Archive resolved issues, prune stale entries |
| `/memory-promote` | Promote domain patterns from memory files to reusable skills |
| `/memory-claude-md-optimize` | Audit, score, and migrate flat CLAUDE.md into Memory Bank |

### Skill Authoring

| Skill | Description |
|-------|-------------|
| `/skill-author` | Create, audit, or convert Claude Code skills |
| `/skill-evaluate` | Evaluate skill quality before importing |
| `/skill-import` | Fetch a single skill from any GitHub repo |

### Git Workflow

| Skill | Description |
|-------|-------------|
| `/git-worktree` | Manage git worktrees for parallel branch work |
| `/finish-branch` | Branch completion — merge, PR, keep, or discard |
| `/docs` | Fetch and cache current Claude Code documentation |

## Hooks

Hooks are **natively loaded** by Claude Code from `hooks/hooks.json` when the plugin is enabled. No installation step required.

| Event | Script | Purpose |
|-------|--------|---------|
| `UserPromptSubmit` | `capture_learning.py` | Detect corrections/learnings via regex (English + CJK), queue them |
| `SessionStart` | `session_start_reminder.py` | Show pending queue count at session open |
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
# 161 tests, ~1s
```

## Attribution

Learning capture patterns ported from [claude-reflect v3.1.0](https://github.com/BayramAnnakov/claude-reflect) by Bayram Annakov. The `skill-author` skill incorporates patterns from [obra/superpowers](https://github.com/obra/superpowers). Both used under MIT License.

## Installation

```bash
/plugin marketplace add MMoMM-org/the-custom-startup
/plugin install helper@the-custom-startup
```
