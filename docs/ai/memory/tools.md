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
- **Perf tests exceed their 100 ms p95 cap under parallel load** — macOS's 150-290 ms first-exec cost outlasts warmup, so a busy machine reads as a regression. → `perf`-marked, deselected by default; run `pytest -m perf` on an idle machine.

<!-- 2026-09-08 -->
- **A `<<'PY'` heredoc inside `$(...)` breaks on bash 3.2 if its body holds `\'`** — "unexpected EOF while looking for matching `''`"; a quoted `"$(...)"` breaks on any apostrophe. → Assign via unquoted `VAR=$(...)`; no `\'` in the body.

<!-- 2026-10-02 -->
- **`skillOverrides` cannot reach a plugin skill** — `off`/`name-only` are silently ignored for plugin sources; only `enabledPlugins` (whole plugin) works. A repo skill honours it. → Per-skill control means installing into the repo.

<!-- 2026-10-10 -->
- **`$TMPDIR` differs between sandboxed and unsandboxed Bash calls** — a file one call writes is absent for the other, and a count over it reads empty, not zero. → Pass the scratchpad's absolute path between calls, never `$TMPDIR`.
- **A baseline worktree for before/after test runs must be on a branch** — the guard hooks bypass on a detached HEAD, so `git worktree add --detach` yields dozens of false deny failures. → Run `git switch -c tmp/<name>` inside it first.
- **A squash-merged PR's branch commits are reachable from no ref once the branch is deleted** — no clone fetches them, `fetch-depth: 0` included, so a test reading one skips everywhere. → Inline the data the test needs.

