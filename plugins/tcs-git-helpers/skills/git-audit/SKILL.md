---
name: git-audit
description: "Use when auditing repo state — branch hygiene, PR state, stale-merged branches, override audit events, or running interactive cleanup of merged branches. Triggers on: git-audit, stale branches, branch cleanup, override audit, repo health."
user-invocable: true
argument-hint: "[--brief | --cleanup [--yes] | --json | --overrides]"
allowed-tools: Bash
---

## Persona

**Active skill: tcs-git-helpers:git-audit**

Report repo state for the current git repository: branch, PR status, stale-merged
branches, plugin version, recent overrides, and suggested next actions. All
state-gathering is delegated to the plugin's python backend — this skill is a
thin Claude-facing wrapper.

## Interface

```
State {
  mode: "default" | "brief" | "cleanup" | "json" | "overrides"
  // default      → multi-section structured report (branch / PR / stale / version / overrides / suggestions)
  // --brief      → single-line summary, ≤80 chars target
  // --cleanup    → list stale-merged branches; per-branch y/N prompt at a TTY, or --yes to delete all non-interactively (agents/CI have no TTY)
  // --json       → emit current stale-branch cache as JSON to stdout (tooling-consumable)
  // --overrides  → tail of override audit log (default last 7 days; --limit N for last N events)
  cacheAgeHours: number    // surfaced as "(cache Nh old)" warning when > 24
}
```

Spec refs:
- SDD §UI Visualization Guide → Status output structure
- SDD §Building Block View → `git_status_audit.py`
- PRD acceptance criteria M4 (SessionStart brief), M6 (stale branches), M12 (audit log)

## Constraints

**Always:**
- Invoke `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/git_status_audit.py` for every mode — the python backend is the single source of truth.
- Pass exactly one mode flag (`--brief` / `--cleanup` / `--json` / `--overrides`); omit all flags for the default multi-section report.
- Pipe the script's stdout to the user verbatim — do not rewrite, summarize, or reformat.
- Surface stderr on non-zero exit; do not swallow errors.
- Surface the `(cache Nh old)` warning verbatim when mtime exceeds the 24h stale-branch TTL.
- For `--cleanup`: the per-branch `y/N` prompt only runs at a real TTY. Claude's Bash tool always gets a piped stdin (no TTY, in any environment), so for Claude the bare `--cleanup` only lists candidates. To actually delete, FIRST show the candidate list and get the user's explicit go-ahead, THEN re-run with `--cleanup --yes` (deletes all listed branches). The script consults `git worktree list` and EXCLUDES branches checked out in any worktree.
- When the script reports `tcs-git-helpers not installed in this repo`, surface the message and suggest the user run `/tcs-git-helpers:git-setup`. The git/PR state still renders; only the post-merge cache refresh is missing.

**Never:**
- Re-implement git state queries (`git rev-parse`, `git status`, `gh pr list`, etc.) inline — the markdown body is intentionally state-free.
- Delete a stale branch without explicit user confirmation. `--cleanup --yes` is permitted ONLY after the user has seen the candidate list and approved (their approval is the confirmation that replaces the TTY prompt). Never pass `--yes` on the first, unprompted invocation.
- Operate on branches currently checked out in any worktree.
- Strip or suppress the cache-staleness warning marker.

**Mode reference:**

| Flag | Output | Notes |
|------|--------|-------|
| (none) | Multi-section structured report | branch / PR state / stale branches / plugin version / recent overrides / suggestions — see SDD §Status output structure |
| `--brief` | Single line, ≤80 chars | `[tcs-git-helpers] <branch> • <state> • <ahead/behind> • <stale-count>` |
| `--cleanup` | List candidates; interactive purge at a TTY | Worktree-checked-out branches excluded. Under Claude (no TTY) lists only — add `--yes` to delete all after user approval |
| `--cleanup --yes` | Non-interactive: delete ALL listed candidates | For agents/CI (no TTY). Use only after the user approves the listed candidates |
| `--json` | Stale-branch cache JSON | Tooling-consumable |
| `--overrides` | Audit-log tail | Default last 7 days; pass `--limit N` for last N events |

## Workflow

### 1. Detect mode from `$ARGUMENTS`

Parse the user's argument string. Recognized flags (mutually exclusive):

- `--brief`
- `--cleanup` (optionally followed by `--yes` to delete all listed candidates non-interactively)
- `--json`
- `--overrides` (optionally followed by `--limit N`)

If no flag was passed, run the default multi-section report.

### 2. Invoke the python backend

Run:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/git_status_audit.py" <flags>
```

Examples:

```bash
# Default report
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/git_status_audit.py"

# Brief mode (single line)
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/git_status_audit.py" --brief

# Stale-branch purge — bare form lists candidates (no TTY under Claude)
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/git_status_audit.py" --cleanup

# Stale-branch purge — delete ALL listed candidates (after user approval)
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/git_status_audit.py" --cleanup --yes

# JSON for tooling
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/git_status_audit.py" --json

# Last 20 override-audit events
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/git_status_audit.py" --overrides --limit 20
```

### 3. Surface output verbatim

- **stdout** → pipe to the user without rewriting; the script's structured layout matches the SDD §Status output structure spec.
- **stderr** → surface only when exit code is non-zero, prefixed with the failing mode for context.
- For `--cleanup` under Claude: there is no TTY, so the bare run prints the candidate list plus a hint and deletes nothing. Surface that list to the user and ask for approval. On approval, re-run with `--cleanup --yes` to delete all listed candidates. If the user instead wants to choose a subset, let them run `--cleanup` themselves in their terminal (the `!` prefix gives the per-branch `y/N` prompts), or delete the named branches with `git branch -d <name>`.

### 4. Cache-staleness handling

The script self-detects cache age and prepends `(cache Nh old)` to the brief / status output when mtime > 24h. Surface this verbatim — do not strip the warning. If the user asks why the cache is stale, point them at `git fetch && /tcs-git-helpers:git-audit --cleanup` to refresh.

### 5. Setup degradation

If the script reports `tcs-git-helpers not installed in this repo`, surface the message and suggest the user run `/tcs-git-helpers:git-setup`. The status report still renders — the missing githooks only affect post-merge cache refresh, not the live git/PR queries.

### 6. Error handling

If `python3` is unavailable or the script exits non-zero:

- Surface stderr verbatim.
- Do not retry with different arguments.
- Do not fall back to inline `git status` calls — the markdown body is intentionally state-free.

Common non-zero exits:

- `1` — not inside a git repository (script prints `[tcs-git-helpers] ERROR: not inside a git repository`)
- other — see script's argparse / mode handlers in `${CLAUDE_PLUGIN_ROOT}/scripts/git_status_audit.py`
