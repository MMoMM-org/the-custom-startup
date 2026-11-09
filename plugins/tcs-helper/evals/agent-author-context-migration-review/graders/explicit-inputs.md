---
type: llm
focus: {source: file, path: agents/migration-reviewer.md}
weight: 1
---
This is an agent definition. The agent runs as a subagent: it sees only its own body and the brief its
caller sends, never the caller's conversation. The request that produced it referred to facts from that
conversation ("the file we discussed", "the usual branch", "the bug from earlier", a convention
"mentioned once", "the test command from last time" and the like). Check the body (everything after
the frontmatter; the description does not count) for two things.

(a) Explicit inputs: every fact the job depends on that the request took from the conversation (which
file, branch, bug, convention, rule, command or scale) is named as an input the caller passes, in an
input or parameter section or an equivalent list, or the body tells the agent to report it as missing
or ask the caller for it when the brief lacks it. A concrete value the author invented in place of
the caller's fact (a guessed branch name, path or rule) does not count, unless the body makes it a
default the caller can override.
(b) No borrowed context: the body contains no wording that presumes the agent can see that conversation,
such as "as discussed", "the file we discussed", "the earlier bug", "the usual branch", "as before",
"from last time" or "the convention mentioned", used as if the agent already knew what it refers to.

PASS only if both (a) and (b) hold. FAIL if either fails. Judge only these two points; the quality of the
rest of the agent does not matter.
