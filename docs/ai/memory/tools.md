# Tools — the-custom-startup
<!-- CI, build pipeline, API clients, local dev setup. Updated: 2026-09-01 -->
<!-- What goes here: commands that are non-obvious, tool quirks, CI gotchas, env var names -->
<!-- What does NOT go here: domain rules (→ domain.md), code style (→ general.md) -->
<!-- Form: one rule + its tell, ≤ 250 chars, no spec refs. See memory-add/reference/category-formats.md -->

<!-- 2026-05-09 -->
- **`gh pr view --json mergeMethod` does not exist** (gh 2.88.1) — returns `Unknown JSON field`. → Detect a squash after the fact with `git cherry origin/<default> <branch>`; all `-` lines mean the patches are already applied.
- **Only `PreToolUse:ExitWorktree` is blockable among the worktree and session events** — it accepts `permissionDecision: deny`, while `WorktreeRemove` and `SessionEnd` are documented as non-blockable. → Register worktree data-loss guards there.

<!-- 2026-05-09 -->
- **`$'\0'` expands to the empty string in bash**, so `case $x in *$'\0'*)` matches everything. Bash strings cannot hold NUL anyway. → Reject bad input with `read -r` plus a per-key allowlist, never a NUL case-glob.
- **`mktemp -d` without a template fails under the harness sandbox** ("Operation not permitted") despite a writable `/var/folders/`. → Always pass one: `mktemp -d "${TMPDIR:-/tmp}/name-XXXXXX"`. Never `$TMPDIR/$RANDOM`.

<!-- 2026-05-09 -->
- **Clear dedup and cache artifacts at the top of every perf-test iteration**, or vary the key — otherwise iterations 2..N measure the early-exit path instead of the trigger path, and a regression passes.

<!-- 2026-05-23 -->
- **A CLI stub must apply `--jq` itself** — real `gh` filters server-side and returns the bare value, so a stub that `cat`s its envelope silently diverges from production. → Scan args for `--jq` and pipe the response through it.
- **bats `run` uses a subshell, so the function's variable mutations are lost** — unavoidable with `--separate-stderr`. → Split by concern: call directly to assert side-effect vars, use `run` to assert stderr. [lib_override.bats:201]

<!-- 2026-07-02 -->
- **`rule-enforcer --scan` follows `@`-imports but not prose "see X" pointers** — rules one hop past the import frontier, or in `~/.claude/`, fall outside default scope. → Convert the pointer to an `@`-import, or run `--scope global`.

<!-- 2026-09-04 -->
- **`gh pr merge --auto` merges at once when the branch has no required status checks** — auto-merge needs protection rules to have something to wait for. → Block on `gh pr checks` yourself when a check must gate the merge.

<!-- 2026-09-10 -->
- **CI runs Python 3.11, this machine runs 3.14** — `.github/workflows/tests.yml` pins 3.11 for the whole suite on ubuntu and macOS, so newer stdlib passes locally and breaks CI. → Check when an attribute was added, never just `hasattr` locally.
- **`tomllib.TOMLDecodeError` has `lineno`/`colno`/`msg` only on 3.14+** — on 3.11 the position is only in `str(e)`, and a `getattr` fallback diverges at end of document. → Parse `str(e)` (`r"at line (\d+)"`); treat `None` as a real outcome.
- **`uv` under the Bash sandbox needs its cache and python dirs redirected** — `~/.cache/uv` and `~/.local/share/uv/python` are denied. → `UV_CACHE_DIR="$TMPDIR/uvcache" UV_PYTHON_INSTALL_DIR="$TMPDIR/uvpython" uv run --python 3.11 …`.

<!-- 2026-10-08 -->
- **`docs-sync` wants a root `CHANGELOG.md` entry for any change under `plugins/` or `scripts/`** — the plugin's own CHANGELOG does not count; CI reports `CHANGELOG.md` unaccounted. → Write both, or waive it in the PR body.

<!-- 2026-09-01 -->
- **The Bash tool reaps the process group at the tool-call boundary** — `nohup`/`disown` block SIGHUP, not harness teardown, so a backgrounded server dies silently. → Run it in the foreground inside a `run_in_background: true` call.

<!-- 2026-09-04 -->
- **`stat -f` is a format string on BSD and means *filesystem* on GNU** — on Linux `stat -f %m` prints a filesystem report and fails, so a `||` fallback appends to it. → `m="$(stat -c %Y "$f" 2>/dev/null)" || m="$(stat -f %m "$f")"`.

<!-- 2026-09-04 -->
- **Perf test p95 exceeds 100ms cap (2x the 50ms target) under load** — 124.8/156.4ms parallel-agent, 193.5ms alone; max 269ms = macOS's 151-286ms first-exec cost, warmup can't absorb. → `perf`-marked, deselected by default; run `pytest -m perf`.

<!-- 2026-09-08 -->
- **A `<<'PY'` heredoc inside `$(...)` breaks on bash 3.2 if its body holds `\'`** — "unexpected EOF while looking for matching `''`"; a quoted `"$(...)"` breaks on any apostrophe. → Assign via unquoted `VAR=$(...)`; no `\'` in the body.

<!-- 2026-10-02 -->
- **`skillOverrides` cannot reach a plugin skill** — `off`/`name-only` are silently ignored for plugin sources; only `enabledPlugins` (whole plugin) works. A repo skill honours it. → Per-skill control means installing into the repo.

<!-- 2026-10-10 -->
- **`$TMPDIR` differs between sandboxed and unsandboxed Bash calls** — a file one call writes is absent for the other, and a count over it reads empty, not zero. → Pass the scratchpad's absolute path between calls, never `$TMPDIR`.
- **A baseline worktree for before/after test runs must be on a branch** — the guard hooks bypass on a detached HEAD, so `git worktree add --detach` yields dozens of false deny failures. → Run `git switch -c tmp/<name>` inside it first.
- **A squash-merged PR's branch commits are reachable from no ref once the branch is deleted** — no clone fetches them, `fetch-depth: 0` included, so a test reading one skips everywhere. → Inline the data the test needs.
