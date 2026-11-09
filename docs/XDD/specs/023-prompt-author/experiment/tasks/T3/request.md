I have a code-review orchestrator in Claude Code. It sends one reviewer subagent per perspective (Claude Sonnet, Claude Code default system prompt). The subagent sees nothing of the orchestrator's conversation. It sees only the prompt I give it, plus its tools: Read, Grep, Glob, and Bash restricted to `git diff`, `git log`, `git show` and `git status`. It runs in the user's working tree. That tree is shared with the user and may contain uncommitted work that belongs to a teammate.

This is the perspective I need the reviewer prompt for:

| Perspective | Intent | What to look for |
|---|---|---|
| Correctness & Quality | Find defects before they merge | logic errors, wrong conditions and off-by-ones, missing null/None handling, error handling gaps, resource leaks, unsafe input handling, naming and pattern inconsistencies |

For each review the orchestrator has the commit range under review (`{{BASE}}..{{HEAD}}`) and the repository path, which is the subagent's working directory.

After all reviewers return, the orchestrator synthesizes their output:
1. Deduplicate findings by location (within 5 lines), keeping the highest severity.
2. Sort by severity descending, then confidence descending.
3. Assign IDs (C1, H1, M1, L1, …) and build a summary table.

Write the prompt template the orchestrator sends to this reviewer subagent. Use `{{BASE}}` and `{{HEAD}}` as placeholders. Return it between `<prompt>` and `</prompt>` and nothing else.
