---
description: Write a skill for the changelog-entry output format; graded on how its examples are chosen and backed by rules.
tags: [skill-author, examples, spec-023]
runs: 3
max_turns: 30
timeout_seconds: 900
allowed_tools: [Read, Glob, Grep, Write, Edit]
expected_outcome: skills/changelog-entry/SKILL.md exists and shows the output format with 3-5 examples that differ in kind, each behaviour they show also stated as a rule.
---

/tcs-helper:skill-author Create a new personal skill, `changelog-entry`, and write it to
`skills/changelog-entry/SKILL.md` in the current working directory. The skill writes the CHANGELOG.md entry for a release. The format is
easier to show than to describe, so the skill should include examples of good output alongside its
rules. Keep it short. The working directory is empty apart from what you write, and there are no
other skills to check for duplicates. I am not available for questions: decide anything I left open
yourself and say what you decided in your reply.

The output format:

1. A heading `## [x.y.z] - YYYY-MM-DD`.
2. Sections in this order, each only when it has items: `### Breaking`, `### Added`, `### Fixed`, `### Changed`.
3. Each item is one line, written for a user of the library, not for its developers, and ends with the pull request number in parentheses, such as `(#123)`.
4. A release with nothing user-visible gets the single item `- Internal changes only.` under `### Changed`.

Write the finished skill file, then give me a short summary.
