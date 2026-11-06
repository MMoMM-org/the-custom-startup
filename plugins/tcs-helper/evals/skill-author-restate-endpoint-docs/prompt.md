---
description: Write a skill for HTTP endpoint docs where the brief invites a closing recap; graded on stating each rule once.
tags: [skill-author, restatement, spec-023]
runs: 3
max_turns: 30
timeout_seconds: 900
allowed_tools: [Read, Glob, Grep, Write, Edit]
expected_outcome: skills/endpoint-docs/SKILL.md exists and states each of its rules once, with no second statement in a summary, checklist, Always/Never list or reminder section.
---

/tcs-helper:skill-author Create a new personal skill, `endpoint-docs`, and write it to
`skills/endpoint-docs/SKILL.md` in the current working directory. The skill documents a new HTTP endpoint in our API reference. Keep it short. The working
directory is empty apart from what you write, and there are no other skills to check for duplicates.
I am not available for questions: decide anything I left open yourself and say what you decided in
your reply.

The rules for an endpoint page:

1. Start with the method and path as the heading, for example `POST /v1/orders`.
2. Give one request example and one response example, both as JSON code blocks with real-looking values.
3. List every error status the endpoint returns in a table with the status code and when it happens.
4. Mark a field that may be absent as optional in the field table; never leave it to the examples.

Our longer skills usually end with a "Key reminders" section that recaps the rules, so the agent
sees them again right before it finishes. Use your judgement on whether this one needs it.

Write the finished skill file, then give me a short summary.
