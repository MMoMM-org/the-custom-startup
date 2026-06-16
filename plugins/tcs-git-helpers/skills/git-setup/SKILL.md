---
name: git-setup
description: "Use when installing or updating tcs-git-helpers in a target repo. MUST BE USED whenever the user says install hooks, install tcs-git-helpers, run git-setup, update hooks, or hook conflicts (Husky, lefthook, pre-commit, simple-git-hooks). Triggers on: git-setup, install hooks, update hooks, conflicts."
user-invocable: true
argument-hint: "[--update | --with-gha | --with-branch-protection]"
allowed-tools: Bash, Read, Write, Edit
---

## Persona

**Active skill: tcs-git-helpers:git-setup**

Idempotent per-repo installer for the `tcs-git-helpers` plugin. Orchestrates conflict detection, file copies, `core.hooksPath` configuration, and optional GitHub Actions / branch-protection setup. Does NOT auto-commit — Marcus reviews and commits the resulting changes.

## Interface

```
Mode {
  default                    → install hooks fresh (clean repo) OR detect existing
                                state and branch into the appropriate sub-flow
  --update                   → re-install/refresh hooks; show per-file diff
                                before overwriting an older marker
  --with-gha                 → also copy templates/github-actions/pr-title-check.yml
                                into <repo>/.github/workflows/
  --with-branch-protection   → invoke the branch-protection helper; applies
                                the ADR-12 single-coder preset via `gh api`.
                                Idempotent (re-run is a no-op if protection
                                already matches). Set `TCS_BP_YES=1` to skip
                                the interactive confirm prompt.
}

ExitCode {
  0  success — hooks installed (or already up to date) and summary printed
  1  fatal — not a git repo / templates missing / unrecoverable IO error
  2  abort — Husky/lefthook/pre-commit/simple-git-hooks/custom hooksPath
            detected (see `references/migrating-from-husky.md`)
  3  conflict — existing .githooks/ without a tcs-git-helpers marker, or
            older marker (use --update or accept per-file diff prompt)
  4  warn — non-.sample files in .git/hooks/ or other soft conditions; the
            skill should ask the user to confirm before proceeding
}

Sentinel {
  TCS_GIT_HELPERS_SETUP_ACTIVE=1   exported INSIDE a (subshell) only,
                                    bounding its scope per ADR-11. Required
                                    so the protect-git-internals.sh
                                    PreToolUse hook permits writes to
                                    .githooks/* and .git/config.
}
```

Spec refs:
- PRD §Feature M10 — Plugin distribution + per-repo setup (AC1–AC6)
- PRD §Feature S1 — `--with-branch-protection`
- PRD §Feature S2 — `--with-gha`
- SDD §Skills — `/tcs-git-helpers:git-setup` workflow
- SDD §Cross-Cutting — UI Visualization Guide
- ADR-10 (conflict abort policy: Husky/lefthook/pre-commit/simple-git-hooks)
- ADR-11 (`TCS_GIT_HELPERS_SETUP_ACTIVE` subshell sentinel)
- ADR-12 (single-coder branch-protection preset)
- integration §5 (conflict-detection signatures), §9 (token-scope matrix)

## Constraints

**Always:**
- Acquire `<repo>/.githooks/.setup.lock` via `lib/lock.sh acquire` BEFORE any write. Reclaim stale locks (>5 min OR dead PID) automatically.
- Run `lib/detect_conflicts.sh` BEFORE `lib/install_files.sh`. Branch on the exit code: 0 = clean install or up-to-date noop; 2 = abort with reference doc; 3 = conflict (per-file diff / `--update` flow); 4 = warn + confirm.
- Wrap every filesystem write to `.githooks/*` and `.git/config` in a subshell that exports `TCS_GIT_HELPERS_SETUP_ACTIVE=1` (ADR-11). The skill's `lib/install_files.sh` already does this — call it directly rather than re-implementing.
- Print a structured summary listing what was copied, the configured `core.hooksPath`, and any conflicts/warnings encountered (M10 AC1).
- For `--with-gha`: call `lib/with_gha.sh` after the core install completes successfully.
- For `--with-branch-protection`: call `lib/with_branch_protection.sh`. The helper is idempotent and can be re-run independently of the rest of setup.
- Release the lock via `lib/lock.sh release` on exit, including error paths.
- Cite `references/migrating-from-husky.md` whenever the skill aborts on Husky / lefthook / pre-commit / simple-git-hooks / custom-hooksPath.

