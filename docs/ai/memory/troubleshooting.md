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

## A hardcoded `LC_ALL=en_US.UTF-8` in a bats test breaks where the locale is absent — Status: resolved
<!-- 2026-11-27 -->
This container has only C.utf8/de_DE.utf8: a new bash warns on stderr (no-stderr check fails), an in-shell assignment stays in C silently. → Use `_utf8_locale` from tests/bats/lib/helpers.bash and assert it is non-empty.

## A `@dataclass` module loaded via `spec_from_file_location` crashes on Python 3.11 — Status: resolved
<!-- 2026-11-27 -->
With `from __future__ import annotations`, `exec_module` raises because dataclasses looks up `sys.modules[cls.__module__]`. → Set `sys.modules[name] = module` before `spec.loader.exec_module(module)`.
