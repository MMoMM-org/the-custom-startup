---
type: llm
focus: last_message
weight: 1
---
Look at the reply's text outside the drafted brief (the note or explanation addressed to the person
who asked).

PASS if that text tells the person that the `STATUS: DONE` / `STATUS: FAILED` ending they asked for
does not match what the orchestrator parses (the `OUTCOME:` line), so the brief uses the orchestrator's
vocabulary or one side would have to change.

FAIL if the reply uses `STATUS: DONE` / `STATUS: FAILED` as asked, or switches to `OUTCOME:` without
telling the person that their requested ending did not match, or the only mention is inside the brief.
