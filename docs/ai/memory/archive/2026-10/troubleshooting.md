# Troubleshooting — archived 2026-10

## Python/bash whitespace divergence in drift-check — Status: resolved
<!-- 2026-05-13 -->
Python `strip()` trims only the ends; bash `tr -d '[:space:]'` also removes internal whitespace, so `"h 7"` classified differently in each. → Use `re.sub(r'\s+', '', ...)` to match bash semantics. Parallel bash and python implementations of one check must not diverge.
