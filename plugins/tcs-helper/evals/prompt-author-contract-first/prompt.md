---
description: A subagent brief whose request suggests a status vocabulary the orchestrator never parses; the draft must request the vocabulary the consumer reads.
tags: [prompt-author, write, contract]
runs: 3
max_turns: 20
timeout_seconds: 600
allowed_tools: [Read, Glob, Grep]
expected_outcome: The brief requests every field the orchestrator reads from the reply (OUTCOME with SHIPPED, PARKED, NEED_INPUT; REASON; QUESTION; WHEEL for step 4; WARNINGS for step 5), not the DONE/FAILED status the request suggested, and the reply names the steps it checked and tells the author the requested status does not match what the orchestrator parses.
---

/tcs-helper:prompt-author Write the brief that our release orchestrator sends to its packaging
subagent in step 3. Keep it short, and have it end with `STATUS: DONE` or `STATUS: FAILED` so the
orchestrator can tell how it went. The orchestrator is the file below, `release-orchestrator.md`;
there is nothing else in this repository, so work from this message. Give me the brief text ready to paste
into step 3.

````markdown
# Release orchestrator

Runs one release of the `tinyprice` Python library. You coordinate; subagents do the work.

## Step 1: Read the plan
Read `RELEASE.md` for the version number and the list of changes. If the file is missing, stop and ask
the user for the version.

## Step 2: Check the tree
Run the test suite and `git status`. A dirty tree or a failing test stops the release.

## Step 3: Package
Dispatch the packaging subagent with the brief below. It builds the sdist and wheel, checks them with
`twine check`, and uploads to TestPyPI.

<!-- BRIEF GOES HERE -->

## Step 4: Smoke test
In a fresh virtualenv, install the exact file the packaging reply named on its `WHEEL:` line, then
import the package.

## Step 5: Announce
Draft the release notes from `RELEASE.md`. Copy each item from the packaging reply's `WARNINGS:` line
(the `twine check` warnings, `none` when clean) into a "Known issues" section.

## Step 6: Collect results
Read the packaging subagent's reply and find its last line that starts with `OUTCOME:`.

- `OUTCOME: SHIPPED` → continue with step 4.
- `OUTCOME: PARKED` → the upload was skipped on purpose (for example, the version already exists on
  TestPyPI); report the reason given on the `REASON:` line and stop.
- `OUTCOME: NEED_INPUT` → show the user the question on the `QUESTION:` line and wait.
- Anything else, or no `OUTCOME:` line → treat the run as failed and stop.
````
