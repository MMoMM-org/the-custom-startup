# Follow-ups

> Tracked work items not yet scoped into a full XDD spec. When promoting an
> entry into a spec, link the new `docs/XDD/specs/NNN-…/` from the entry's
> "Spec" line.

## Open

### F-001 — Harness-hook pattern matches inside quoted args (false-positive class)

**Status**: open · **Surfaced**: PR #21 · **Spec**: none yet

`plugins/tcs-git-helpers/scripts/block-bad-git-ops.sh` runs each destructive-op
pattern against the raw `tool_input.command` string. When the command's
positional payload contains text that happens to match a pattern, the hook
denies a command that is behaviourally safe.

**Concrete encounters (PR #21):**
- A `git commit -m "..."` whose body **describes** a `core.hooksPath` config
  write — `HOOKSPATH_OVERRIDE` fires on the `git commit`, not on the body text.
- A `gh pr create --body "..."` whose body **describes** a destructive op
  (reset / force-push / force-delete / etc.) — the corresponding rule fires
  even though the `gh` command itself does nothing destructive.

**Why it's not a one-line fix:**

The matcher uses POSIX ERE substring matching on the raw command line
(CON-9). To exclude quoted-string regions you need shell-aware tokenisation.
Two viable approaches:

1. **Pre-strip quoted segments** before matching. A `_strip_quoted_segments`
   helper that removes balanced `'...'` and `"..."` spans, then runs patterns
   against the residual. Watch out for nested quotes, escape sequences, and
   heredocs.
2. **Token-level matching.** Tokenise the command via a bash-aware parser,
   then only match patterns against `argv[0..]` of recognised command
   invocations.

(1) is simpler but has edge cases (heredocs, escaped quotes). (2) is more
correct but a larger refactor.

**Workarounds in use today:**

- Rewrite the inner text to avoid the literal pattern (current workaround —
  used to commit / open PR #21 and to write this very entry).
- The granular override env var (`CLAUDE_ALLOW_<RULE>=1`) does **not**
  propagate from Claude's Bash shell into the PreToolUse hook process — that
  belongs in a separate follow-up (see F-003 candidate below).

**Test plan when fixed:**

- `git commit -m "<contains a destructive-rule literal>"` → ALLOW.
- `gh pr create --body "<contains rule literals>"` → ALLOW.
- All existing deny tests still pass (the surrounding pattern still matches
  genuine destructive commands).
- Edge cases: nested quotes, escaped quotes, heredocs, command substitution.

**Files in scope:**

- `plugins/tcs-git-helpers/scripts/block-bad-git-ops.sh`
- `plugins/tcs-git-helpers/scripts/lib/pattern_match.sh` (where `_match_command` lives)
- `plugins/tcs-git-helpers/tests/bats/block-bad-git-ops.bats`

---

### F-002 — Harmonise cache-path resolution (lib-bundle.sh vs scripts/lib/cache.sh)

**Status**: open · **Surfaced**: spec-012 SDD §Risks and Technical Debt · **Spec**: none yet (carved out of spec-012 scope)

Two cache-path resolvers exist with different defaults:

| Resolver | Lives in | Default path | Used by |
|---|---|---|---|
| `_resolve_data_dir()` | `templates/githooks/lib-bundle.sh` (installed in repo `.githooks/`) | `${HOME}/.claude/plugins/data/tcs-git-helpers-<repo>/cache/` | git-spawned hooks (post-merge, pre-push) |
| `_cache_dir()` | `scripts/lib/cache.sh` (plugin source) | `${CLAUDE_PLUGIN_DATA:-${HOME}/.claude/plugin-data}/cache/` | `git_status_audit.py`, `session-start-brief.sh`, all skill paths |

When `CLAUDE_PLUGIN_DATA` is set by the harness (skill invocations), both
*might* converge if the harness's value matches the bundle's derived path —
but that is not guaranteed and not documented. When unset (scripts run
directly), the audit script falls back to `~/.claude/plugin-data/`, not the
bundle's `~/.claude/plugins/data/tcs-git-helpers-<repo>/`.

**Quote from spec-012 SDD:**

> The existing `scripts/lib/cache.sh` has a fallback for missing
> `CLAUDE_PLUGIN_DATA` that points at a DIFFERENT directory than where
> harness-spawned code actually writes. This is debt from spec/011; it's
> working accidentally (no hook successfully writes via that path because
> the hook never sources the lib). After this fix lands, the existing
> `cache.sh` fallback path can be removed — `_resolve_data_dir` in
> `lib-bundle.sh` becomes the single resolver.

**Today's symptom:**

`cmd_cleanup` works because it overwrites the cache with its own refresh
before reading (Bug 1 fix from spec-012). But `cmd_brief` and any future
read-only consumer that reads cache *without* refreshing would see stale or
empty data if the post-merge hook wrote to a different directory than the
reader checks.

**Proposed scope (one PR or a mini-spec):**

1. Single source of truth for cache-dir resolution: either elevate
   `_resolve_data_dir`'s logic into `cache.sh` as the shared library, or
   have `cache.sh._cache_dir` shell out to `_resolve_data_dir`.
2. Drop the `cache.sh` fallback to `~/.claude/plugin-data/`.
3. Add bats / pytest coverage proving the hook and the audit script write to
   and read from the same path under both `CLAUDE_PLUGIN_DATA`-set and
   -unset conditions.
4. Migration note for users whose old cache is at
   `~/.claude/plugin-data/cache/<hash>-stale-cache.{tsv,json}`: rerun
   `/tcs-git-helpers:git-setup`; the next merge regenerates.

**Files in scope:**

- `plugins/tcs-git-helpers/scripts/lib/cache.sh`
- `plugins/tcs-git-helpers/templates/githooks/lib-bundle.sh`
- `plugins/tcs-git-helpers/scripts/git_status_audit.py` (uses `_cache_dir`)
- `plugins/tcs-git-helpers/scripts/session-start-brief.sh` (uses `_cache_dir`)
- bats + pytest coverage

---

## Resolved

_(none yet — move entries here with the resolving PR number when closed)_
