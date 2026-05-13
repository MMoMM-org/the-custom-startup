# Troubleshooting — the-custom-startup
<!-- Known issues and proven fixes. Updated: 2026-05-13 -->
<!-- Format: ## [Issue title] — Status: open/resolved — [fix description] -->
<!-- Resolved entries are archived by /memory-cleanup, not deleted -->

## spec-012 T2.2: Python/bash whitespace divergence in drift-check — Status: resolved
<!-- 2026-05-13 -->
Real parity bug: Python `strip()` removes only leading/trailing whitespace, but bash `tr -d '[:space:]'` removes ALL whitespace including internal. Version file `"h 7\n"` would return `"h7"` (bash) vs `"h 7"` (python), causing different OK/DRIFT classifications. Fixed by replacing `strip()` with `re.sub(r'\s+', '', ...)` to match bash semantics exactly. ADR-4 forbids bash/python divergence — spec-driven testing caught this before merge. New parity test row validates internal-space case; all 24 tests pass.