<!-- 2026-10-23 -->
- **The Edit tool drops a whitespace-only `new_string`** — it reports success and inserts nothing, so a six-space anchor became `^`, matching every line. → Use `perl -pi` or `sed` for literal-space replacements; check with `cat -vet`.
- **A local test run is one CI leg, never both** — a red `bats (ubuntu-latest)` can sit behind a green macOS run for several commits. → Read each matrix leg's result before saying CI is green.
- **`cmd | tail` reports tail's exit status** — a failing bats run reads as exit 0, and the last `ok N` is a test number, not a count. → `set -o pipefail` or `${PIPESTATUS[0]}`; count against the TAP plan.
- **bash 3.2 `${s:n}`, `${s:k:n}`, `+=` and `${s//}` are O(n) per call** — and in a UTF-8 locale offsets count characters, so a per-byte loop is O(n²). → `local LC_ALL=C`, and slice a bounded buffer, not the whole string.
- **bats does not run test bodies under `set -u`** — a lib reading an optional argument as bare `"$1"` passes every test and aborts for a real `set -u` caller. → Write `${1:-}`; run one real invocation per entry point.
- **`run diff <(a) <(b)` fails inside bats** with `Operation not permitted` on `/dev/fd/N`. → Write both sides to files in the test's tmpdir and diff those.
- **A test that fails only inside the Bash sandbox is not a code failure** — `mktemp -d` and other writes outside the allowed dirs fail there. → Re-run unsandboxed before treating a red test as real.
- **The Bash sandbox denies writes to `.git/config`, so some git commands half-complete** — `checkout -b` rewrites the tree but leaves HEAD behind; `push -u` pushes but sets no upstream. → Run branch-creating git unsandboxed.
- **`cp -n` skipping a file exits 1 on BSD and 0 on GNU** — a `cp -p` → `cp -n -p` mutant is a silent no-op only on Linux, so on macOS it fails both tests and proves nothing. → Mutate to an early `return 0`.
- **A plugin can ship themes** — every `themes/<slug>.json` in an enabled plugin is auto-discovered into `/theme` (Claude Code ≥ 2.1.118), with no `plugin.json` entry. → User-global themes go in `~/.claude/themes/`.
- **`claude -p --output-format json` wraps the model's output** — the payload is a JSON string under `.result`. → `jq -c 'try (.result | fromjson) catch empty'`; a test stub must emit the same envelope.
- **`claude plugin eval` reads `evals/**/case.yaml`** (or `prompt.md` + `graders/`), not `evals.json`; `eval init` needs a TTY; the report publishes to claude.ai by default. → `init --bare`, always `--no-publish`.
- **A plugin eval run starts in an empty dir, with Write/Edit removed** — case `allowed_tools` cannot grant them, and `add_dirs` fixtures went unseen. → Inline inputs in the prompt; pass `--allow-tools Write Edit`.
- **A typed `/plugin:skill` in an eval prompt records no `Skill` tool call** — `tool_used: Skill` then reads 0 though the skill ran. → Use that grader only for unprompted-trigger cases.
- **The eval `llm` judge misgrades on the full trace** — it failed a correct run 3 of 3. → `focus: last_message`, and grade writes with `regex` on `target: trace`.
- **`GIT_CONFIG_GLOBAL=/dev/null` does not isolate ignore rules** — `~/.config/git/ignore` still applies to `check-ignore`. → Add `-c core.excludesFile=/dev/null` in fixtures that assert ignore status.
- **A pre-push hook gets remote sha `000…0` for a new branch** — `git rev-list $local --not $remote` fails, and `|| true` turns that into "nothing to check". → Use the empty tree, `4b825dc642cb6eb9a060e54bf8d69288fbee4904`.
- **Editing a hook's `command` in `.claude/settings.json` can take effect in the running session.** → Make the change and watch for the hook to fire before telling anyone to restart.
- **Each shell exec in the hook path costs ~2.4 ms on macOS, ~0.2 ms on Linux**, `#!/usr/bin/env bash` adds another exec, and a new file's first exec costs 150-290 ms once. → Warm fresh fixtures with a throwaway exec before timing.
- **`--plugin-dir` loads a plugin whose skills never reach the model's skill listing** — a prompt-cost measurement built on it measures nothing. → Measure with `claude -p --settings <file>` and a raised `skillListingBudgetFraction`.
- **`$TMPDIR` can be on another device than the repo** — `mktemp` + `mv` is then copy-and-unlink, and Python's `shutil.move` fallback truncates the target. → Create the temp file in the target's own directory and `os.replace()`.
- **A plugin updated mid-session runs its old version until `/reload-plugins`** — the skill preamble's base directory names the version that actually loaded. → Reload, then check that path before running an installer skill.
- **In project rules `paths:` is the conditional key; `globs:` loads the rule always** (Claude Code 2.1.296). A path rule rides the Read result and agents mostly ignore it; `Explore` gets no always-loaded rules. → Use `paths:`.
- **A CLI flag named `--force` cannot be run by Claude here** — the security pre-check hook blocks any `--force*` token, not only `git push --force`. → Name flags by what they do (`--discard-edits`).
- **Test tooling is not on PATH in the dev container** — `bats: command not found`. → `./scripts/dev/test.sh` provisions pytest and bats into `.venv/` and runs both; call `.venv/bin/bats` directly for one file.
- **`timeout` does not exist on macOS or `macos-latest` runners** — `run timeout 5 …` exits 127 there, so the hang guard never runs. → Copy `_timeout` from `observability-timed-wrapper.bats` (perl fallback that forks).
- **A `!` in a commit subject reaches git as `\!` under the Bash tool's zsh**, and the commit-msg hook rejects `feat\!:`. → Mark a breaking change with a `BREAKING CHANGE:` footer, not the `!` subject form.
- **`json.dump` escapes non-ASCII by default** — a script that changes one field rewrites every line holding `ä` or `→` as `\uXXXX`. → Pass `ensure_ascii=False` and write a trailing newline.
- **The skill listing is budgeted, so every skill added truncates every description** — sessions warn `N skills, X chars > 30000 budget`; each description is capped by `skillListingMaxDescChars`. → Count the listing's chars before adding a skill.
