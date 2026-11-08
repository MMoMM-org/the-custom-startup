---
description: Write a subagent brief from a fixed four-step script; the brief must say what to do when input is unclear, when to stop and report, and give the goal and done criterion.
tags: [prompt-author, write, agentic, spec-023]
runs: 3
max_turns: 30
timeout_seconds: 900
allowed_tools: [Read, Glob, Grep, Write, Edit]
expected_outcome: briefs/migrate-brief.md exists and states an action for missing or unclear input, a stop-and-report condition other than success, and the goal with a done criterion rather than only the four steps.
---

/tcs-helper:prompt-author Write the brief our maintenance orchestrator sends to its migration
subagent in step 2, and save it to `briefs/migrate-brief.md` in the current working directory.

The subagent runs in Claude Code with Read, Grep, Edit and Bash, in a checkout of our `ledgerly`
Python service. Its job: replace every call of the deprecated `ledgerly.money.round_half_up(x)` with
`ledgerly.money.quantize(x, rounding="half_up")`. I would write it as four steps: 1. grep for
`round_half_up`; 2. replace each call; 3. run `pytest`; 4. report back. Keep it about that short.

The orchestrator is the file below, `maintenance-orchestrator.md`; there is nothing else in this
repository, so work from this message. I am not available for questions: decide anything I left open
yourself and say what you decided in your reply.

````markdown
# Maintenance orchestrator

Runs one deprecation clean-up on the `ledgerly` repository. You coordinate; subagents do the work.

## Step 1: Open the issue
Find the open issue labelled `deprecation` and note its number.

## Step 2: Migrate
Dispatch the migration subagent with `briefs/migrate-brief.md`, passing the repository path and the
issue number in the task prompt.

## Step 3: Collect
Read the subagent's reply and find its last line that starts with `RESULT:`.

- `RESULT: MIGRATED` → open a pull request with the files named on the `FILES:` line.
- `RESULT: BLOCKED` → post the text of the `REASON:` line as a comment on the issue and stop.
- Anything else, or no `RESULT:` line → mark the run failed and stop.
````

Write the brief file, then give me a short note.
