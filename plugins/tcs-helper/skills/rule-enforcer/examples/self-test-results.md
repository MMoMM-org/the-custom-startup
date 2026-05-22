# Self-Test Results

Run each fixture from `self-test-fixtures.md` in a fresh Claude Code session
after the rule-enforcer skill is indexed.

For each row: record the date, the actual mechanism the skill produced, and PASS/FAIL.

| Date | Fixture | Expected Mechanism | Actual Mechanism | PASS / FAIL | Notes |
|------|---------|--------------------|--------------------|-------------|-------|
| TBD  | Fixture 1 | CI workflow (auto-PR or commit with [skip ci]) | _pending_ | _pending_ |       |
| TBD  | Fixture 2 | git pre-push hook (warn-only, lets push through) | _pending_ | _pending_ |       |
| TBD  | Fixture 3 | Claude PostToolUse hook (post-tool reminder/correction) | _pending_ | _pending_ |       |

## Run instructions

1. Restart Claude Code session so the rule-enforcer skill is indexed.
2. For each fixture: invoke `/enforce-rule "<rule text>"` and answer Q1-Q4 per the fixture spec.
3. Record the actual Step 6 mechanism + Step 8 hand-off in the table.
4. Mark PASS if actual matches expected; FAIL otherwise.
5. Any FAIL: file a follow-up to fix the matrix or workflow logic.
