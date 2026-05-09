# Integration Research — `tcs-git-helpers`

**Researcher:** Integration lens · **Date:** 2026-05-08
**Scope:** External-boundary contracts: `gh` CLI, GitHub API, Claude Code hook lifecycle, Boucle prior art, conflict detection.

---

## 1. External Dependency Inventory

| Dependency | Min version | Verified | Fallback if unavailable |
|---|---|---|---|
| `git` | 2.30+ | 2.50.1 | None — setup aborts |
| `gh` CLI | 2.0+ (stable JSON) | 2.88.1 | Push-state checks **fail-open + stderr warn** (§7.2 of brainstorm) |
| GitHub API v3/v4 | n/a | Endpoint reachable | `--with-branch-protection` fails loud; core hooks unaffected |
| Bash | 3.2+ (macOS default) | n/a | Required |
| `coreutils timeout(1)` | any | **Not in macOS PATH** | See §8 — bash-only fallback recommended |
| Python 3.9+ | for `git_status_audit.py` only | local 3.x | Status skill unavailable; hooks unaffected |

**`gh` auth:** `gh auth status` exit 0 = logged in. Token scope **`repo`** is sufficient for branch protection PUT. Marcus's token has `repo, workflow, gist, read:org` ✓.

---

## 2. `gh` CLI Contract

### 2.1 `gh pr list --head <branch> --state all --json state,number,mergedAt --limit 1`

Verified gh 2.88.1:

| Scenario | exit | stdout | stderr |
|---|---|---|---|
| No PR / unknown branch | `0` | `[]` | empty |
| Open PR | `0` | `[{"state":"OPEN","number":N,"mergedAt":null}]` | empty |
| Merged PR | `0` | `[{"state":"MERGED","number":N,"mergedAt":"…"}]` | empty |
| Not a GitHub remote | `1` | empty | `no GitHub remote found` |
| Auth missing | `4` | empty | `gh auth login` prompt |
| Network / 5xx / 404 | `1` | empty | `dial tcp …` / `HTTP 4xx/5xx` |

State enum: `OPEN | CLOSED | MERGED | DRAFT`. Closed-without-merge = `CLOSED` (`mergedAt: null`). **`[]` does not distinguish "no PR" from "branch unknown to GH"** — both look identical → fail-open is correct (§7.2 caveat).

### 2.2 Squash-merge confirmation — brainstorm §7.4 needs correction

**`mergeMethod` is NOT a `--json` field on `gh pr list` or `gh pr view`** (verified — both error: `Unknown JSON field: "mergeMethod"`). Available: `mergeCommit`, `mergedAt`, `mergeStateStatus`. Replace brainstorm §7.4's cross-check with:
```bash
SHA=$(gh pr view "$NUM" --json mergeCommit --jq '.mergeCommit.oid')
PARENTS=$(git rev-list --parents -n 1 "$SHA" | awk '{print NF-1}')   # 1=squash/rebase, 2=merge
```
Or GraphQL `pullRequest.mergeCommit.parents.totalCount`. **Primary detector remains `git cherry` (§7.4).** This is the cross-check only.

### 2.3 Branch protection (G12)
`PUT /repos/{owner}/{repo}/branches/{branch}/protection` — scope `repo`, repo admin (single-account = always admin). `GET …/protection` returns `404 Branch not protected` (gh exit 0, parseable). Auto-delete: `PATCH /repos/{owner}/{repo}` with `delete_branch_on_merge=true`. ≤3 calls per repo → rate limits irrelevant.

### 2.4 Auth preflight
`gh auth status --active --hostname github.com` — exit 0 logged-in. Use exit code, not stderr text (versions ≥ 2.40 stable).

---

## 3. Hook Event Verification — RESOLVES §6.2.4

Source: <https://code.claude.com/docs/en/hooks> (fetched 2026-05-08).

| Event | Can deny? | Use |
|---|---|---|
| `PreToolUse` (`Bash`) | ✅ `permissionDecision: "deny"` | §6.2.1 destructive-op blocker |
| `PreToolUse` (`Edit\|Write\|NotebookEdit`) | ✅ | §6.2.2 pre-edit branch check |
| `PostToolUse` (`Bash`) | ❌ | §6.6 nudges via stderr |
| `SessionStart` | ❌ | §6.2.3 brief (advisory) |
| **`SessionEnd`** | ❌ explicit non-blockable | **Cannot use for §6.2.4** |
| **`WorktreeRemove`** | ❌ "failures logged in debug mode only" | **Cannot use for §6.2.4** |
| **`PreToolUse` (`ExitWorktree`)** | ✅ | **Correct event for §6.2.4** — Boucle uses this |
| `Stop` | ✅ exit 2 | Fallback if `ExitWorktree` is bypassed |

**RESOLUTION:** brainstorm §6.2.4 / §9 #7 → use `PreToolUse` matcher `ExitWorktree`. Verified via Boucle `worktree-guard/hook.sh`. `ExitWorktree` is a Claude Code native tool (visible in this session's deferred-tool list).

