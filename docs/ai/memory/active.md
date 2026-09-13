# Active — the-custom-startup
<!-- Always loaded: @-imported from CLAUDE.md, so it reaches every session AND every subagent. -->
<!-- Budget: ≤ 2.5 KB. Full means something leaves before anything enters. -->
<!-- Admission: silent violation AND broad trigger, both. Criterion and rejected candidates: -->
<!-- plugins/tcs-helper/skills/memory-add/reference/category-formats.md § Active layer -->

<!-- 2026-09-01 -->
- **bash 3.2 breaks two regex forms in `[[ =~ ]]`** — PCRE `\s`/`\b` never match; bounded `^.{m,n}$` returns false on matching input. Hooks that match commands then silently never fire. → Use `[[:space:]]`, `[[:<:]]`, `${#var}` checks.
- **A bare `[[ ]]` only fails a bats test as its body's last statement** — non-final `[[ ]]` silently passes even when false (negated or not); `[ ]`/`test` fails correctly anywhere. → Assert substrings via a `grep -qF` helper.
- **jq under `set -e` makes a hook fail closed** — a non-zero exit on malformed JSON reads to Claude Code as "deny tool call". → Append `2>/dev/null || true` to every jq command substitution in a hook meant to fail open.
- **A failed `git init` in a bats fixture leaks commits onto the parent branch** — git falls back to the parent `.git/`. Tell: stray fixture commits on your branch. → Use `git -C "$tmpdir"` plus `GIT_CONFIG_GLOBAL=/dev/null`.
- **`CLAUDE_PLUGIN_ROOT`/`CLAUDE_PLUGIN_DATA` reach only harness-spawned plugin code** — not git-spawned hooks (`core.hooksPath`), not Bash-tool subprocesses. `CLAUDECODE=1` does propagate. → Git-hook code must self-derive its paths.
- **The Bash tool reaps the process group at the tool-call boundary** — `nohup`/`disown` block SIGHUP, not harness teardown, so a backgrounded server dies silently. → Run it in the foreground inside a `run_in_background: true` call.
- **Scope reviewer prompts to a commit range, not the working tree** — reviewers scan by path and then flag a teammate's uncommitted work as your task's extras. → Name the range, the expected files, and say to ignore the rest.

<!-- 2026-09-04 -->
- **A `|| fallback` inside `$( )` appends to partial output, not replaces it** — a command that writes and *then* fails leaves both: `printf '%.0f' 23.5` in a comma locale yields `230`. → Assign whole values: `x=$(cmd) || x=0`.
- **`stat -f` is a format string on BSD and means *filesystem* on GNU** — `stat -f %m file` on Linux prints a whole filesystem report to stdout, then exits non-zero, so a `||` fallback appends the real value to it (235 chars where an mtime is 10). The free-block counts inside then change between calls, so an "untouched file" assertion fails under load only. → `m="$(stat -c %Y "$f" 2>/dev/null)" || m="$(stat -f %m "$f")"`.
- **Perf test p95 exceeds 100ms cap (2x the 50ms target) under load** — 124.8/156.4ms parallel-agent, 193.5ms alone; max 269ms = macOS's 151-286ms first-exec cost, warmup can't absorb. → `perf`-marked, deselected by default; run `pytest -m perf`.
