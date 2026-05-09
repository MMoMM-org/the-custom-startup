# Security Findings — tcs-git-helpers v1.0 (PRD phase)

Read brainstorm `docs/XDD/ideas/2026-05-08-tcs-git-safety.md` end-to-end. Findings below are framed as **seatbelt design**, not adversarial threat modeling.

---

## 1. Threat Model

**Adversary:** none in the traditional sense. Marcus is trusted; no external actor is in scope.

**Actor whose mistakes we're catching:** Claude — a stateless, capable, forgetful operator that reflexively reaches for destructive commands when a softer path exists. Claude is not adversarial but has *adversarial-shaped failure modes*: regex-evasion via shell idioms, forgetting it set an env var earlier, blindly following `references/*.md` content.

**Assets (in priority order):**
1. Uncommitted/unpushed work (irrecoverable)
2. Local git history & reflog (recoverable but easily destroyed: §6.2.1 reflog/reset/clean rows)
3. Remote branch & PR state (recoverable but socially expensive: §1 FM1 closed-PR pushes, FM3 squash trap)
4. Plugin & repo file integrity (`.githooks/`, `.config`, plugin scripts)

**Trust boundaries (high → low):**
Marcus → Plugin source-of-truth (`${CLAUDE_PLUGIN_ROOT}`) → Repo `.githooks/` (committed, reviewable) → `.githooks/.config` (per-repo, parsed) → Claude-issued shell commands (must pass hooks) → environment variables Claude exports (lowest trust, audit-logged).

**Attack surface:** Bash tool input strings, Write/Edit targets, JSON stdin to hooks, `.githooks/.config` contents, `gh` exit codes, `${CLAUDE_PLUGIN_DATA}` cache files, override env vars.

---

## 2. Per-Component Security Review (§6.2)

| Hook | Bypassed → | Buggy (false-pass) → | Buggy (false-deny) → |
|---|---|---|---|
| **block-bad-git-ops** (§6.2.1) | Destructive op runs; reflog usually saves it except for clean -f / reflog expire / push to closed PR | Same as bypass — **catastrophic for the destructive subset** | Annoying; Marcus overrides per-violation. Acceptable. |
| **pre-edit-branch-check** (§6.2.2) | Edits land on main; existing user-global `block-main-edits.sh` is a second line of defense (§4.3 layer) → tolerable | Edits on main land silently | Spurious denial blocks legit work; Marcus sets escape var |
| **session-start-brief** (§6.2.3) | No brief; Claude flies blind. Low security impact | **Misleading state report is worse than no report** — Claude trusts "clean" when not. Cache-staleness (§7.3 24h) must be surfaced loudly | Brief never blocks |
| **worktree-exit-guard** (§6.2.4) | **Data loss** — top-priority asset gone | Data loss without warning | Stuck worktree; one-shot override resolves |
| **nudge-hook** (§6.6) | Nudge missing; Claude proceeds. Low impact | Wrong nudge confuses Claude | n/a — non-blocking |

**Severity ranking:** worktree-exit-guard ≥ block-bad-git-ops (destructive subset) > pre-edit-branch-check > session-start-brief > nudges.

The destructive subset of §6.2.1 (`reset --hard`, `clean -f`, `reflog expire`, `branch -D`, `stash drop/clear`, push to closed PR with squash) deserves the strictest regex review — these are unrecoverable. Use a **dedicated test fixture corpus** (TDD) with known evasion strings.

---

## 3. Override-Hatch Hardening

The brainstorm's per-violation env-var design (§4.2) is correct. Concrete hardening:

**Required:**
1. **One-shot semantics for ALL overrides** — currently noted only for `CLAUDE_ALLOW_WORKTREE_EXIT_WITH_CHANGES` (§6.2.4). Generalize: hook checks env var, **unsets it after consuming**, requires re-set per attempt. Prevents Claude from exporting once and forgetting.
2. **Audit log per override** — append to `${CLAUDE_PLUGIN_DATA}/overrides.log` with `{timestamp, var, command, cwd, branch}`. Surface count in `session-start-brief.sh` ("3 overrides used in last session").
3. **Drop the master override `CLAUDE_ALLOW_GIT_BAD_OPS`** (§6.2.1) — or gate it behind a non-trivial value like `CLAUDE_ALLOW_GIT_BAD_OPS="$(date +%Y-%m-%d)"` matching today's date. A binary master flag is exactly the thing Claude will reflexively set; the granular flags exist precisely to *prevent* this.
4. **Stderr-warn when env var is set but operation isn't denied** — surfaces stale/forgotten overrides early.

