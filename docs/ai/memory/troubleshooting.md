# Troubleshooting — the-custom-startup
<!-- Known issues and proven fixes. Updated: 2026-10-29 -->
<!-- Format: ## [Issue title] — Status: open/resolved, then the fix in one or two lines -->
<!-- Resolved entries are archived by /memory-cleanup, not deleted -->
<!-- A resolved record earns its place only if the fix is non-obvious from the code -->

## A Bash call run from directory D creates `D/.claude/` — Status: open
<!-- 2026-10-23 -->
Gitignored, so `git status` is clean, but tests that list subdirectories count it: red locally, green in CI. → Skip dot-prefixed names in directory discovery; prefer absolute paths over `cd`.

## Python `re` `$` matches before a trailing newline — Status: resolved
<!-- 2026-11-26 -->
A `^[A-Z_]+$` guard with `.match` accepted `"RULE\n"`, so a newline reached report output (spec 024). → Validation guards use `\A…\Z` with `fullmatch`; mutate `.pyc`-safe (`PYTHONDONTWRITEBYTECODE=1`).