→ `requirements-researcher`: update §6.2.4 wording to lock `PreToolUse:ExitWorktree`.

---

## 4. Boucle Absorption Mapping

Sources: Boucle-framework `tools/{git-safe,branch-guard,worktree-guard}` on github.com/Bande-a-Bonnot.

### 4.1 `git-safe` → `block-bad-git-ops.sh` (§6.2.1)
- **Keep 1:1:** regex set for `--no-verify`, `reset --hard`, `checkout .`, `restore --worktree`, `clean -f`, `branch -D`, `stash drop/clear`, `reflog expire`, `push --delete`, `push origin :branch`.
- **Keep + extend:** `--force` blocked / `--force-with-lease` allowed → also block `--force-with-lease` to protected branches.
- **Adapt:** master kill `GIT_SAFE_DISABLED=1` → `CLAUDE_ALLOW_GIT_BAD_OPS=1`; debug `GIT_SAFE_LOG=1` → `TCS_GIT_HELPERS_LOG=1`. Force-push-to-`main`/`master` rule → generalize to `TCS_PROTECTED_BRANCHES`.
- **Improve:** Boucle uses exit-code 2; we use modern `permissionDecision: "deny"` JSON output (richer reasons + override hints).
- **Defer:** `.git-safe` allowlist file → v1.1 (brainstorm §9 #9).
- **Skip:** `hook.ps1`, `install.sh`.

### 4.2 `branch-guard` → `pre-commit` (§6.3.1)
- **Keep:** default protected `main, master, production, release`.
- **Adapt:** `.branch-guard` separate file → fold into `.githooks/.config` `TCS_PROTECTED_BRANCHES` (single config); `BRANCH_GUARD_PROTECTED` → `TCS_PROTECTED_BRANCHES`.
- **Diverge:** Boucle allows `--amend` on protected; we deny by default, opt-in via `TCS_ALLOW_AMEND_ON_PROTECTED=1`.

### 4.3 `worktree-guard` → `worktree-exit-guard.sh` (§6.2.4)
- **Keep 1:1:** event = `PreToolUse:ExitWorktree`; four checks (uncommitted/untracked/unmerged/unpushed); `git cherry "origin/$base" "$branch"` for unmerged.
- **Improve:** base-branch detection — try `git symbolic-ref refs/remotes/origin/HEAD` first, then Boucle's fallback chain (`origin/main → origin/master → main → master`).
- **Defer:** Boucle's `.worktree-guard` per-check allow file; v1.0 uses single env var.

**No vendoring.** Re-implement; cite Boucle URLs in `references/destructive-ops.md` and `references/worktree-discipline.md`.

---

## 5. Conflict-Detection Signatures (§6.5.1 step 4)

| Tool | Signature | Action |
|---|---|---|
| Husky v8/v9 | `.husky/` dir (non-`_/` files); `package.json` `"husky"` key or `"prepare":"husky install"` | **Abort** — routes hooksPath; needs migration |
| Husky v4 | `package.json` `"husky": {"hooks": {…}}` | **Abort** |
| lefthook | `lefthook.{yml,yaml}` / `.lefthook.yml` at root | **Abort** |
| pre-commit (py) | `.pre-commit-config.yaml` | **Abort** |
| simple-git-hooks | `package.json` `"simple-git-hooks"` key | **Abort** |
| Custom `core.hooksPath` | `git config --get core.hooksPath` ≠ empty AND ≠ `.githooks` | **Abort** |
| Existing `.git/hooks/*` non-`.sample` | listed | **Warn** (won't fire — `core.hooksPath` overrides) |
| Existing `.githooks/` no marker | no `# tcs-git-helpers: vX.Y.Z` line | Per-file diff (brainstorm §6.5.1) |
| GHA PR-title (different) | `.github/workflows/*.yml` referencing `amannn/action-semantic-pull-request` or `actions-ecosystem/action-pr-title` | Conflict only if `--with-gha`; warn |

**Rationale for abort policy:** Husky/lefthook/pre-commit each set `core.hooksPath`. Coexistence is brittle. Document migration in `references/migrating-from-husky.md` (new doc).

→ `security-researcher`: Husky's `prepare` script runs arbitrary npm code on install. Note in security notes.

---

## 6. External Failure Modes

| Failure | Detection | Handling |
|---|---|---|
| `gh` not installed | `command -v gh` empty | Hooks degrade; setup `--with-branch-protection` hard-fail |
| `gh` unauthenticated | `gh auth status` ≠ 0 | Same |
| Network slow / partition | timeout > 5s | Fail-open + warn (`timeout 5 gh …`) |
| `timeout(1)` missing on macOS | `command -v timeout \|\| gtimeout` | **Open** — see §8 |
| GitHub 5xx | `gh` exit 1 + `HTTP 5xx` | Fail-open |
| Repo not on GitHub | `git remote get-url origin` no `github.com` | `pre-push` fail-open; `--with-branch-protection` aborts |
| Auth expires mid-session | gh auth error | Fail-open + nudge `gh auth refresh` |
| Rate limit | gh stderr `rate limit exceeded` | Fail-open (single-account: very rare) |
| GHE vs github.com | `gh auth status --hostname` | Setup detects host; gh handles transparently |

---

## 7. Squash-Merge Detection — Reliable Contract

Priority order, all three signals:

1. **Primary: `git cherry "origin/$DEFAULT" "$BRANCH"`** (Boucle method, brainstorm §7.4) — patch-equivalence, robust to SHA rewrites.
2. **Cross-check: merge-commit parent count** — `git rev-list --parents -n 1 <sha> | awk '{print NF-1}'`. `1` = squash/rebase, `2` = merge.
3. **Confirmation: `gh pr view --json mergeCommit,mergedAt,state`** — **not** `mergeMethod` (doesn't exist).

`git merge-base --is-ancestor` is insufficient (fails on squash — squashed branch's tip is not an ancestor of default).

---

## 8. Open Integration Questions for Marcus

1. **`timeout(1)` portability on macOS:** (a) require `brew install coreutils` (`gtimeout`); (b) bash-only background-kill fallback in `lib/git_state.sh`; (c) Python wrapper. **Recommend (b)** — keeps hooks dependency-free.
2. **Vendor Boucle?** Brainstorm §11 says no. Confirming. **Recommend: re-implement, cite URLs in `references/`.**
3. **Branch-protection preset (§9 #8):** PR-required, ≥1 review, dismiss-stale-reviews, no-force-push, no-deletions, require-up-to-date — exact rules need Marcus's call. Test on this repo first.
4. **`mergeMethod` correction:** brainstorm §7.4 names a non-existent JSON field. Replace with parent-count check (§2.2 above) or drop the cross-check and rely on `git cherry` alone?
5. **Multi-account gh auth:** Marcus has `MMoMM-org` active; `gh pr list` uses active context but auto-switches per-host. Setup should `gh auth status --hostname <host>` before `--with-branch-protection`.
6. **Husky/lefthook conflict policy:** confirm **abort + doc'd migration** (vs offer in-place migration). Recommend abort.

---

## 9. Token Scope Pre-Flight (cross-cut from security-researcher)

Before `--with-branch-protection`, validate scopes are **necessary AND sufficient**.

**Required scope:** `repo` (and that's it — branch-protection PUT, repo PATCH for `delete_branch_on_merge`, all under `repo`).
**Excessive (warn):** `admin:org`, `delete_repo`, `admin:repo_hook`, `admin:public_key`, `admin:enterprise`, `site_admin`, `workflow` (only needed for `.github/workflows/*` push, not protection setup).

**Detection (verified):**
```bash
SCOPES=$(gh auth status 2>&1 | grep -oE "Token scopes: '[^|]+" | sed -E "s/.*: '//;s/', '/,/g;s/'$//")
# alt: gh api -i user 2>&1 | awk -F': ' '/^X-Oauth-Scopes:/ {print $2}'
```
Both produce comma-list (e.g. `gist,read:org,repo,workflow`). Marcus's token: `gist,read:org,repo,workflow` — has `workflow` (excessive for branch-protection alone, fine if also installing GHA).

**UX policy:**

| Condition | Setup behavior |
|---|---|
| Missing `repo` | **Block** — print: `gh auth refresh -s repo` and exit non-zero |
| Has `repo` only | Proceed silently |
| Has `repo` + excessive scopes (`admin:org`, `delete_repo`, etc.) | **Warn + confirm** — list excessive scopes, link to <https://github.com/settings/tokens>, require interactive `y` (skip in `--yes` mode but still log to stderr) |
| Has `repo` + `workflow` AND `--with-gha` requested | Proceed silently (`workflow` is necessary) |
| Has `repo` + `workflow` AND `--with-gha` NOT requested | Soft warn (single stderr line; no confirm) |

**Why warn, not block, on excessive scopes:** the token is the user's; we can't revoke it. Blocking would force token rotation just to use this plugin — too aggressive. Warn signals the principle of least privilege without dictating.

**Implementation lives in:** `lib/git_state.sh` → `_check_gh_scopes()` (called only by `setup --with-branch-protection`, not by hot-path hooks).

→ `security-researcher`: confirm warn-vs-block matrix above. Worth a `references/gh-token-hygiene.md` doc?

---

## 10. Citations

- Hook events: <https://code.claude.com/docs/en/hooks> (cached `docs/ai/external/claude/hooks.md`, 2026-05-08)
- Boucle: `github.com/Bande-a-Bonnot/Boucle-framework/tree/main/tools/{git-safe,branch-guard,worktree-guard}`
- gh CLI 2.88.1 (`gh pr list --help`, `gh api --help`, verified locally)
- Branch protection: <https://docs.github.com/rest/branches/branch-protection>
- TCS baseline: `/Volumes/Moon/Coding/MiYo/Kado/.githooks/{pre-commit,commit-msg}`

— end Integration research.
