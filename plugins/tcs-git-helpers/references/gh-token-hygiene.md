# gh token hygiene

> Required scopes for `--with-branch-protection`, why excessive scopes
> warn (not block), and the `gh auth refresh` recovery.

## What goes wrong

The `gh` CLI authenticates with a token that carries a set of OAuth
scopes. When `/tcs-git-helpers:git-setup --with-branch-protection` runs, it
calls `gh api -X PUT …/protection` and `gh api -X PATCH …
delete_branch_on_merge=true`. Both endpoints require the `repo` scope.

Two failure modes to be aware of:

**1. Insufficient scope — setup blocks.** If the token lacks `repo`, the
`gh api` call fails with HTTP 403 / 404 and the setup skill aborts
non-zero. The fix is one-line: `gh auth refresh -s repo`.

**2. Excessive scope — setup warns.** If the token has `admin:org`,
`delete_repo`, `admin:repo_hook`, `admin:public_key`,
`admin:enterprise`, `site_admin`, or `workflow` (without
`--with-gha`), the operation will succeed but the token's blast
radius is larger than needed. A leak (env-var spill in a screen-share,
a stray `printenv` in logs, a gist-paste of `gh auth status`) becomes
proportionally more dangerous:

- `delete_repo` — repo deletion across the user's repos.
- `admin:org` — org-level write across all org repos.
- `admin:repo_hook` — install/modify webhooks (data exfiltration).
- `admin:public_key` — install SSH keys on the account.
- `workflow` — push to `.github/workflows/*` and trigger Actions runs
  (CI takeover); only needed if you also `--with-gha`.

The setup skill warns and requires interactive `y` confirmation to
proceed (per integration.md §9 token UX matrix). With `--yes`, the
warn still logs to stderr.

The tradeoff in ADR-12: warn rather than block, because the token is
the user's; blocking would force token rotation just to use the
plugin, which is too aggressive for a single-coder workflow.

## How to detect

**Current token scopes:**

```bash
gh auth status
# github.com
#   ✓ Logged in to github.com as marcus (oauth_token)
#   ✓ Token: gho_************************************
#   ✓ Token scopes: 'gist', 'read:org', 'repo', 'workflow'
```

The `Token scopes:` line is what the plugin parses. Programmatic form
(verified in integration.md §9):

```bash
SCOPES=$(gh auth status 2>&1 \
  | grep -oE "Token scopes: '[^|]+" \
  | sed -E "s/.*: '//;s/', '/,/g;s/'$//")
echo "$SCOPES"
# → gist,read:org,repo,workflow

# Alternative — direct from API response header:
gh api -i user 2>&1 | awk -F': ' '/^X-Oauth-Scopes:/ {print $2}'
```

**Setup-time UX matrix** (per integration.md §9):

| Token scopes | `--with-branch-protection` behavior |
|---|---|
| Missing `repo` | **Block** — print `gh auth refresh -s repo` and exit non-zero |
| `repo` only | Proceed silently |
| `repo` + excessive (`admin:org`, `delete_repo`, `admin:repo_hook`, `admin:public_key`, `admin:enterprise`, `site_admin`) | **Warn + confirm** — list excessive scopes, link to <https://github.com/settings/tokens>, require `y` |
| `repo` + `workflow` AND `--with-gha` requested | Proceed silently (`workflow` is necessary) |
| `repo` + `workflow` AND `--with-gha` NOT requested | Soft warn (single stderr line, no confirm) |

**Detect what the token can actually do** (a sanity check separate from
declared scopes):

```bash
gh api user --jq '.login'              # who am I?
gh api repos/<owner>/<repo> --jq '.permissions'  # repo-level perms
```

Fine-grained tokens may have narrower effective permissions than their
classic-scope equivalents; the per-repo view is more accurate for
those.

## Fix

**Insufficient scope — refresh:**

```bash
gh auth refresh -s repo
# Opens browser to GitHub's OAuth approval flow.
# Approves the additional scope; gh updates the stored token.
```

If `--with-gha` is also intended:

```bash
gh auth refresh -s repo,workflow
```

**Excessive scope — rotate to a minimal token.** Two flavors of token,
pick one:

### Option A — Fine-grained personal access token (recommended)

Fine-grained tokens scope to specific repos with explicit permissions.
For `--with-branch-protection` on one repo:

1. Go to <https://github.com/settings/tokens?type=beta>
2. Click **Generate new token**.
3. **Token name:** something descriptive, e.g. `tcs-git-helpers — repo X`.
4. **Expiration:** 90 days (rotate quarterly; see Prevention).
5. **Repository access:** *Only select repositories* → pick the one
   repo.
