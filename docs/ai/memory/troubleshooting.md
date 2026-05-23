# Troubleshooting — the-custom-startup
<!-- Known issues and proven fixes. Updated: 2026-05-13 -->
<!-- Format: ## [Issue title] — Status: open/resolved — [fix description] -->
<!-- Resolved entries are archived by /memory-cleanup, not deleted -->

## spec-012 T2.2: Python/bash whitespace divergence in drift-check — Status: resolved
<!-- 2026-05-13 -->
Real parity bug: Python `strip()` removes only leading/trailing whitespace, but bash `tr -d '[:space:]'` removes ALL whitespace including internal. Version file `"h 7\n"` would return `"h7"` (bash) vs `"h 7"` (python), causing different OK/DRIFT classifications. Fixed by replacing `strip()` with `re.sub(r'\s+', '', ...)` to match bash semantics exactly. ADR-4 forbids bash/python divergence — spec-driven testing caught this before merge. New parity test row validates internal-space case; all 24 tests pass.

## spec-014 T1.3: `_write_pr_state_cache` wholesale-replace silently drops fields — Status: resolved
<!-- 2026-05-23 -->
The cache writer's jq expression at `cache.sh:263-270` is `.branch_state[$branch] = { state, checked_iso, ... }` — it **replaces** the branch entry, it does not merge into the existing one. Any caller that does a partial write (e.g., learns the merge_commit SHA later and wants to add it to an entry that already has `state` + `number`) MUST either (a) read the existing entry's fields first and pass them all back in to the writer, or (b) be aware the omitted fields will be silently dropped. T1.3 originally passed `pr_number="0"` on the SHA write-back; that caused the `number` field a prior write captured to vanish. Discovered only because a spec-compliance fix added an explicit "is the SHA round-tripped through the writer" assertion to the cache-miss test (would otherwise have shipped silently). Fix pattern at `block-bad-git-ops.sh:312-326`: read `_existing_number` via `_pr_state_path` + `jq '.branch_state[$b].number // 0'` before the rewrite. Applies to ANY caller of `_write_pr_state_cache` doing a partial update — until/unless the writer is changed to merge instead of replace.