**Never:**
- Auto-commit the installed files. Setup never runs `git add` / `git commit`. Marcus reviews and commits manually (M10 AC5).
- Write outside the documented surface: `<repo>/.githooks/*`, `<repo>/.git/config` (only `core.hooksPath`), and (with `--with-gha`) `<repo>/.github/workflows/pr-title-check.yml`. Anything else requires explicit user confirmation.
- Bypass conflict detection. Even with `--update`, run `lib/detect_conflicts.sh` first so the skill behaves consistently against Husky-mid-migration repos.
- Bypass the lock. Two concurrent setup runs MUST serialize on `.githooks/.setup.lock`.
- Recurse into submodules. List them in the summary but do not enter (M10 AC6).
- Export `TCS_GIT_HELPERS_SETUP_ACTIVE` in the parent shell. Subshell only.
- Run `gh api` directly from this skill's main flow. Branch-protection writes go through `lib/with_branch_protection.sh`.

## Workflow

### 1. Acquire the per-repo setup lock

```bash
"${CLAUDE_PLUGIN_ROOT}/skills/git-setup/lib/lock.sh" acquire
```

The helper writes `<repo>/.githooks/.setup.lock` containing `<pid>:<unix-timestamp>`. A second concurrent invocation will wait up to `TCS_LOCK_TIMEOUT` seconds (default 10 s) before failing; set `TCS_LOCK_TIMEOUT=0` to fail immediately. Locks older than 5 minutes (or with dead PIDs) are reclaimed automatically.

If acquire fails, surface the error (`another setup run holds .githooks/.setup.lock`) and exit non-zero — do NOT force-remove a foreign lock.

**Ordering note.** The lock is acquired FIRST (before conflict detection) so two concurrent runs serialize across the whole detect→install sequence, not just the write. Acquiring creates `<repo>/.githooks/` plus the bare `.setup.lock` before step 2 runs, so on a fresh repo the conflict detector sees a `.githooks/` that contains only the lock. `detect_conflicts.sh` explicitly ignores a `.githooks/` that holds nothing but `.setup.lock` (or is otherwise empty) and treats it as a clean install — the lock never counts as a pre-existing foreign hook set. `install_files.sh` (step 4) also writes `.githooks/.gitignore` so `.setup.lock` is never committed.

### 2. Detect conflicts

```bash
"${CLAUDE_PLUGIN_ROOT}/skills/git-setup/lib/detect_conflicts.sh"
```

Branch on the exit code:

| Exit | Meaning | Action |
|------|---------|--------|
| 0 | clean OR matching version | Continue to step 4 (or skip if up-to-date noop) |
| 2 | Husky / lefthook / pre-commit / simple-git-hooks / non-`.githooks` `core.hooksPath` | **Abort.** Cite `references/migrating-from-husky.md`. Release lock, exit 2. |
| 3 | Existing `.githooks/` no marker, OR older version marker | Conflict / per-file diff flow. With `--update`: show diff and prompt before overwrite. Without: prompt before continuing. |
| 4 | Non-`.sample` `.git/hooks/*` files OR other soft warning | Warn. Confirm interactively before proceeding (existing files won't fire under `core.hooksPath` but are visible noise). |

The detector's stdout includes one line per condition with severity tag (`ABORT`, `CONFLICT`, `OUTDATED`, `WARN`, `INFO`, `OK`, `REF`). Surface all of it to the user.

### 3. User confirmation

Per ADR-10 + sandbox-and-git-config.md:

- **Claude invoking:** Print the conflict summary and the planned actions. Wait for user `y`/`yes` confirmation in chat before proceeding past any non-`OK` finding. The Bash hook `protect-git-internals.sh` denies the actual write anyway unless the sentinel is set, so confirmation is procedural — but the skill must not act surprised when the hook denies an unprompted Edit/Write call.
- **Marcus invoking directly:** Same prompt; Marcus types the response.

### 4. (Subshell) install hooks

```bash
"${CLAUDE_PLUGIN_ROOT}/skills/git-setup/lib/install_files.sh"
```

Internally this opens a `(subshell)`, exports `TCS_GIT_HELPERS_SETUP_ACTIVE=1`, copies templates, `chmod +x`s hook scripts, runs `git config core.hooksPath .githooks`, and exits the subshell so the sentinel does NOT leak into the parent. Verified by `tests/bats/skill_git_setup.bats::C26`.

After this step, the repo has:

- `<repo>/.githooks/{pre-commit,pre-push,commit-msg,post-merge}` (executable, version banner substituted from `plugin.json` at install time — see ADR-13)
- `<repo>/.githooks/.config.example` and `<repo>/.githooks/exclude-paths.example`
- `<repo>/.git/config` with `[core] hooksPath = .githooks`

### 5. (Optional) `--with-gha`

```bash
"${CLAUDE_PLUGIN_ROOT}/skills/git-setup/lib/with_gha.sh"
```

Copies `templates/github-actions/pr-title-check.yml` into `<repo>/.github/workflows/`. Idempotent: an existing tcs-git-helpers-managed workflow is refreshed silently; a foreign workflow is left alone with a warning (override via `TCS_GHA_FORCE=1`).

### 6. (Optional) `--with-branch-protection`

```bash
"${CLAUDE_PLUGIN_ROOT}/skills/git-setup/lib/with_branch_protection.sh"
```

Applies the ADR-12 single-coder branch-protection preset to the repo's default branch via `gh api PUT /repos/:owner/:repo/branches/<default>/protection`. Behavior:

- **Pre-flight scope check.** Requires `repo` scope; warns (but proceeds with confirm) on excessive scopes such as `admin:org` or `delete_repo`. Cites `references/gh-token-hygiene.md` in both the missing-scope abort and the excessive-scope warning.
- **Plan + confirm.** Prints the planned ruleset and waits for `y`/`yes` before writing. Set `TCS_BP_YES=1` to skip the prompt for non-interactive use (e.g. scripted setup).
- **Idempotent.** If the existing protection on the default branch already matches the preset, the helper exits 0 with an "already up to date" message and issues no `PUT`. Re-running is safe.
- **Best-effort `delete_branch_on_merge`.** PATCHes the repo setting to enable auto-delete on merge; failure is non-fatal (logged, helper continues).
- **Failure mode.** If `gh api` fails (network error, auth error, rate-limit, 422), the helper exits non-zero. The surrounding setup state — installed `.githooks/*` files, `core.hooksPath = .githooks`, and any `--with-gha` workflow already copied — is **not** rolled back. Marcus reviews the error, fixes the underlying issue (re-auth, scope upgrade, network), and re-runs `--with-branch-protection` on its own.

### 7. Print summary + release lock

Always print a structured summary listing:

- Files copied (with destination paths).
- `core.hooksPath` value.
- Any conflicts or warnings encountered.
- Submodules listed (not recursed) per M10 AC6.
- Reminder: setup did NOT auto-commit; Marcus reviews via `git status` then commits.

Release the lock on EVERY exit path — success, abort (exit 2), conflict that the user declines, and any error in between:

```bash
"${CLAUDE_PLUGIN_ROOT}/skills/git-setup/lib/lock.sh" release
```

`release` removes the lock when the current process owns it OR when the recorded owner PID is no longer alive — so it cleans up correctly even though the skill runs `acquire` and `release` as separate Bash calls (different PIDs). A lock owned by a *live* foreign run is never force-removed. If you abort before reaching this step, run `release` explicitly (e.g. in a `trap`) so a dead-PID lock is not left in `.githooks/`.

## Conflict matrix

| Detected condition | Signature | Severity | Action |
|---|---|---|---|
| Husky v8/v9 | `.husky/` directory; `package.json` `"husky"` key or `"prepare":"husky install"` | **ABORT** | `references/migrating-from-husky.md` |
| Husky v4 | `package.json` `"husky": {"hooks": {…}}` | **ABORT** | `references/migrating-from-husky.md` |
| lefthook | `lefthook.yml` / `lefthook.yaml` / `.lefthook.yml` at repo root | **ABORT** | `references/migrating-from-husky.md` |
| pre-commit framework | `.pre-commit-config.yaml` at repo root | **ABORT** | `references/migrating-from-husky.md` |
| simple-git-hooks | `package.json` `"simple-git-hooks"` key | **ABORT** | `references/migrating-from-husky.md` |
| Custom `core.hooksPath` | `git config --get core.hooksPath` is non-empty AND ≠ `.githooks` | **ABORT** | `references/migrating-from-husky.md` + `references/sandbox-and-git-config.md` |
| Existing `.githooks/`, no marker | No `# tcs-git-helpers: vX.Y.Z` line on lines 1–3 of any standard hook | **CONFLICT** | Per-file diff prompt |
| Existing `.githooks/`, matching version | Marker `v1.0.0` present | **OK** | Up-to-date noop; skip step 4 |
| Existing `.githooks/`, older version | Marker `vX.Y.Z` < `v1.0.0` | **OUTDATED** | Use `--update` to refresh |
| `.git/hooks/*` non-`.sample` | At least one non-`.sample` file under `.git/hooks/` | **WARN** | Confirm; existing files won't fire under `core.hooksPath` |
| Submodules present | `.gitmodules` exists | **INFO** | List submodules in summary; do NOT recurse |

## References

- `references/migrating-from-husky.md` — abort-and-migrate workflow (covers Husky, lefthook, pre-commit, simple-git-hooks).
- `references/sandbox-and-git-config.md` — why `git config core.hooksPath` writes are gated on the sentinel.
- `references/gh-token-hygiene.md` — token-scope matrix for `--with-branch-protection`.
- `references/INDEX.md` — full reference catalog.
