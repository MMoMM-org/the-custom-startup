I'm building an orchestrator in Claude Code that implements a plan task by task. For each task it dispatches a fresh implementer subagent (Claude Sonnet, Claude Code default system prompt) through the Agent tool. The subagent sees nothing of the orchestrator's conversation. It sees only the prompt I give it, plus its tools: Read, Edit, Write, Glob, Grep, and Bash restricted to `git` and `python3 -m unittest`. It works directly in the repository.

For each task the orchestrator has:
- the task text, copied from the plan;
- the section of the solution design document (SDD) that the task refers to, when there is one;
- scene-setting: spec name, phase, top-level repo directories, current branch.

We work test-first and want the work committed when the subagent is done.

When the subagent returns, the orchestrator runs this logic on its final message:

```
DONE                → proceed to spec compliance review
DONE_WITH_CONCERNS  → read concerns; if about correctness/scope → address first; else note and proceed
NEEDS_CONTEXT       → provide the missing context, re-dispatch
BLOCKED             → assess: context problem → re-dispatch; too complex → escalate model;
                      task too large → split; plan wrong → escalate to user
```

Write the prompt template the orchestrator sends to the implementer subagent. Mark where the per-task material goes with `{{TASK_TEXT}}`, `{{SDD_SECTION}}` (may be empty) and `{{SCENE}}`. Return the template between `<prompt>` and `</prompt>` and nothing else.
