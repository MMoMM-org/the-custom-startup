# Sandbox and git config

> Why `git -c core.hooksPath=…` is denied, why `.git/config` writes happen
> only at setup time, and how `git_safe()` filters known-harmless sandbox
> warnings,
> and how to make everyday git work under the Bash sandbox.

## What goes wrong

Two interactions between Claude Code's sandbox and git's config system
cause friction without the plugin in the loop, and create bypass surface
with it:

**1. Sandbox blocks `.git/config` writes.** Claude Code's filesystem
sandbox restricts writes outside the working directory and a few
explicit allow paths. `.git/config` lives inside the repo dir but is
treated as a high-trust file (it controls remotes, hooks, signing
keys, fetch refspecs). Hooks and skills that try to set a config value
mid-session fail with:

```
warning: could not write config file .git/config
```

The git operation may still partially succeed (some commands cope with
read-only config), but the intended effect is gone. This is *not* a
bug in git; it is the sandbox doing its job.

**2. `git -c core.hooksPath=…` is the canonical hook bypass.** A single
invocation of `git -c core.hooksPath=/dev/null commit` runs git with
the hooks path pointed at an empty directory; `pre-commit` and
`commit-msg` never fire. Equivalently: `git config core.hooksPath
/tmp/empty` (writing to the config directly), or `git config --global
core.hooksPath /tmp/empty` (subverting at the user-global level). All
three are denied by `block-bad-git-ops.sh` (M7).

The plugin's defense in depth requires both layers (Claude-side hooks
and `.githooks/`) to remain effective. Subverting `core.hooksPath`
disables the second layer for any git invocation in the current
session. The denial is non-negotiable.

There is also a third, milder failure mode: hook scripts that emit the
`could not write config file .git/config` warning to stderr without
needing the write — for example, a read-only `git config --get` should
not print this warning, but some git versions emit it transiently when
the global config is locked. The `git_safe()` filter in
`lib/git_state.sh` strips these specific known-harmless lines so they
do not pollute denial messages.

## How to detect

**Sandbox refusal during a git operation:**

```
warning: could not write config file .git/config
```

This message appears on stderr from git itself (not from the plugin).
It indicates a write that the sandbox refused. The exit code may still
be 0 — git treats config-write failures as warnings, not errors.

**Bypass attempt denied by the plugin:**

```bash
git -c core.hooksPath=/dev/null commit -m "skip hooks"
# → permissionDecision: deny
# → reason: hooksPath override; see references/sandbox-and-git-config.md
```

The pattern matches:

- `git -c core.hooksPath=…` in any position, behind other global options too
- `git config core.hooksPath …` (write form), including `--unset`
- `git config --global core.hooksPath …`, `--local`, `--file <f>`, or any
  run of options before the key
- `git config set core.hooksPath …` / `git config unset core.hooksPath`
  (git 2.46+ subcommand syntax)
- the key in any letter case: `core.hookspath`, `CORE.HOOKSPATH` (git
  config keys are case-insensitive)

Read forms are allowed without the setup sentinel: `--get`, `--get-all`,
`--get-regexp` and `git config get`. The exemption covers only the clause
that reads: `git config --get core.hooksPath && git config core.hooksPath …`
is still refused for its second half. A key that only starts the same way
(`core.hooksPathology`) is not matched.

The corpus is in
`plugins/tcs-git-helpers/tests/fixtures/commands/destructive_corpus.txt`
under `HOOKSPATH_OVERRIDE`.

**Verify current `core.hooksPath`:**

```bash
git config --get core.hooksPath
```

A clean repo with the plugin's `.githooks/` installed prints `.githooks`.
Empty output means hooks live in `.git/hooks/` (the default). Anything
else (`.husky`, `/tmp/empty`, etc.) is a tooling collision — see
[`migrating-from-husky.md`](migrating-from-husky.md).

## Fix

