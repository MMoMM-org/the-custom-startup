# Tools — the-custom-startup
<!-- CI, build pipeline, API clients, local dev setup. Updated: 2026-09-01 -->
<!-- What goes here: commands that are non-obvious, tool quirks, CI gotchas, env var names -->
<!-- What does NOT go here: domain rules (→ domain.md), code style (→ general.md) -->
<!-- Form: one rule + its tell + one pointer, ≤ 250 chars. See memory-add/reference/category-formats.md -->

<!-- 2026-05-09 -->
- **bash 3.2 breaks two regex forms in `[[ =~ ]]`** — PCRE `\s`/`\b` never match; bounded `^.{m,n}$` returns false on matching input. Hooks that match commands then silently never fire. → Use `[[:space:]]`, `[[:<:]]`, `${#var}` checks.
- **`gh pr view --json mergeMethod` does not exist** (gh 2.88.1) — returns `Unknown JSON field`. → Detect a squash after the fact with `git cherry origin/<default> <branch>`; all `-` lines mean the patches are already applied.
- **Only `PreToolUse:ExitWorktree` is blockable among the worktree and session events** — it accepts `permissionDecision: deny`, while `WorktreeRemove` and `SessionEnd` are documented as non-blockable. → Register worktree data-loss guards there.

<!-- 2026-05-09 -->
- **bats `! cmd` only fails a test as the body's last command** — non-final negations silently pass. Ordinary assertions still fail correctly; the trap is negation-only. → Use a helper returning 1 so `set -e` fires. [spec-011 T1.5]
- **`$'\0'` expands to the empty string in bash**, so `case $x in *$'\0'*)` matches everything. Bash strings cannot hold NUL anyway. → Reject bad input with `read -r` plus a per-key allowlist, never a NUL case-glob.
- **jq under `set -e` makes a hook fail closed** — a non-zero exit on malformed JSON reads to Claude Code as "deny tool call". → Append `2>/dev/null || true` to every jq command substitution in a hook meant to fail open. [spec-011 T2.4]
- **`mktemp -d` without a template fails under the harness sandbox** ("Operation not permitted") despite a writable `/var/folders/`. → Always pass one: `mktemp -d "${TMPDIR:-/tmp}/name-XXXXXX"`. Never `$TMPDIR/$RANDOM`.
- **A failed `git init` in a bats fixture leaks commits onto the parent branch** — git falls back to the parent `.git/`. Tell: stray fixture commits on your branch. → Use `git -C "$tmpdir"` plus `GIT_CONFIG_GLOBAL=/dev/null`. [spec-011 T2.1]

<!-- 2026-05-09 -->
- **Clear dedup and cache artifacts at the top of every perf-test iteration**, or vary the key — otherwise iterations 2..N measure the early-exit path instead of the trigger path, and a regression passes. [spec-011 T3.3]

<!-- 2026-05-13 -->
- **`CLAUDE_PLUGIN_ROOT`/`CLAUDE_PLUGIN_DATA` reach only harness-spawned plugin code** — not git-spawned hooks (`core.hooksPath`), not Bash-tool subprocesses. `CLAUDECODE=1` does propagate. → Git-hook code must self-derive its paths. [spec-012]

<!-- 2026-05-23 -->
- **A CLI stub must apply `--jq` itself** — real `gh` filters server-side and returns the bare value, so a stub that `cat`s its envelope silently diverges from production. → Scan args for `--jq` and pipe the response through it. [spec-014 T1.3]
- **bats `run` uses a subshell, so the function's variable mutations are lost** — unavoidable with `--separate-stderr`. → Split by concern: call directly to assert side-effect vars, use `run` to assert stderr. [lib_override.bats:201]

<!-- 2026-06-22 -->
- **The Bash tool reaps the process group at the tool-call boundary** — `nohup`/`disown` block SIGHUP, not harness teardown, so a backgrounded server dies silently. → Run it in the foreground inside a `run_in_background: true` call.

<!-- 2026-07-02 -->
- **`rule-enforcer --scan` follows `@`-imports but not prose "see X" pointers** — rules one hop past the import frontier, or in `~/.claude/`, fall outside default scope. → Convert the pointer to an `@`-import, or run `--scope global`. [spec-016]
