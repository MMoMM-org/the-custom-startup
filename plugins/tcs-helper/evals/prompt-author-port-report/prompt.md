---
description: Port a Claude chat template to a small local model; the report lists each change with its profile topic or entry, labels unverified changes, and carries exactly one delivery label.
tags: [prompt-author, port, small-local, spec-023]
runs: 3
max_turns: 30
timeout_seconds: 900
allowed_tools: [Read, Glob, Grep, Write, Edit]
expected_outcome: port/review-helper.md has no AskUserQuestion or Claude-project reference; port/report.md lists each change with a small-local profile topic or PA entry, labels changes from unverified topics unverified, and says "not evaluated on target" and no other delivery label.
---

/tcs-helper:prompt-author Port this chat template to a small local model: llama3.2 (3B) running in
Ollama, used as a chat assistant with the template pasted as the first message. The template is
`templates/review-helper.md`; its full text is below, and the repository holds nothing else.

Write the ported template to `port/review-helper.md` and your port report (everything you would tell me
about the port apart from the template itself) to `port/report.md`, both in the current working
directory. I am not available for questions: decide anything I left open yourself and say what you
decided in your reply.

````markdown
# Code review helper

Works with a Claude project: the repository's CLAUDE.md is pre-loaded, so follow its conventions.

You are a senior reviewer. When I paste a diff, review it.

**IMPORTANT:** ALWAYS ask me one question at a time with the AskUserQuestion tool before you review.

- Never comment on formatting; the linter owns that.
- Rate each finding as blocking, major or minor.
- Show me the findings and wait for my approval before you write the summary.

When everything is approved, suggest that I run `/tcs-workflow:review` for the full multi-agent pass.

Diff:
{{DIFF}}
````

Write both files, then give me a short summary.
