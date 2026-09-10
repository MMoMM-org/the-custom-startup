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
- **CI runs Python 3.11, this machine runs 3.14** — `.github/workflows/tests.yml:61,101` pins `3.11` and runs the whole `pytest -q` on ubuntu AND macos. Anything newer than 3.11 passes locally and breaks CI. → Check the version a stdlib attribute was added in, never just `hasattr` locally.
- **`tomllib.TOMLDecodeError` has `lineno`/`colno`/`msg` only on 3.14+** (gh-126175) — 3.11.14 exposes none; the position survives only inside `str(e)`. Worse, `getattr`-with-fallback *diverges*: for an end-of-document error 3.14's attribute gives a line and the message gives none. → Parse `str(e)` only (`r"at line (\d+)"`); its wording is byte-identical 3.11→3.14. Treat `None` as a real outcome, not a 3.11 artifact.
- **`uv` needs both cache and python dirs redirected under the Bash sandbox** — `~/.cache/uv` and `~/.local/share/uv/python` are both denied. → `UV_CACHE_DIR="$TMPDIR/uvcache" UV_PYTHON_INSTALL_DIR="$TMPDIR/uvpython" uv run --python 3.11 --no-project script.py` works and needs no sandbox override.
