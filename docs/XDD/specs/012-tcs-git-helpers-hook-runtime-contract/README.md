# Specification: 012-tcs-git-helpers-hook-runtime-contract

## Status

| Field | Value |
|-------|-------|
| **Created** | 2026-05-13 |
| **Current Phase** | PRD |
| **Last Updated** | 2026-05-13 |

## Documents

| Document | Status | Notes |
|----------|--------|-------|
| requirements.md | completed | All 5 open questions resolved; ready for SDD handoff |
| solution.md | pending | SDD evaluates Options A/B/C trade-offs once PRD is approved |
| plan/ | pending | — |

**Status values**: `pending` | `in_progress` | `completed` | `skipped`

## Decisions Log

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-05-13 | Spec opened | Empirically verified during session that `.githooks/post-merge` silently no-ops in production because it depends on `CLAUDE_PLUGIN_ROOT` / `CLAUDE_PLUGIN_DATA` which are not propagated to git-invoked hooks. Stale-branch cache has never been written for any repo on this machine. |
| 2026-05-13 | Spec-first path chosen | Per memory `feedback_spec_first.md` and the cross-cutting nature of the fix (affects all 4 hooks installed by `install_files.sh`, intersects plugin update model), PRD→SDD→PLAN before any code. |
| 2026-05-13 | Q5 + Q1 resolved at PRD time | Drift check fires at **skill invocation time**, not SessionStart. Each skill that depends on hook-produced state compares installed hook banner to its required hook version and prompts the user on mismatch. SessionStart noise gets ignored; in-context prompts at the moment of dependency are the only signal that lands. This also locks Q1 — fail-loud-prompt-reinstall is the update model, scoped to skill invocations. New Feature 4 added to PRD to capture the acceptance criteria. |
| 2026-05-13 | Q2 + Q3 + Q4 resolved at PRD time | Q2: installed hook code is self-contained per-repo, no plugin-cache reference at runtime. SDD picks layout (single-file inline vs hook+lib siblings in `.githooks/`). Q3: Option D — independent `HOOK_BUNDLE_VERSION`, load-bearing. Q4: broader pattern — all four installed hooks + their shared lib are ONE versioned unit; bumping the bundle version re-installs everything together. Maintainer constraint codified: any change to installed-hook templates or shared lib MUST bump `HOOK_BUNDLE_VERSION`, enforced by CI. Feature 6 promoted to Must Have to reflect the atomic-unit framing. |
| 2026-05-13 | All 5 PRD open questions closed | Ready for SDD handoff. No remaining ambiguity at the requirements level; SDD chooses concrete implementation shapes within these constraints. |

## Context

Builds on `011-tcs-git-helpers` (original plugin design). That spec correctly defined the cache contract but did not anticipate that the harness's `CLAUDE_PLUGIN_*` env vars are not visible to hooks invoked by `git` itself.

Empirical findings (this session):

- 3-context env probe confirmed: harness-invoked plugin hooks (PostToolUse:Bash, SessionStart) see `CLAUDE_PLUGIN_ROOT` and `CLAUDE_PLUGIN_DATA`; git-invoked hooks during real `git merge` and Bash-tool processes see neither.
- `~/.claude/plugins/data/tcs-git-helpers-*/cache/` contains many `pr-state.json` and `nudge-verify-*` entries (written by harness-spawned `nudge-hook.sh`) but zero `*-stale-cache.{tsv,json}` entries (would be written by git-spawned `post-merge` if env was right).
- Downstream: `/tcs-git-helpers:git-audit --cleanup` reports "No stale-merged branches" while `git branch --merged main` shows 6 stale branches.

Three coupled architectural facts:

1. Hook fires from `git`, not the harness → no harness env vars
2. Plugin versions live in versioned cache dirs with no `current` symlink → no stable absolute path the hook can hard-code
3. Installed hook is templated once at git-setup time and frozen → plugin updates don't propagate

Pre-sketched solution shapes (SDD must evaluate, not PRD pre-decide):

- **A** — Inline lib code into the hook at install time (self-contained, no env dependency, bug-fix propagation requires re-install)
- **B** — Stable manifest at the repo's data dir (SessionStart refreshes; race on first new-version merge before first new-version session)
- **C** — SessionStart auto-detects drift via *plugin* version banner and re-installs (plugin version becomes load-bearing)
- **D** — Self-contained installed hook + **independent hook-version stamp** + plugin code compares "installed hook version" to "expected hook version" on SessionStart and prompts user to re-install only on actual hook drift. Decouples plugin updates (frequent) from hook re-installs (only when hook code actually changed). Requires maintainer discipline: bump hook version whenever hook template or inlined lib changes.

Open PRD questions: update model, hook independence vs current-plugin-code, version-banner role, scope (post-merge only / all installed hooks / broader pattern).

Tangential bugs to fold or split: `cmd_cleanup` never refreshes cache; hook silently exits on missing env var.

---
*This file is managed by the xdd-meta skill.*