**Not needed:** rate-limiting (annoying for legitimate work), expiry timers (one-shot supersedes), confirmation tokens beyond date-stamping (paranoid for a single-operator system).

---

## 4. `.config` Parser Security Spec (§6.4)

Key allowlist already correct. **Concrete parser rules** for `lib/config_parser.sh`:

```
For each line in .githooks/.config:
  1. Strip trailing CR (\r) — handle CRLF files
  2. Strip leading/trailing whitespace
  3. If empty OR starts with '#' → skip
  4. Match strict regex: ^([A-Z][A-Z0-9_]{0,63})=(.{0,256})$
     If no match → REJECT with line number
  5. Reject if KEY not in allowlist (§6.4 list) → REJECT
  6. Validate VALUE per key-type:
       boolean keys (TCS_REQUIRE_SCOPE, TCS_ENABLE_*, TCS_ALLOW_AMEND_*) → must match ^[01]$
       integer keys (TCS_MAX_SUBJECT_LENGTH)                            → must match ^[0-9]{1,4}$
       branch-list (TCS_PROTECTED_BRANCHES)                              → ^[A-Za-z0-9._/-]+(\|[A-Za-z0-9._/-]+)*$
       commit-types (TCS_ALLOWED_COMMIT_TYPES)                           → ^[a-z]+( [a-z]+)*$
       path keys (TCS_HOOK_EXCLUDE_PATHS_FILE)                           → ^[A-Za-z0-9._/-]+$, no '..', resolved path must remain inside repo
  7. Reject if VALUE contains any of: backtick, $(, ${, $((, |, ;, &, >, <, newline, NUL, \, ", '
     (Even though we never eval, defense-in-depth against future regression)
  8. Assign via `printf -v "$KEY" '%s' "$VALUE"` — never `eval`, never `declare $line`, never `source`
```

**MUST reject (test corpus):**
- `TCS_PROTECTED_BRANCHES=$(rm -rf ~)` — command substitution
- `TCS_PROTECTED_BRANCHES=`backtick`evil`backtick``
- `TCS_PROTECTED_BRANCHES=main\nmalicious=1` — newline injection
- `EVIL=1` — unknown key
- `TCS_REQUIRE_SCOPE=true` — wrong type (must be 0/1)
- `TCS_HOOK_EXCLUDE_PATHS_FILE=../../etc/passwd` — path traversal

**MUST accept:** all `.config.example` lines uncommented.

**TOCTOU caveat:** parse once at hook entry, snapshot values into local vars; do not re-read `.config` during a single hook invocation.

---

## 5. Hook-Bypass Surface Inventory

| Vector | Detected by | Caught? | v1.0 verdict |
|---|---|---|---|
| `bash -c "git push"` | regex on full command string | ✅ regex matches `git\s+push` substring | OK |
| `eval "git push"` / `$(git push)` / `(git push)` | same | ✅ | OK |
| `git\t push` (tab not space) | regex `\s+` | ✅ if `\s+` used; **broken if regex uses literal space** | Mandate `\s+` |
| `gIt push` / case variants | regex case-sensitive | ❌ git is case-sensitive on Linux/macOS-APFS so this fails to invoke git anyway | Acceptable |
| Shell alias `gp=git push` set in same session | regex on `gp` literal | ❌ undetected by Bash matcher; `.githooks/pre-push` catches it git-side | Acceptable (defense-in-depth §4.3) |
| Function `gp() { git push; }` | same as alias | ❌ Bash matcher; `.githooks/pre-push` catches | Acceptable |
| `~/.gitconfig` aliases (`git pf` → `push --force`) | regex sees `git pf` | ❌ Claude-side miss; `.githooks/pre-push` still fires | Document in `references/destructive-ops.md` |
| `/usr/bin/git push` (absolute path) | regex `git\s+push` matches | ✅ | OK |
| `git -c core.hooksPath=/dev/null push` | regex | ✅ Bash matcher catches `git\s+.*push`; **also** add explicit pattern `git\s+-c\s+core\.hooksPath=` → DENY | **Add this pattern** to §6.2.1 |
| `git config core.hooksPath ...` to disable git-side hooks | sandbox blocks `.git/config` writes | ✅ | Verify sandbox actually blocks during PLAN |
| `rm -rf .git/hooks/` or `chmod -x .githooks/*` | not currently caught | ❌ | **Add Write/Edit PreToolUse pattern** for `.githooks/*` modifications outside `/tcs-git-helpers:setup` context |
| Plugin-disable then act | plugin gone, Claude-side hooks gone | partial — `.githooks/` still fires | Acceptable; surface in brief |
| `git push --no-verify` (server-side bypass of pre-push) | already in §6.2.1 | ✅ | OK |
| Disable plugin via `.claude/settings.local.json` edit | not detected | ❌ | Out-of-scope; user-global `block-main-edits.sh` still protects main |
| Heredoc / multiline command | regex on full string | ✅ | OK |
| Subprocess via Python/Node tool that's not Bash | Bash matcher only | ❌ | v1.0 acceptable — Claude rarely shells via non-Bash tools; `.githooks/` is the catchall |

