---
description: Write a skill for the api-error output format; graded on how its examples are chosen and backed by rules.
tags: [skill-author, examples, spec-023]
runs: 3
max_turns: 30
timeout_seconds: 900
allowed_tools: [Read, Glob, Grep, Write, Edit]
expected_outcome: skills/api-error-response/SKILL.md exists and shows the output format with 3-5 examples that differ in kind, each behaviour they show also stated as a rule.
---

/tcs-helper:skill-author Create a new personal skill, `api-error-response`, and write it to
`skills/api-error-response/SKILL.md` in the current working directory. The skill designs the JSON error response body our HTTP API returns. The format is
easier to show than to describe, so the skill should include examples of good output alongside its
rules. Keep it short. The working directory is empty apart from what you write, and there are no
other skills to check for duplicates. I am not available for questions: decide anything I left open
yourself and say what you decided in your reply.

The output format:

1. A JSON object with `code` (UPPER_SNAKE_CASE, stable across releases), `message` (one sentence for a human) and `status` (the HTTP status as a number).
2. A validation error adds `fields`: a list of `{"field": ..., "problem": ...}` objects, one per invalid field.
3. A rate-limit error (429) adds `retry_after_seconds` as a number.
4. `message` never contains stack traces, SQL, or internal host names.

Write the finished skill file, then give me a short summary.