**To set `core.hooksPath` legitimately:** run the setup skill. It is the
only path that writes `.git/config` — under explicit Claude Code
permission prompt, with the `TCS_GIT_HELPERS_SETUP_ACTIVE=1` sentinel
(ADR-11) bounding the write to the setup subshell:

```
/tcs-git-helpers:git-setup
```

The skill executes the equivalent of:

```bash
( export TCS_GIT_HELPERS_SETUP_ACTIVE=1
  git config core.hooksPath .githooks
)
```

Marcus approves the permission prompt once. Subsequent operations
(hooks firing, status calls) only *read* config and never trip the
sandbox.

**If you got a stale `core.hooksPath` warning during setup:** it usually
means a previous hook tool (Husky, lefthook) left the config pointing
elsewhere. Clear it:

```bash
git config --unset core.hooksPath
```

…then re-run `/tcs-git-helpers:git-setup`. See
[`migrating-from-husky.md`](migrating-from-husky.md) for the full
removal of competing tooling.

**If a hook needs to read a config value:** always use `git config --get`
(read-only). The `lib/git_state.sh` helpers wrap most calls with the
`git_safe()` filter, which:

- Runs the underlying git command.
- Captures stderr.
- Strips the known-harmless `could not write config file .git/config`
  line (and a small allowlist of similar transient warnings).
- Forwards anything else unchanged so real errors still surface.

You should not need to call `git_safe()` directly from a new hook —
the existing helpers (`gs_current_branch`, `gs_default_branch`,
`gs_is_clean`, `gs_pr_state`) already use it.

**If a denied operation truly needs the bypass** (e.g., debugging the
plugin itself): use the granular override, not the master kill, and
not `git -c core.hooksPath=…`:

```bash
CLAUDE_ALLOW_HOOKSPATH_OVERRIDE=1 git -c core.hooksPath=/dev/null commit -m "debug"
```

The override consumes single-shot (5s sentinel, ADR-5) and emits a
JSONL audit line. Subsequent invocations re-deny.

## Prevention

- **Never call `git config <key> <value>` (write form) from inside a
  hook script.** Hooks fire frequently; even a single write per hook
  invocation will hit the sandbox. Restrict writes to the setup skill,
  which runs once per repo and prompts for permission.
- **Do not point `core.hooksPath` anywhere except `.githooks` (or
  unset).** The `.githooks/` directory is the plugin's git-side layer;
  competing values defeat defense in depth.
- **Do not add `git -c core.hooksPath=…` to aliases or wrapper
  scripts.** The Claude-side regex catches the literal command, but a
  wrapper that constructs the argument at runtime can slip past — the
  `.githooks/` layer is gone in that case anyway, since the wrapper is
  the bypass.
- **Use read-only config calls everywhere.** `git config --get`,
  `git config --get-all`, `git config --get-regexp` are all
  sandbox-safe. They do not fail with the warning.
- **Wrap new git invocations in `git_safe()`** (or one of the
  `gs_*` helpers in `lib/git_state.sh`) so the known-harmless warning
  does not leak into denial reasons or skill output.

## Sandbox-compatible git

The sandbox protects `.git/config` and `.git/hooks/` from writes, and
`sandbox.filesystem.allowWrite` cannot lift that; only turning filesystem
isolation off does. So inside the sandbox some git commands finish only
partly, with no hard error:

| Command | What is left undone |
|---|---|
| `git push -u` | pushes, sets no upstream |
| `git checkout -b <b> origin/<x>`, `--track`, `switch -c` with a remote start | writes the branch and the tree, fails on the tracking config, HEAD stays on the old branch |
| `git branch --set-upstream-to`, `git remote add\|set-url`, `git config <key> <value>` | fail |
| `fetch`/`pull`/`push` over SSH (macOS) | fail even with the host allowed |
| `gh` (macOS) | TLS errors |

### The settings template

