# Active — the-custom-startup
<!-- Always loaded: @-imported from CLAUDE.md, so it reaches every session AND every subagent. -->
<!-- Budget: ≤ 2.5 KB. Full means something leaves before anything enters. -->
<!-- Admission: silent violation AND broad trigger, both. Criterion and rejected candidates: -->
<!-- plugins/tcs-helper/skills/memory-add/reference/category-formats.md § Active layer -->

<!-- 2026-09-01 -->
- **bash 3.2 breaks two regex forms in `[[ =~ ]]`** — PCRE `\s`/`\b` never match; bounded `^.{m,n}$` fails on matching input, so hooks silently never fire. → `[[:space:]]`, `([^[:alnum:]_]|$)`, `${#var}`; BSD `[[:<:]]` fails open on Linux.
- **Non-final `[[ ]]` (bash 3.2) and `! cmd` (any bash) cannot fail a bats test** — ubuntu's bash 5 enforces `[[ ]]`, so only local/macOS runs are blind. → Use `_has`/`_lacks` (`tests/bats/lib/`); `test_bats_blind_assertions.py` rejects both.
- **jq under `set -e` makes a hook fail closed** — a non-zero exit on malformed JSON reads to Claude Code as "deny tool call". → Append `2>/dev/null || true` to every jq command substitution in a hook meant to fail open.
- **A failed `git init` in a bats fixture leaks commits onto the parent branch** — git falls back to the parent `.git/`. Tell: stray fixture commits on your branch. → Use `git -C "$tmpdir"` plus `GIT_CONFIG_GLOBAL=/dev/null`.
- **`CLAUDE_PLUGIN_ROOT`/`CLAUDE_PLUGIN_DATA` reach only harness-spawned plugin code** — not git-spawned hooks (`core.hooksPath`), not Bash-tool subprocesses. `CLAUDECODE=1` does propagate. → Git-hook code must self-derive its paths.
- **Scope reviewer prompts to a commit range, not the working tree** — reviewers scan by path and then flag a teammate's uncommitted work as your task's extras. → Name the range, the expected files, and say to ignore the rest.

<!-- 2026-09-04 -->
- **A `|| fallback` inside `$( )` appends to partial output, not replaces it** — a command that writes and *then* fails leaves both: `printf '%.0f' 23.5` in a comma locale yields `230`. → Assign whole values: `x=$(cmd) || x=0`.

<!-- 2026-10-23 -->
- **A fixed file name under `$TMPDIR` is shared by every session** — a failed write leaves another session's file in place, and `git commit -F` commits its message. → Write message and scratch files to the session scratchpad.
