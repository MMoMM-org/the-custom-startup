---
description: Rewrite an existing 281-byte prompt; the delivery note must give both sizes and name the failure each added section prevents.
tags: [prompt-author, write, cut-test, spec-023]
runs: 3
max_turns: 30
timeout_seconds: 900
allowed_tools: [Read, Glob, Grep, Write, Edit]
expected_outcome: notes/commit-msg.md states the old size (281 bytes) and the new size, and names, for each section the replacement adds, the PA entry or failure it prevents.
---

/tcs-helper:prompt-author Our commit hook sends the prompt below to the Claude API (Claude Haiku) with
the staged diff filled in at `{{diff}}`, and writes the model's whole reply into `.git/COMMIT_EDITMSG`
as the commit message. It works, but some replies start with "Here's a commit message:" or wrap the
message in a code fence, and those end up in the git history. Rewrite the prompt so the hook can use
the reply as it is.

First save the current prompt, exactly as given, to `prompts/commit-msg.txt` in the current working
directory. Then write the replacement to `prompts/commit-msg.new.txt`, and write your delivery note
(everything you would tell me about the replacement) to `notes/commit-msg.md`. There is nothing else in
this repository, so work from this message. I am not available for questions: decide anything I left
open yourself and say what you decided in your reply.

```text
You write git commit messages. You will get a staged diff. Write a good commit message for it.
Use the conventional commits style, for example "fix: handle empty cart". Keep the subject short.
Add a body if the change needs explaining. Be concise and professional.

Diff:
{{diff}}
```

Write the three files, then give me a short summary.