`/tcs-git-helpers:git-setup` offers
`templates/claude-settings/sandbox-git.json` and merges it into the repo's
`.claude/settings.json` only after you confirm its diff:

```json
{
  "sandbox": {
    "excludedCommands": [
      "git push *", "git fetch *", "git pull *",
      "git checkout -b *", "git switch -c *",
      "git branch *", "git remote *", "gh *"
    ],
    "filesystem": { "denyWrite": ["./.githooks"] }
  },
  "permissions": {
    "ask": [
      "Bash(git remote add *)", "Bash(git remote set-url *)",
      "Bash(git remote remove *)", "Bash(git remote rename *)"
    ]
  }
}
```

The merge only adds entries; a re-run changes nothing. To apply it without
the skill, run `skills/git-setup/lib/sandbox_settings.sh --diff`, then
`--apply` outside the sandbox: `.claude/settings.json` is itself protected.

- **`.githooks` in `denyWrite` is required, not optional.** An excluded
  `git push` runs `.githooks/pre-push` outside the sandbox, and `.githooks/`
  is not a protected path. Without the entry, a sandboxed
  `echo … > .githooks/pre-push` followed by `git push` is a sandbox escape.
  `protect-git-internals.sh` covers Edit and Write, not Bash. The cost:
  `git-setup` writes `.githooks/` from outside the sandbox (a prompt, rare).
- **`git config *` stays sandboxed on purpose.** A config write goes through
  the unsandboxed-retry prompt, where you see it; `block-bad-git-ops.sh`
  guards `core.hooksPath` either way.
- **Changing a remote asks.** `git remote *` runs outside the sandbox, so
  the four commands that change a remote need a yes; `git remote -v` does not.

### What the template cannot do

- **Run each excluded git command alone in its Bash call.** Every part of a
  chained call must match an exclusion, or the whole call stays sandboxed.
  `git push -u origin feat; echo "rc=$?"` pushes, fails locally with
  `could not lock config file .git/config`, sets no upstream, and still
  exits 0. The same holds for `cd x && git push`, `git -C <path> push`, a
  subshell, a pipe into another command, a redirect, and a `VAR=1` prefix,
  override tokens included (verified on macOS: `FOO=1 git push -u` stayed
  sandboxed). Check the result (`git rev-parse --abbrev-ref @{u}`) in a
  separate call. `block-bad-git-ops.sh` enforces this; see below.
- A failed `push -u` can still look right: when the branch already tracked
  something (`checkout -b x origin/main` sets `origin/main`), `@{u}` keeps
  printing that, not the branch you pushed.
- An excluded command runs with full filesystem and network access:
  `git push *` can reach any host.
- A plain `git checkout -b <b>` without tracking writes no config and
  works sandboxed anyway; the exclusion matters only when it sets tracking.
- GPG signing (`~/.gnupg`, the gpg-agent socket) and credential helpers
  (osxkeychain) under the sandbox are not documented upstream; check them on
  macOS before relying on them.

### SANDBOX_CHAINED_GIT

`block-bad-git-ops.sh` denies a Bash call that holds a git command writing
`.git/config` when the call is not that command alone. The commands:

| Command | Needs the exclusion |
|---|---|
| `git push -u` / `--set-upstream`, also inside a short-option bundle | `git push *` |
| `git checkout -b` / `switch -c` that sets tracking: `--track`, or a remote-tracking start point unless `branch.autoSetupMerge=false`; never with `--no-track` | `git checkout -b *` / `git switch -c *` |
| `git branch --set-upstream-to`, `-u`, `--unset-upstream`, `--track`, `-t` | `git branch *` |
| `git remote add`, `set-url`, `remove`, `rm`, `rename` | `git remote *` |

"Alone" means: with quoted text blanked, the call has no `;`, `&`, `|`,
`<`, `>`, backtick, `$(` or newline, its first word is `git`, and the
subcommand follows right after (`git -C <dir>` does not match `git push *`).