6. **Repository permissions:**
   - **Administration:** Read and write (for branch protection).
   - **Contents:** Read and write (for PR / branch operations).
   - **Pull requests:** Read and write (for `gh pr` calls).
   - **Metadata:** Read (always required, auto-included).
7. Click **Generate token** and copy the value.
8. Replace your current token:

   ```bash
   gh auth logout                   # removes the over-scoped token
   gh auth login --with-token < /path/to/token.txt
   # Or paste interactively:
   # gh auth login → "Paste an authentication token"
   ```

9. Verify:

   ```bash
   gh auth status
   ```

### Option B — Classic token with minimal scopes

If fine-grained doesn't fit (some `gh` commands aren't yet supported):

1. Go to <https://github.com/settings/tokens> (classic).
2. **Generate new token (classic)**.
3. **Note:** descriptive name.
4. **Expiration:** 90 days.
5. **Scopes:** check **only** `repo`. (Add `workflow` only if you also
   need GHA management.)
6. **Generate**, copy, and:

   ```bash
   gh auth logout
   gh auth login --with-token < /path/to/token.txt
   gh auth status        # confirm scopes show only `repo` (and maybe `workflow`)
   ```

7. **Revoke the old over-scoped token** at
   <https://github.com/settings/tokens> — click **Delete** next to it.
   `gh auth logout` only removed it locally; the GitHub-side token is
   still valid until revoked.

**If the warning fired but you'd already accepted the risk:** the
setup skill records the warning to the audit log
(`${CLAUDE_PLUGIN_DATA}/audit/overrides.jsonl`). No further action; the
trail exists for a future review.

## Prevention

- **Prefer fine-grained tokens over classic.** Per-repo scoping is the
  largest single reduction in blast radius.
- **One token per use case, not one token for everything.** The
  branch-protection token can be repo-scoped and short-TTL; a separate
  token for `gh repo create` operations carries `repo` + `workflow` if
  needed.
- **Rotate quarterly.** Set a calendar reminder; tokens with no
  expiration outlive the contexts that motivated them.
- **Never put `admin:org` on a personal-use token.** If you need
  org-level write, use the org's dedicated automation account.
- **Don't paste `gh auth status` output into chat / docs / gists.** The
  token value is masked, but the scope list combined with the username
  is enough for an attacker to know what they have if they later
  steal the token (e.g., from a leaked env file).
- **Trust the warning.** The setup skill's confirm prompt exists
  precisely so excessive scopes don't slip through silently. If you
  hit it routinely, the lesson is to rotate to a minimal token.

## Why

GitHub's token model lets you scope tightly, but the default UX nudges
toward broad scopes (the OAuth flow's "select all" buttons; the
classic-token UI grouping `repo` with `repo:status`, `repo_deployment`,
etc.). The plugin's `--with-branch-protection` requires only `repo` for
classic tokens, or three specific permissions on a fine-grained token.
Anything more is unnecessary surface.

ADR-12 (single-coder branch-protection preset) is built around the same
principle: the protection rules don't require organizational features
(no PR-review-required, no admin-bypass), so the token shouldn't carry
organizational scopes either. One repo, one token, minimum scopes — no
shared-secret rotation problem, no role-escalation surface.

The warn-not-block decision in the UX matrix (integration.md §9) was a
deliberate trade-off: a token forced rotation to use the plugin would
push users toward the master override (`--yes` + ignore the warn), or
toward not running `--with-branch-protection` at all. The warn signals
the principle of least privilege without dictating; the audit log
records that the user saw and accepted the warning.

A note on `gh auth login` defaults: the OAuth flow's default scope set
is broader than what most operations need. If you ran `gh auth login`
once long ago and have not rotated, the token almost certainly carries
more scopes than you remember. `gh auth status` is the cheapest way to
check.

---

## See also

- [`sandbox-and-git-config.md`](sandbox-and-git-config.md) — why
  `gh api` calls are the only network surface from the plugin.
- [`best-practices.md`](best-practices.md) — §1 pre-flight branch
  state; the brief surfaces gh auth status.
- ADR-12 in `docs/XDD/specs/011-tcs-git-helpers/solution.md` — the
  single-coder branch-protection preset.
- GitHub fine-grained tokens: <https://github.com/settings/tokens?type=beta>
- GitHub classic tokens: <https://github.com/settings/tokens>
- `gh auth refresh` docs: <https://cli.github.com/manual/gh_auth_refresh>
