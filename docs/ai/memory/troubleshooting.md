# Troubleshooting — the-custom-startup
<!-- Known issues and proven fixes. Updated: 2026-09-01 -->
<!-- Format: ## [Issue title] — Status: open/resolved, then the fix in one or two lines -->
<!-- Resolved entries are archived by /memory-cleanup, not deleted -->
<!-- A resolved record earns its place only if the fix is non-obvious from the code -->

## Python/bash whitespace divergence in drift-check — Status: resolved
<!-- 2026-05-13 -->
Python `strip()` trims only the ends; bash `tr -d '[:space:]'` also removes internal whitespace, so `"h 7"` classified differently in each. → Use `re.sub(r'\s+', '', ...)` to match bash semantics. Parallel bash and python implementations of one check must not diverge.

## `_write_pr_state_cache` replaces the branch entry rather than merging — Status: resolved
<!-- 2026-05-23 -->
Standing caveat, not just a past bug: any partial write silently drops the fields it omits. → Every caller must read the existing entry and pass all fields back in, until the writer merges instead of replacing. [cache.sh:263]