The rule fires only when user, project or local settings list the
command's exclusion and the most specific `sandbox.enabled` is not `false`.
Without the exclusion, running the command alone would not help. Settings
that cannot be read allow the call, like every lookup in this hook.

Fix: run the command alone, then check its result in the next call. When
the session is not sandboxed after all, override with
`CLAUDE_ALLOW_SANDBOX_CHAINED_GIT=1` as the first token: single use,
audited.

### Repairing a half-done command

`scripts/git-sandbox-repair.sh` fixes what a sandboxed command left behind.
Run it from the prompt, so it runs outside the sandbox:

```
! bash ~/.claude/plugins/cache/the-custom-startup/tcs-git-helpers/*/scripts/git-sandbox-repair.sh
```

| Finding | Action |
|---|---|
| current branch has no upstream, `origin/<branch>` exists | sets the upstream (`FIXED`) |
| branch not pushed yet, or already tracking | reports it (`INFO`, `OK`) |
| the index matches another branch's tree, not HEAD's | reports it with the command that would fix it (`REPORT`, exit 2) |

`--dry-run` prints `WOULD-FIX` instead of writing. The script never resets,
checks out or moves a ref: an index that matches another branch can also be
staged work, so that case stays yours to decide.

## Why

Two design decisions converge here:

**CON-7 — `.git/config` writes only at setup, under permission prompt.**
The brainstorm and the security research (§5 Hook-Bypass Surface
Inventory) treat `.git/config` as a high-trust file. Per-operation
writes from automated tools (a hook setting `user.name`, a skill
toggling `core.editor`, etc.) expand the attack surface: every write
is a chance for the wrong value to land, and there is no audit trail
inside git for config changes.

The trade-off: setup writes are batched, infrequent, and gated on a
human approving the macOS / Claude Code sandbox prompt. Runtime
operations are read-only. The user-facing cost is a single prompt the
first time the plugin runs in a new repo. The benefit is that the
plugin cannot rewrite `.git/config` later without prompting again.

**ADR-11 — `TCS_GIT_HELPERS_SETUP_ACTIVE=1` env-var sentinel.** The
PreToolUse hooks for `Edit` / `Write` / `NotebookEdit` deny edits to
`.githooks/*`, `.git/config`, and `.git/hooks/*` *unless* the sentinel
is set. The setup skill exports the sentinel inside a `(subshell)`
block to bound its lifetime — when the subshell exits, the var is
gone, and subsequent operations cannot edit those paths.

The same sentinel gates `block-bad-git-ops.sh` for the
`HOOKSPATH_OVERRIDE` rule: `git config core.hooksPath …` is denied in
normal sessions but allowed inside the setup subshell.

**Boucle parity, with extension.** Boucle's `git-safe` enumerated the
hook-bypass patterns (`--no-verify`, `reset --hard`, etc.) but did
*not* explicitly cover `git -c core.hooksPath=…`. The plugin adds it
because the Claude-Code sandbox does not block `core.hooksPath`
*reads*, and a single `-c` flag is enough to neutralize `.githooks/`.
This is documented in research/security.md §5 ("Two missing patterns
to add"); the corpus and `block-bad-git-ops.sh` cover it.

The `git_safe()` filter is a smaller decision: macOS sandbox + Claude
Code permissions occasionally emit warnings that are *not* the user's
fault and have no actionable component. Strip those at the wrapper
layer rather than asking every consumer to grep them out.

---

## See also

- [`destructive-ops.md`](destructive-ops.md) — the full deny set; this
  doc covers only the `core.hooksPath` extension.
- [`migrating-from-husky.md`](migrating-from-husky.md) — competing
  `core.hooksPath` values from other hook managers.
- [`best-practices.md`](best-practices.md) — §2 defense in depth.
- ADR-11 in `docs/XDD/specs/011-tcs-git-helpers/solution.md` — the
  sentinel design.
