---
description: Write a skill for the test-name output format; graded on how its examples are chosen and backed by rules.
tags: [skill-author, examples, spec-023]
runs: 3
max_turns: 30
timeout_seconds: 900
allowed_tools: [Read, Glob, Grep, Write, Edit]
expected_outcome: skills/test-name/SKILL.md exists and shows the output format with 3-5 examples that differ in kind, each behaviour they show also stated as a rule.
---

/tcs-helper:skill-author Create a new personal skill, `test-name`, and write it to
`skills/test-name/SKILL.md` in the current working directory. The skill names unit tests in our Python code base. The format is
easier to show than to describe, so the skill should include examples of good output alongside its
rules. Keep it short. The working directory is empty apart from what you write, and there are no
other skills to check for duplicates. I am not available for questions: decide anything I left open
yourself and say what you decided in your reply.

The output format:

1. The pattern `test_<unit>_<condition>_<expected>`, all snake_case.
2. `<condition>` describes the input or state, not the implementation, such as `empty_cart` rather than `calls_len`.
3. `<expected>` states the observable outcome, such as `returns_zero` or `raises_value_error`.
4. A test of the default, happy path uses `valid_input` as its condition.

Write the finished skill file, then give me a short summary.
