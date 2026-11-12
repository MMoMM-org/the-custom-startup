# Failure Investigation

How to investigate, categorize, and fix every failing test.

---

## Failure Categories

| Cause Category | What to Look For | Action |
|---------------|-----------------|--------|
| **Your changes broke it** | Test was passing in baseline, fails after your changes | Fix the implementation or update the test to match new correct behavior |
| **Test is outdated** | Test assertions don't match current intended behavior | Update the test to match correct behavior |
| **Test has a bug** | Test logic is flawed (wrong assertion, bad mock, race condition) | Fix the test |
| **Missing dependency** | Import errors, missing fixtures, setup failures | Add the missing piece |
| **Environment issue** | Port conflicts, file locks, timing issues | Fix the environment setup |
| **Actual bug in code** | Test correctly catches a real bug | Fix the production code |

## Fix Protocol

For EVERY failing test:

1. **Read the failing test** — understand what it's testing and why
2. **Read the code under test** — understand the implementation
3. **Determine the correct fix** — fix the code, the test, or both
4. **Apply the fix** — edit the minimal set of files needed
5. **Re-run the specific test** — confirm the fix works
6. **Re-run the full suite** — confirm no regressions

## Iterate

Repeat until ALL tests pass. If fixing one test breaks another:
- Do NOT revert and give up
- Investigate the chain of dependencies
- Find the root cause that satisfies all tests

## Escalation (Last Resort)

This is ONLY acceptable for:
- External service dependencies that are down
- Infrastructure requirements beyond the codebase (e.g., database migration needed)
- Permission/access issues

This is NOT acceptable for:
- "Complex" code you don't understand — Read it more carefully
- "Might break something else" — Run the tests and find out
- "Not my responsibility" — You touched the codebase, so it is. Start step 1 of the Fix Protocol.

Use the escalation template from `output-format.md`.

## Ownership Counter-Actions

When you catch yourself about to deflect, do the right column instead. None of them ends in a
report that leaves the test red.

| Instead of... | Do... |
|---------------|-------|
| "This test was already failing" | Run it, read the assertion, trace the wrong value back to the code that produces it, and fix that (Fix Protocol above). |
| "Not caused by my changes" | Fix it anyway: ownership does not depend on the cause. Need the cause for the commit message? Run the test on the base commit, then fix it. |
| "Pre-existing issue" | Categorize it with the Failure Categories table and apply that row's action. |
| "This is outside the scope" | Fix it in this change. Only the escalation cases above go to the user, with the escalation template. |
| "The test might be flaky" | Run it 3 times. Fails every time: it is not flaky, fix it. Fails sometimes: find the nondeterminism (time, ordering, shared state, network, random seed) and remove it. |
| "I'd recommend fixing this separately" | Fix it now. A separate fix is acceptable only for an escalation case, reported with the template. |
| "This appears to be a known issue" | Look for the tracking issue. Tracked and the fix lies outside the codebase: escalate with the template and link it. Otherwise fix it. |