**Two missing patterns to add to §6.2.1:**
- `git\s+-c\s+core\.hooksPath` — disabling git-side hooks
- `git\s+config\s+(--\S+\s+)?core\.hooksPath` — same via subcommand

**Write/Edit PreToolUse should also block edits to `.githooks/*`, `.git/config`, `.git/hooks/*`** unless the invoking tool is `/tcs-git-helpers:setup` (signaled via env var the skill sets internally).

---

## 6. v1.1 Allowlist (`.git-safe`) — Security Model

When the file-based allowlist (§6.2.1 deferred) lands, treat it like `.config`:
- Strict line-format parser, no eval
- Per-line entry = one literal command pattern OR one regex (clearly distinguished by prefix, e.g. `literal:` vs `regex:`)
- File must be **committed** (`.git-safe`, repo root) — uncommitted file → ignored with warning. Forces allowlist changes through git review.
- Cap entries at e.g. 50; cap regex complexity (no nested quantifiers).
- Audit log per allowlist hit (same `overrides.log`).

**Risk vs env-var:** allowlist entries are *long-lived*; an env var is one-shot. Allowlist is more dangerous because Claude can add an entry, commit it, and forget. Mitigation: linter in `pre-commit` warns when `.git-safe` changes ("review carefully — this expands the bypass surface").

---

## 7. GitHub Branch Protection (G12) — `gh api` Auth Scope

`/tcs-git-helpers:setup --with-branch-protection` calls `gh api -X PUT …/protection`. Required scope: `repo` (full) — `gh` already grants this on `gh auth login`, so no new exposure. **But:**

- Before invoking, run `gh auth status` and surface the active scopes to Marcus. If a token has `admin:org` or `delete_repo` it isn't strictly needed for branch protection — recommend a fine-grained token for the setup call.
- `gh api -X PATCH repos/.../delete_branch_on_merge=true` — same scope.
- Document in `references/sandbox-and-git-config.md` that `gh` token scope creep is the auth risk, not the protection call itself.

---

## 8. Trust Transitivity — `references/*.md` → Executed Commands

Plugin is the trust boundary; `references/` content is trusted because it's in `${CLAUDE_PLUGIN_ROOT}` and ships via marketplace updates. Concern: a future plugin update could change recovery instructions Claude executes. Mitigation:

- All recovery instructions in `references/*.md` must use **non-destructive commands only** — `git cherry-pick`, `git fetch`, `git log`, `git reflog show`. Reviewers in PR review enforce this.
- Add a constitution rule (or `references/INDEX.md` header): *"Recovery snippets in references/ must not use any command listed in §6.2.1 destructive set."*
- Plugin marketplace updates are out-of-band trust (Marcus reviews updates) — same as code review.

---

## 9. Open Security Questions for Marcus

1. **Drop `CLAUDE_ALLOW_GIT_BAD_OPS` master override entirely?** (recommend yes, or gate with date-stamp)
2. **One-shot semantics for all overrides** — generalize from worktree-exit only? (recommend yes)
3. **Audit log location** — `${CLAUDE_PLUGIN_DATA}/overrides.log` acceptable, or prefer per-repo `.git/info/tcs-overrides.log`?
4. **`.git-safe` allowlist (v1.1)** — committed-only, or also accept `.git/info/git-safe` (uncommitted)? Committed is safer; uncommitted is more flexible.
5. **Block edits to `.githooks/*` and `.git/hooks/*` by default?** Skill sets bypass env var during setup. (recommend yes)
6. **`gh auth status` scope warning** before `--with-branch-protection`? Adds friction but flags broader-than-needed tokens.
7. **Constitution rule for `references/` content** — forbid destructive commands in any recovery snippet?
