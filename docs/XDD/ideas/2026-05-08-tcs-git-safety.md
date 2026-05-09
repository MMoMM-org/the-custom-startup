# tcs-git-helpers — Git Workflow Discipline Plugin for Claude

**Date:** 2026-05-08
**Status:** Brainstorm spec — ready for `/xdd` PRD phase
**Author:** Marcus Breiden (with Claude)
**Branch:** `feat/tcs-git-safety` (legacy name; will rename PR/branch during PRD phase)
**Plugin name:** `tcs-git-helpers` (covers safety hooks, nudges, best-practices references, opt-in GHA branch protection)

---

## 1. Context & Motivation

Marcus operates multiple repos: TCS itself plus the MiYo ecosystem (Kado, Hakobi, Tomo, Kokoro, Kouzou, Seigyo, Hashi). Recurring git workflow problems are caused **primarily by Claude (the AI agent)**, not by Marcus — Marcus knows the rules; Claude forgets them between sessions.

### Observed Failure Modes

1. **Pushes to closed/merged PRs** — Claude pushes to a branch whose PR was already closed/merged, polluting the closed PR or creating dirty re-open scenarios.
2. **New branches from main while another branch is unfinished** — Most common pattern: a feature branch is *clean* (everything committed) but **not yet merged or PR'd**, and Claude creates the next feature branch from main/master. Result: the prior branch sits orphaned, never finished, and merges silently de-prioritized work into oblivion. Less common but related: branching off a *dirty* working tree.
3. **Squash-merge branch reuse** — Claude continues work on a branch that was already squash-merged. Result: PR shows `mergeable: CONFLICTING` because old commits' patches no longer apply to a master that already has their content under different SHAs. Marcus's existing finding documents the recovery (cherry-pick onto fresh branch).
4. **Edits/commits attempted on main/master** — Existing `~/.claude/hooks/block-main-edits.sh` denies, but Claude keeps blundering in instead of pre-flighting branch state.
5. **Bad commit/merge messages** — No Conventional-Commits enforcement; existing `commit-msg` hook only checks length.
6. **Stale local branches** — Branches whose PRs were merged accumulate (currently 6 in Kado: `docs/restructure-documentation`, `feat/read-tags-operation`, `feat/search-filter`, `chore/github-funding`, `docs/api-reference-add-kado-open-notes`, `fix/issue-8-blacklist-crud-semantics`).
7. **Destructive git operations** — `git reset --hard`, `git checkout .`, `git clean -f`, `git branch -D`, `git stash drop`, `git reflog expire`, `--no-verify` commits, etc. Often invoked reflexively to "fix" a state that should have been investigated first. (Boucle-framework's `git-safe` documents the canonical set; see §11.)
8. **Worktree exit data loss** — Exiting a Claude Code worktree session can delete the worktree branch and any uncommitted/unpushed commits. (Boucle-framework's `worktree-guard` documents.)

### Live Incident Captured During Brainstorm

While brainstorming this very design, Claude (this session) was about to write the spec file while still on `main`. Marcus had to manually prompt the branch switch. This is the case-in-point: even when designing the safety net, Claude forgets to pre-flight. Motivates the `SessionStart` awareness brief (see §6.2.3).

---

## 2. Goals

| # | Goal | Success Criteria |
|---|---|---|
| G1 | Hard-block pushes to closed/merged PRs | Hook denies; provides recovery steps including `references/squash-merge-trap.md` |
| G2 | Hard-block branch creation from unfinished work | Hook denies on dirty working tree, OR if current branch has commits not yet merged/PR'd (the "clean-but-orphaned" case) |
| G3 | Detect and block resume on squash-merged branches | Hook denies `git checkout <merged-branch>`; merge-commit branches NOT flagged (false-positive avoidance via `git cherry`) |
| G4 | Make Claude pre-flight branch state | `SessionStart` hook outputs branch/PR/cleanliness brief without `gh` network calls |
| G5 | Enforce Conventional Commits format | `commit-msg` hook validates `<type>(<scope>)?: <subject>` against allowlist |
| G6 | Surface stale local branches | `post-merge` hook + `/tcs-git-helpers:status --cleanup` |
| G7 | Block broader destructive git operations | Bash PreToolUse hook denies `reset --hard`, `checkout .`, `clean -f`, `branch -D`, `stash drop/clear`, `reflog expire`, `--no-verify`, etc. (Boucle-framework `git-safe` parity) |
| G8 | Prevent worktree-exit data loss | `WorktreeRemove` (or `SessionEnd`) hook checks for uncommitted/untracked/unmerged/unpushed before allowing exit |
| G9 | Nudge Claude after key git ops | PostToolUse hooks emit context-specific reminders (e.g. after `git checkout -b` → "verify base branch clean") |
| G10 | Distribute via TCS plugin to all Marcus's repos | `/tcs-git-helpers:setup` skill installs `.githooks/` per-repo; Claude-side hooks register via plugin's `hooks/hooks.json` |
| G11 | Defense-in-depth: hooks committed to repo | `.githooks/` files tracked in git so Docker/CI/non-Claude consumers also protected |
| G12 | Optional: GitHub branch protection inline | `/tcs-git-helpers:setup --with-branch-protection` calls `gh api` to set protection rules on default branch |

---

## 3. Non-Goals (Parking Lot)

Explicitly **out of scope for v1.0**, deferred to v1.1+:

- Auto-delete merged branches (v1.0 only suggests via `post-merge` and `--cleanup`)
- Cross-repo orchestration skill (run setup across all Marcus's repos in one shot)
- Conventional-changelog / release-please integration
- Telemetry / violation tracking
- AI-driven commit-message generation
- Per-repo custom validators beyond `.githooks/.config`
- Resolution of `/tcs-helper:finish-branch` triggering in wrong repo (separate skill-discoverability concern; tracked in §12)
- Mobile/Windows-specific edge cases (Marcus is macOS-first)

**Note on GitHub branch protection (G12):** Single-account use of GH still benefits — protection is a tripwire against Claude accidents (force-push, direct push to main, branch-deletion), not multi-user enforcement. Inline as opt-in.

---

## 4. Architecture Decisions

### 4.1 Target

**Claude (the agent), not Marcus.** Marcus knows the rules; the agent forgets between sessions. Design centers on machine-enforced pre-flight checks and denial hooks.

### 4.2 Enforcement Style

**Hard-deny + per-violation env-var escape hatches** for safety hooks. Consistent with existing `block-main-edits.sh` and Kado's `pre-commit`. Each escape hatch is granular so override-of-one doesn't bypass-all.

**Soft-nudge** (PostToolUse `additionalContext` output) for follow-up reminders. Doesn't block anything; surfaces context Claude reads.

### 4.3 Distribution & Lifecycle

**Plugin-internal Claude hooks; per-repo `.githooks/` defense in depth.**

| Layer | Path | Lifecycle | Why this layer |
|---|---|---|---|
| Plugin-internal Claude hooks | `${CLAUDE_PLUGIN_ROOT}/scripts/*.sh` registered in `hooks/hooks.json` | Fires only when plugin enabled (intentional coupling) | Plugin-install ↔ protection-active. Disable plugin = consciously waive Claude-side protection |
| Repo-local git hooks | `<repo>/.githooks/*` with `git config core.hooksPath .githooks` | Per-repo, committed in git, always active | Defense in depth — protects Docker, CI, non-Claude consumers; survives plugin disable |

**Why plugin-internal for Claude hooks (not user-global):** The original draft put hooks in `~/.claude/hooks/` for "always-fires" semantics. Marcus revised: protection should be coupled to plugin installation. Disabling the plugin should disable the Claude-side protection (plugin lifecycle = trust signal). The `.githooks` layer remains as universal defense in depth, so disabling the plugin doesn't strip git-side protection.

**Hook script writing constraints (the actual difference plugin-vs-user-global):**
- Use `${CLAUDE_PLUGIN_ROOT}` to reference plugin-bundled scripts and references
- Use `${CLAUDE_PLUGIN_DATA}` for persistent data (cache files that should survive plugin updates)
- Use `$CLAUDE_PROJECT_DIR` for project-relative paths
- Hook entry points in `hooks/hooks.json` reference `${CLAUDE_PLUGIN_ROOT}/scripts/<script>.sh`

### 4.4 Update Mechanism

`.githooks/` files use copy-with-version. Each installed hook gets a marker as first comment line:
```
# tcs-git-helpers: v1.0.0
```
`/tcs-git-helpers:setup --update` detects mismatched markers, shows per-file diffs, asks per-file resolution.

Claude-side hooks (in plugin) update automatically when plugin is updated via marketplace — no per-repo action needed.

---

## 5. Plugin Layout

```
plugins/tcs-git-helpers/
├── .claude-plugin/
│   └── plugin.json                  # name: tcs-git-helpers, version: 1.0.0
├── README.md
├── CHANGELOG.md
├── hooks/
│   └── hooks.json                   # Registers PreToolUse (Bash + Write/Edit/NotebookEdit),
│                                    # PostToolUse (Bash for nudges), SessionStart, WorktreeRemove
├── scripts/                         # Source-of-truth — referenced via ${CLAUDE_PLUGIN_ROOT}
│   ├── lib/
│   │   ├── git_state.sh             # Shared: branch state, PR query, git_safe wrapper, state detection
│   │   ├── config_parser.sh         # Strict key=value parser for .githooks/.config (no source)
│   │   └── pattern_match.sh         # Bash regex helpers (no lookahead, POSIX ERE)
│   ├── block-bad-git-ops.sh         # Bash PreToolUse — broad destructive-op blocker (G1, G2, G3, G7)
│   ├── pre-edit-branch-check.sh     # Write/Edit PreToolUse — augment of block-main-edits.sh (G4)
│   ├── nudge-hook.sh                # Bash PostToolUse — soft nudges (G9)
│   ├── session-start-brief.sh       # SessionStart — local-only brief (G4)
│   ├── worktree-exit-guard.sh       # WorktreeRemove (or SessionEnd) — data-loss prevention (G8)
│   └── git_status_audit.py          # Backend for /tcs-git-helpers:status (gh-aware)
├── templates/githooks/              # Copied to <repo>/.githooks/ by setup
│   ├── pre-commit                   # Block protected-branch + secrets + .config exclusions
│   ├── pre-push                     # gh pr list → reject closed/merged (G1)
│   ├── commit-msg                   # Conventional Commits + length (G5)
│   ├── post-merge                   # Suggest stale-branch cleanup (G6)
│   └── .config.example              # Empty template with comment hints (NOT named .config)
├── templates/github-actions/
│   └── pr-title-check.yml           # Optional GHA, opt-in via --with-gha
├── references/                      # Knowledge base
│   ├── INDEX.md
│   ├── best-practices.md            # Overarching git workflow best practices (entry point)
│   ├── squash-merge-trap.md         # Marcus's existing finding, formalized
│   ├── branch-lifecycle.md          # Create→Work→PR→Merge→Cleanup
│   ├── conventional-commits.md
│   ├── pr-vs-commit-messages.md     # Squash-merge: PR title becomes commit
│   ├── force-push-safety.md         # --force vs --force-with-lease, shared branches
│   ├── rebase-vs-merge.md
│   ├── stale-branch-cleanup.md      # auto-delete-head setting, fetch --prune
│   ├── working-tree-hygiene.md      # Clean state, stash-vs-branch for WIP
│   ├── destructive-ops.md           # Why reset --hard / clean -f / branch -D are blocked + alternatives
│   ├── worktree-discipline.md       # Worktree-specific patterns and pitfalls
│   └── sandbox-and-git-config.md    # Known sandbox interactions
└── skills/
    ├── setup/SKILL.md               # /tcs-git-helpers:setup
    └── status/SKILL.md              # /tcs-git-helpers:status
```

---

## 6. Components

### 6.1 References (Knowledge Base)

Standalone markdown documents that hooks and skills cite by relative path. Each follows the same structure:

1. **What goes wrong** — concrete failure mode
2. **How to detect** — diagnostic commands
3. **Fix** — recovery steps
4. **Prevention** — how to avoid
5. **Why** — root explanation (so Claude can judge edge cases instead of blindly following)

**Initial content priorities:**
- `squash-merge-trap.md` — Marcus's existing finding 1:1
- `best-practices.md` — overarching index/landing doc that other refs link from; covers branch-naming, commit-message-quality, when-to-rebase-vs-merge at a high level then defers to specific docs
- Other refs get a first pass with established best practices, grow organically

**Citation pattern in hook denial messages:**
```
See: ${CLAUDE_PLUGIN_ROOT}/references/squash-merge-trap.md
```

**`references/` is plugin-internal only** — not copied into target repos. Claude reads via plugin path. Rationale: keeps single source of truth; updates propagate via plugin update.

### 6.2 Claude-side Hooks (Plugin-Internal)

All registered in `hooks/hooks.json` referencing `${CLAUDE_PLUGIN_ROOT}/scripts/*`.

#### 6.2.1 `block-bad-git-ops.sh` (Bash PreToolUse)

Regex-dispatches on `tool_input.command` from JSON stdin. **Pattern set absorbs Boucle-framework `git-safe` parity plus our branch-lifecycle additions:**

| Pattern (Bash POSIX ERE; no lookaheads) | Check | Default Action | Override env-var |
|---|---|---|---|
| `git\s+push\b` | `gh pr list --head <branch>` (with timeout, see §7.2) | DENY if PR ∈ {CLOSED, MERGED} | `CLAUDE_ALLOW_PUSH_TO_CLOSED_PR=1` |
| `git\s+push.*--force\b` (without `--force-with-lease`) | Hard match | DENY, recommend `--force-with-lease` | `CLAUDE_ALLOW_FORCE_PUSH=1` |
| `git\s+push.*--force-with-lease` to protected branch | Detect protected branch list | DENY (force-with-lease still rewrites history) | `CLAUDE_ALLOW_FORCE_TO_PROTECTED=1` |
| `git\s+push.*--delete\b` or `git\s+push\s+\S+\s+:\S+` | Hard match | DENY (deletes remote branch) | `CLAUDE_ALLOW_REMOTE_BRANCH_DELETE=1` |
| `git\s+(checkout\|switch)\s+-b\s+\S+` | Current branch state via `lib/git_state.sh` | DENY if base is dirty/unpushed/has-open-PR/squash-merged OR if current branch is *clean but unmerged* (FM2) | `CLAUDE_ALLOW_BRANCH_FROM_UNFINISHED=1` |
| `git\s+(checkout\|switch)\s+([^-\s]\S*)$` (token doesn't start with `-`) | `gh pr list --head <branch> --state merged` + `git cherry` (see §7.4) | DENY if branch was squash-merged AND patches already applied to default | `CLAUDE_ALLOW_RESUME_MERGED_BRANCH=1` |
| `git\s+commit.*(--no-verify\|-n\b)` | Hard match | DENY (bypasses `.githooks/`; defeats the purpose) | `CLAUDE_ALLOW_NO_VERIFY=1` |
| `git\s+reset\s+--hard\b` | Hard match | DENY (destroys working tree + index) | `CLAUDE_ALLOW_RESET_HARD=1` |
| `git\s+checkout\s+\.` or `git\s+checkout\s+--\s+\S+` | Hard match | DENY (discards working changes silently) | `CLAUDE_ALLOW_DESTRUCTIVE_CHECKOUT=1` |
| `git\s+restore\s+(.*--staged.*\|.*--worktree.*--source.*)` | Pattern match | DENY (destructive `git restore` modes) | `CLAUDE_ALLOW_DESTRUCTIVE_RESTORE=1` |
| `git\s+clean\s+(-[a-z]*f\|-[a-z]*x\|--force)` | Hard match | DENY (deletes untracked files) | `CLAUDE_ALLOW_CLEAN_FORCE=1` |
| `git\s+branch\s+-D\b` | Hard match | DENY (force-deletes; use `-d` and recover via reflog if needed) | `CLAUDE_ALLOW_FORCE_BRANCH_DELETE=1` |
| `git\s+stash\s+(drop\|clear)\b` | Hard match | DENY (destroys stash; use `pop` to recover) | `CLAUDE_ALLOW_STASH_DESTROY=1` |
| `git\s+reflog\s+expire\b` | Hard match | DENY (kills the recovery net) | `CLAUDE_ALLOW_REFLOG_EXPIRE=1` |

**Master override:** `CLAUDE_ALLOW_GIT_BAD_OPS=1` (emergencies only; logs to stderr).

Output uses `permissionDecision: deny` with reason that includes:
- What was detected (which pattern matched)
- Recovery steps with reference doc link
- Specific override env-var name (encourages targeted overrides over master)

**Compound-command detection:** regex applied to full `command` string (handles `cd foo && git push`, `(git push)`, etc.).

**Limitations (documented, not fixed):** aliases (`git pf` → `push --force`) cannot be detected at this layer; `.githooks/pre-push` catches them git-side. PowerShell-style command lines not supported (macOS-first).

**Allowlist concept (deferred to v1.1):** Boucle's `.git-safe` per-repo allowlist file is noted as a v1.1 candidate. v1.0 uses env-var overrides only.

#### 6.2.2 `pre-edit-branch-check.sh` (Write/Edit/NotebookEdit PreToolUse)

Augments — does not replace — existing user-global `~/.claude/hooks/block-main-edits.sh`. Both run; deny semantics aggregate. Plugin's version adds:
- Squash-merge orphan detection on non-main branches (warning, not deny — edits on dirty branch are recoverable; edits on main are catastrophic)
- Reference link in denial message: `references/branch-lifecycle.md`

**No migration of existing user-global hook.** It stays in place as universal baseline. When plugin enabled, both fire. When plugin disabled, user-global still protects against main edits (the most catastrophic case).

#### 6.2.3 `session-start-brief.sh` (SessionStart hook)

Local-only (no `gh` call) brief output. Format:
```
[tcs-git-helpers] feat/foo • clean • 2 commits ahead • 6 stale-merged branches
```
Components:
- Current branch (with ⚠ if main/master/protected)
- Working-tree state (clean/dirty)
- Ahead/behind counts vs upstream
- Stale-merged branch count from local cache (see §7.3)

**Performance budget:** must complete in <300ms. Uses only local git commands. Stale-merged count comes from cache; cache refreshed asynchronously by `git_status_audit.py` after `post-merge` and `/tcs-git-helpers:status` runs.

#### 6.2.4 `worktree-exit-guard.sh` (WorktreeRemove or SessionEnd hook)

Absorbs Boucle-framework `worktree-guard` checks. Before allowing worktree removal / session end:

1. **Uncommitted changes** — `git status --porcelain` non-empty? Warn/deny.
2. **Untracked files** — same check, includes `??` entries
3. **Unmerged commits** — commits on this worktree's branch not in default branch
4. **Unpushed commits** — commits not on remote tracking branch

For **unmerged detection:** uses `git cherry` (not SHA comparison) to handle squash-merged-already cases correctly:
```
git cherry origin/$default $branch | grep '^+'
```
Lines starting with `+` are commits not yet applied (in any form) to default — only those count as "real unmerged".

**Event choice (defer to PRD/PLAN):** Claude Code has both `WorktreeRemove` and `SessionEnd` events. Test which one fires reliably and can deny. Boucle uses PreToolUse on whatever Claude does to invoke worktree removal; we'll likely use `WorktreeRemove`.

**Override:** `CLAUDE_ALLOW_WORKTREE_EXIT_WITH_CHANGES=1` (one-shot; only this exit, must re-set per attempt to prevent reflexive reuse).

**Boucle-noted limitations to absorb (in `references/worktree-discipline.md`):** mid-session worktree ops bypass hooks; agent-isolated worktrees can't always emit warnings; symlink configs interfere with cleanup.

### 6.3 Repo-side `.githooks/` Templates

Source files in `templates/githooks/`, installed to `<repo>/.githooks/` by `/tcs-git-helpers:setup`. Each gets `# tcs-git-helpers: vX.Y.Z` as first comment line.

#### 6.3.1 `pre-commit`

Inherits Kado's existing logic with three changes:
1. Outbox-specific `_outbox/` exception → generalized via `.githooks/exclude-paths` (default empty file in plugin; each repo fills as needed)
2. **Configurable protected branches** (Boucle `branch-guard` parity): default `main|master|production|release`, override via `TCS_PROTECTED_BRANCHES` in `.githooks/.config`
3. Secret-detection patterns moved to shared `lib/git_state.sh` for reuse

**`--amend` on protected branches:** Boucle allows; we **deny by default** (amend rewrites history). Opt-in via `TCS_ALLOW_AMEND_ON_PROTECTED=1` in `.config`.

#### 6.3.2 `pre-push` (NEW)

Logic:
```
BRANCH=$(git rev-parse --abbrev-ref HEAD)
gh CLI not available → exit 0 (degraded mode, log warning to stderr)
gh CLI present:
  Run: timeout 5 gh pr list --head <BRANCH> --state all --json state,number --limit 1 --jq '.[0]'
  Truth table: see §7.2
  If PR found and state ∈ {CLOSED, MERGED} → exit 1 with explanation
  Otherwise → exit 0
```

Override: `TCS_ALLOW_PUSH_TO_CLOSED_PR=1 git push ...`

#### 6.3.3 `commit-msg` (upgraded)

Validation pipeline:
1. Length check (existing): subject ≤ `TCS_MAX_SUBJECT_LENGTH` (default 90)
2. Conventional Commits format (NEW):
   ```
   ^(feat|fix|docs|style|refactor|test|chore|perf|revert|build|ci)(\([a-z0-9._-]+\))?!?: .+
   ```
   Type allowlist from `.githooks/.config`'s `TCS_ALLOWED_COMMIT_TYPES`.
3. Optional scope requirement: `TCS_REQUIRE_SCOPE=1` makes `(scope)` mandatory.

**Excluded:** merge commits (`git rev-parse -q --verify MERGE_HEAD` non-empty, or `Merge branch …` / `Merge pull request …` subject patterns).

**Override:** append `[skip-format-check]` to subject line.

#### 6.3.4 `post-merge` (NEW)

After `git pull` or merge, query `gh pr list --head <local-branch> --state merged` for each local branch (excluding protected). Output suggestion list with PR numbers and merge dates. **No auto-delete.** Updates local cache file (see §7.3) for `session-start-brief.sh` to read.

### 6.4 `.githooks/.config` (per-repo, optional)

**Strict key=value parser, no shell `source`** (Gap Review B3). Implemented in `lib/config_parser.sh`. Allowlist of recognized keys:

```
TCS_PROTECTED_BRANCHES          # |-separated, default "main|master|production|release"
TCS_HOOK_EXCLUDE_PATHS_FILE     # path to file with one pattern per line (default: .githooks/exclude-paths)
TCS_ALLOWED_COMMIT_TYPES        # space-separated string
TCS_REQUIRE_SCOPE               # 0 | 1
TCS_MAX_SUBJECT_LENGTH          # integer
TCS_ENABLE_CONVENTIONAL_CHECK   # 0 | 1
TCS_ENABLE_PR_PUSH_CHECK        # 0 | 1
TCS_ALLOW_AMEND_ON_PROTECTED    # 0 | 1
```

`.config` is parsed line-by-line, ignoring comments (`#`) and blanks. Each non-comment line must match `^([A-Z_][A-Z0-9_]*)=(.*)$`. Values are stored without `eval`/`source` semantics — pure string assignment to known shell variables.

The `TCS_HOOK_EXCLUDE_PATHS` array is loaded from a separate file (default `.githooks/exclude-paths`, one pattern per line). Avoids array syntax in `.config` (which would re-introduce `source` injection risk).

**Plugin-shipped default:** empty exclude file plus `.config.example` with commented-out hints.

### 6.5 Skills

#### 6.5.1 `/tcs-git-helpers:setup`

**Modes:**
- (no flag) — per-repo install, default
- `--update` — refresh based on version markers
- `--with-gha` — also install `pr-title-check.yml` GHA
- `--with-branch-protection` — also configure GH branch protection on default branch (G12)

**Per-repo workflow (default mode):**
1. Verify in git repo. If not → error.
2. Verify on feature branch. If on main/master → offer `git checkout -b feat/tcs-git-helpers-setup`.
3. Detect default branch via `origin/HEAD` (handles main vs master).
4. **Conflict detection (Gap Review B6):**
   - Read `git config --get core.hooksPath`. If non-empty and not `.githooks` → abort, require explicit migration confirmation.
   - Scan `.git/hooks/` for non-`.sample` files → warn, list found files, ask confirmation.
   - Check for `.husky/` directory → warn about Husky conflict.
5. Inspect existing `.githooks/`:
   - None → fresh install.
   - Present without `# tcs-git-helpers:` marker → conflict mode: per-file diff, ask resolution (overwrite / merge-manual / skip / backup-as-`.bak.<timestamp>`).
   - Present with matching version marker → "up to date", optional re-apply.
   - Present with older marker → per-file diff, ask resolution.
6. **Concurrent run protection (Gap Review A1):** create `.githooks/.setup.lock` with PID + timestamp. Stale lock (>5min) → reclaim.
7. Copy templates with version marker as first comment line.
8. Create empty `.githooks/exclude-paths` and `.githooks/.config.example` if not present.
9. `git config core.hooksPath .githooks` (with `git_safe` wrapper for sandbox warnings).
10. `chmod +x .githooks/pre-commit .githooks/pre-push .githooks/commit-msg .githooks/post-merge`.
11. Output summary: what was installed, conflicts resolved, suggested next steps. **Does NOT auto-commit** — Marcus reviews then commits.
12. Release `.setup.lock`.

**No `--user-global` mode.** Earlier draft had this for installing Claude hooks to `~/.claude/hooks/`; revised architecture (§4.3) makes Claude hooks plugin-internal, so no user-global install step needed.

**`--with-branch-protection` workflow (when flag set):**
1. Determine default branch + GH owner/repo via `gh repo view`
2. Show planned protection rules (PR-required, status-checks, no-force-push, no-deletions, etc.) — defer to a documented preset
3. Confirm with user
4. `gh api -X PUT repos/<owner>/<repo>/branches/<default>/protection -f ...`
5. Enable "Automatically delete head branches" via `gh api -X PATCH repos/<owner>/<repo> -f delete_branch_on_merge=true`

#### 6.5.2 `/tcs-git-helpers:status`

**Modes:**
- (default) → structured status (branch, working tree, PR state, stale branches, plugin version, suggestions, references list)
- `--brief` → one-line for embedding (also used by `session-start-brief.sh` reads from cache)
- `--cleanup` → interactive purge of stale-merged branches with `git_safe` wrapper (skips branches checked out in worktrees, Gap Review A2)
- `--json` → structured output for tool consumption

**Default output sample:**
```
[tcs-git-helpers status — feat/foo]

Branch:
  ✓ On feature branch
  ✓ Working tree clean
  ⚠ Branch not pushed to remote (no upstream tracking)

PR state for current branch:
  No PR yet for feat/foo

Stale local branches (PR merged, safe to delete):
  feat/old-thing       (PR #38 merged 2026-04-12)
  fix/another-thing    (PR #40 merged 2026-04-15)

Plugin version: v1.0.0  (installed in this repo: v1.0.0 ✓)

Suggestions:
  • Push branch and open PR when ready
  • Run /tcs-git-helpers:status --cleanup to delete 2 stale branches
```

Backend: `scripts/git_status_audit.py`. Shared with `session-start-brief.sh` only via cache file (audit script writes; brief script reads).

### 6.6 Nudge Hooks (PostToolUse — soft reminders)

Single dispatcher script `nudge-hook.sh` registered for `PostToolUse` matcher `Bash`. Reads JSON stdin (which now includes the executed command and its exit status), regex-matches successful operations, emits context-specific nudge via stderr (which Claude Code surfaces as additional context).

**Trigger map:**

| After successful Bash command | Nudge surfaced to Claude |
|---|---|
| `git\s+(checkout\|switch)\s+-b\s+\S+` (new branch created) | "New branch created. Verify base is up-to-date origin/$default before continuing: `git log -1 origin/$default..HEAD` should be empty." |
| `gh\s+pr\s+create` or first `git\s+push\s+-u\s+origin\s+\S+` | "PR will be opened. If your repo squash-merges, the PR title becomes the commit. Confirm the title follows Conventional Commits format (see references/conventional-commits.md)." |
| `gh\s+pr\s+merge` | "PR merged. Run `/tcs-git-helpers:status --cleanup` to identify stale local branches now that the PR is closed." |
| `git\s+rebase\b` (any variant) | "Rebase completed. Verify resulting history with `git log --oneline -10`. If conflicts were resolved, double-check that no commits were lost." |
| `git\s+(merge\|pull)\b` resulting in a merge commit on a feature branch | "Merge into feature branch. Consider: would `git pull --rebase` keep history linear?" |
| `git\s+stash\s+pop` after non-trivial conflict signs | "Stash popped. If conflicts surfaced: verify `.orig` files cleaned up." |

Nudges are **idempotent and stateless** — fired on every match. Claude can ignore. They're hints, not instructions.

**Why PostToolUse, not skill-based:** PostToolUse fires automatically; doesn't require Claude to remember to run a skill. Aligns with the broader plugin philosophy (machine-enforced over Claude-remembered).

### 6.7 GitHub Actions PR-title check (opt-in)

`templates/github-actions/pr-title-check.yml` — runs on `pull_request` events, validates PR title against same Conventional Commits regex as `commit-msg` hook. Important for repos using **squash-merge** (PR title becomes the commit on default branch).

Installed via `/tcs-git-helpers:setup --with-gha`. Default off — each repo decides.

---

## 7. Decision Matrices & Algorithms

### 7.1 Hook Decision Matrix (git state × hook)

Per Gap Review B5, every hook bypasses branch checks when any of these `.git/` markers exist:

| State | `.git/` marker | Behavior |
|---|---|---|
| Rebase in progress | `.git/rebase-merge/` or `.git/rebase-apply/` | Bypass branch checks (rebase replays may touch main temporarily) |
| Merge in progress | `.git/MERGE_HEAD` | Bypass branch checks |
| Cherry-pick in progress | `.git/CHERRY_PICK_HEAD` | Bypass branch checks |
| Bisect in progress | `.git/BISECT_LOG` | Bypass branch checks |
| Detached HEAD | `git symbolic-ref --short HEAD` exits non-zero | Bypass branch checks (no branch to evaluate) |

In all bypass cases, hooks log to stderr that they're bypassing and why.

### 7.2 `gh` Exit Code Truth Table (pre-push and Claude-side push hook)

| `gh pr list` exit | stderr contains | Interpretation | Hook action |
|---|---|---|---|
| 0 | (output JSON empty array `[]`) | No PR for this branch | Allow |
| 0 | (output JSON has PR, state OPEN) | Active PR | Allow |
| 0 | (output JSON has PR, state CLOSED/MERGED) | PR closed | DENY (or override) |
| Non-zero | "no GitHub remote" | Repo not on GitHub | Allow with warning (degraded) |
| Non-zero | "authentication required" / "not logged in" | gh unauthenticated | Allow with warning, prompt to authenticate |
| Non-zero | "API rate limit exceeded" | Rate-limited | Allow with warning (cannot determine state) |
| (timeout) | — | Network slow / hang | Allow with warning |

**Wrapper:** `timeout 5 gh pr list …` (5-second shell timeout — note: `gh` itself has no `--max-time` flag; use the `timeout` coreutil). Default action when state cannot be determined: **allow** (fail-open) with stderr warning. Rationale: false-positive denials of legitimate pushes are worse than false-negatives because the recovery path (cherry-pick to fresh branch) is always available even if a bad push happens.

### 7.3 Stale-Branch Cache for SessionStart

To keep `session-start-brief.sh` under 300ms without `gh` calls, stale-merged branches are cached:

- Cache file: `${CLAUDE_PLUGIN_DATA}/cache/<repo-hash>-stale-cache.json` (per-repo file in plugin's persistent data dir; survives plugin updates)
- Format: JSON with `{"updated": "<ISO timestamp>", "repo_path": "...", "branches": [{"name": "...", "pr_number": N, "merged_at": "..."}]}`
- Updated by: `post-merge` hook (after pulls/merges) and `/tcs-git-helpers:status` (any invocation)
- TTL: brief reads cache regardless of age but reports staleness if >24h old

**Why `${CLAUDE_PLUGIN_DATA}` not `<repo>/.git/`:** plugin-internal cache stays with plugin; doesn't leak into repo's `.git/info/exclude` setup; survives plugin updates.

### 7.4 Squash-Merge vs Merge-Commit Detection (using `git cherry`)

Per Gap Review B4, refined via Boucle `worktree-guard` insight. When a branch's PR is merged, distinguish dangerous (squash/rebase) from safe (merge-commit):

```bash
git cherry "origin/$DEFAULT_BRANCH" "$BRANCH"
```

Each line is `+ <sha>` (commit not yet applied to default) or `- <sha>` (commit already applied, possibly under different SHA via squash/rebase).

- All `+ ` lines means branch has unmerged work → SAFE to resume work, but may still be old.
- All `- ` lines means every commit's patch is already in default → DANGEROUS to resume (squash-merge trap).
- Mixed → typically also DANGEROUS (some patches applied, some not — recovery via cherry-pick to fresh branch).

This is more accurate than `git merge-base --is-ancestor` because it handles squash-rewritten content correctly.

Confirmation (advisory): `gh pr view <num> --json mergeMethod` returns `SQUASH | MERGE | REBASE`. Use as cross-check but don't rely on it solely.

### 7.5 Worktree Behavior

Per Gap Review A2 + Boucle `worktree-guard`:

- All hook scripts use `git -C "$PWD"` (or equivalent) to ensure worktree's branch is queried, not main checkout's.
- `/tcs-git-helpers:status --cleanup` filters branches via `git worktree list --porcelain` — branches checked out in any worktree are NOT proposed for deletion (would error in `git branch -d`).
- `core.hooksPath` is shared across worktrees (set in main `.git/config`), so hooks fire correctly in all worktrees.
- `worktree-exit-guard.sh` (§6.2.4) addresses the data-loss-on-exit case Boucle identifies.

### 7.6 Submodules

Per Gap Review A3. `/tcs-git-helpers:setup` does NOT recurse into submodules. Setup output explicitly notes: *"Submodules detected: <list>. tcs-git-helpers is not installed in submodules — run setup separately if needed."*

---

## 8. Cross-Repo Rollout Plan

### Phase 1: TCS itself (dogfood)
- Build plugin in this repo (`feat/tcs-git-safety` branch — legacy name, can rename via `gh pr edit` or new branch)
- Test by enabling plugin and running `/tcs-git-helpers:setup` against TCS itself
- Validate hook behavior on synthetic scenarios

### Phase 2: Kado (real migration test)
- Kado has existing `.githooks/pre-commit` + `commit-msg` — overlap with new templates
- Auto-detect `_outbox/` hardcoded exception → migrate to `.githooks/exclude-paths`
- Backup existing files, install new versions
- Validate via Kado's existing CI

### Phase 3: Other MiYo repos in parallel
- Hakobi, Tomo, Kokoro, Kouzou, Seigyo, Hashi
- Same setup pattern; less overlap risk than Kado

### Phase 4: User-global hook stays
- `~/.claude/hooks/block-main-edits.sh` is **not retired** (revised from earlier draft). It remains as universal baseline for repos without the plugin enabled.
- Plugin's `pre-edit-branch-check.sh` runs alongside; deny semantics aggregate; no conflict.

### Phase 5 (optional, post-v1.0): GHA + branch-protection per repo
- `/tcs-git-helpers:setup --with-gha` for repos that want PR-title validation
- `/tcs-git-helpers:setup --with-branch-protection` for repos that want GH branch-protection
- Each repo decides individually

---

## 9. Decisions to Lock in PRD/PLAN Phase

These are intentionally deferred from this brainstorm:

1. **Versioning policy** — `tcs-git-helpers` semver scheme (probably bumping minor for new hooks, patch for fixes).
2. **`.githooks/.config` parser implementation language** — Bash (in `lib/config_parser.sh`) preferred for hook startup time (`pre-commit`/`commit-msg` invoke per commit). Confirm during PLAN.
3. **Cache file format details** (§7.3) — JSON vs simpler line-based format for parse speed.
4. **Hook test harness** — bats-core for shell, pytest for Python. Confirm during PLAN.
5. **GitHub Actions PR-title check** — match commit-msg regex exactly? Stricter? Pluggable?
6. **Reference content first-pass** — content quality bar for `best-practices.md` and other refs beyond `squash-merge-trap.md`. Likely Claude with Marcus review.
7. **Exact event for `worktree-exit-guard`** — `WorktreeRemove` vs `SessionEnd` vs `Stop` — needs runtime testing.
8. **Branch-protection preset** — what default rules does `--with-branch-protection` set? (PR required, status checks, no force-push, no deletions, dismiss-stale-reviews, etc.)
9. **Allowlist file** — Boucle's per-repo `.git-safe` allowlist concept. v1.0 uses env-var overrides; v1.1 may add file-based.
10. **PR/branch rename** — current branch is `feat/tcs-git-safety`; should rename to match plugin name during PRD or implementation phase.

---

## 10. Approaches Considered & Why This One Won

### Plugin granularity
- **Single `tcs-git-helpers` plugin (chosen)** — coherent versioning; one install/uninstall; matches scope (git-related discipline beyond just safety)
- Extend `tcs-helper` — too broad; mixes concerns
- Two plugins (claude-hooks + repo-githooks) — over-engineering; nothing benefits from independent install

### Distribution mechanism
- **Copy with version marker for `.githooks/`, plugin-internal for Claude hooks (chosen)** — `.githooks/` committed in repo for Docker/CI/non-Claude consumers; Claude hooks coupled to plugin lifecycle so install/disable means trust signal
- All copy-with-version (earlier draft) — added user-global install complexity; user-global hooks don't benefit from plugin's `${CLAUDE_PLUGIN_ROOT}` ergonomics; protection should follow plugin
- `core.hooksPath` redirect to plugin cache — `.githooks` not committed; loses Docker/CI protection
- Symlinks — Windows quirky, Docker-mount issues, git symlink edge cases

### Hook layer for Claude-side
- **Plugin-internal `hooks/hooks.json` (chosen)** — protection coupled to plugin install; clear lifecycle; uses `${CLAUDE_PLUGIN_ROOT}` for bundled scripts; uses `${CLAUDE_PLUGIN_DATA}` for cache
- User-global `~/.claude/hooks/` (earlier draft) — fires regardless of plugin state, but: (a) requires explicit user-global install step, (b) decoupling protection from plugin signals "always on" which contradicts user's desire for plugin-coupled trust, (c) loses plugin-env-var ergonomics

### Enforcement style
- **Hard-deny + granular env-var escapes for safety; soft-nudge PostToolUse for follow-ups (chosen)** — hard for catastrophic ops, soft for reminders
- All hard-deny — too aggressive for follow-up reminders that aren't violations
- All soft warnings — too easy for Claude to ignore on real violations
- Workflow-only (skills replacing raw `git`) — bypassed by direct git calls; weakest enforcement

---

## 11. References to Existing Material

### Internal (to be inherited/superseded)
- `~/.claude/hooks/block-main-edits.sh` — kept as universal baseline; plugin's `pre-edit-branch-check.sh` runs alongside
- `~/Kouzou/standards/git-conventions.md` — Conventional Commits format basis
- `~/Kouzou/standards/general.md` — branch-before-edit rule, push-every-10-commits rule
- `/Volumes/Moon/Coding/MiYo/Kado/.githooks/pre-commit` — basis for generalized pre-commit
- `/Volumes/Moon/Coding/MiYo/Kado/.githooks/commit-msg` — length-check inherited
- Marcus's existing finding on squash-merge branch reuse → becomes `references/squash-merge-trap.md`

### External prior art (Boucle-framework — pattern source)
- `https://github.com/Bande-a-Bonnot/Boucle-framework/tree/main/tools/git-safe` — destructive-op prevention patterns absorbed into §6.2.1
- `https://github.com/Bande-a-Bonnot/Boucle-framework/blob/main/tools/branch-guard` — protected-branches configurability absorbed into §6.3.1
- `https://github.com/Bande-a-Bonnot/Boucle-framework/blob/main/tools/worktree-guard` — exit-time data-loss prevention absorbed into §6.2.4; `git cherry` for squash-merge detection absorbed into §7.4

Boucle's source itself is not vendored; we re-implement to match TCS conventions and integrate with our reference docs / nudge hooks / config system.

---

## 12. Open Questions for Next Phase

These don't block PRD writing but should be resolved during PLAN:

1. How does the plugin handle Marcus opening the same repo from both host TCS session and Docker container session? Worktree-style separation, or shared `.githooks/`?
2. `references/` — plugin-internal only (current §6.1) or also installed into the repo for offline/off-Claude use?
3. Initial content quality bar for `best-practices.md` and other references — full curated set in v1.0, or stubs that grow?
4. **Skill discoverability issue** — `/tcs-helper:finish-branch` triggered in a different repo unexpectedly. Suggests skill descriptions are too broad. Investigate as separate concern (not blocked on this plugin); possible fixes: tighter skill descriptions, repo-context awareness in skill invocation. Track in tcs-helper, not here.
5. Allowlist mechanism (Boucle `.git-safe` style) for v1.1 — design + scope decision.
6. Branch-protection preset (§9 #8) — exact rules and how to expose customization.
7. Plugin disable/uninstall semantics — when plugin disabled, the Claude-side protection vanishes. Is this surfaced anywhere (e.g. `session-start-brief.sh` warns "plugin disabled — no Claude-side git safety")? Probably yes, but design per PLAN.

---

**End of brainstorm spec.** Ready for `/xdd <this-file>` to enter PRD phase.
