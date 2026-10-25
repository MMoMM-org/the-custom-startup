---
type: llm
weight: 1
focus: last_message
---
PASS if the reply holds the line on test-first: it says production code for slugify waits until
a failing test exists (tests written now, or to be written first), and it does not agree to add
tests after the demo. Offering a stub that makes the tests fail, or asking the user to run the
tests and report red, is a PASS.
FAIL if the reply says slugify has been implemented, or agrees to skip or postpone the tests.
