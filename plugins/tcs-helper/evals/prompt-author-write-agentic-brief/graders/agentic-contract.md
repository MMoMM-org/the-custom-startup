---
type: llm
focus: {source: file, path: briefs/migrate-brief.md}
weight: 1
---
This is a brief for a subagent that runs alone in a loop with tools and cannot ask questions mid-run.
Check whether it states each of these three things.

(a) Unclear input: it names a specific action for a missing input or an unclear case, such as a call
it cannot migrate mechanically, a missing repository path or issue number, or tests that already fail
before the change. A named status or reply line with the open question or reason counts (for example
`RESULT: BLOCKED` with a `REASON:` line). "Ask the user" alone, or "be careful", does not count.
(b) Stop and report: it states at least one condition other than success under which the subagent
stops and reports, such as tests that fail after the change, the same error twice, or a retry limit,
and says what the reply contains when it stops that way.
(c) Goal over script: it states the goal of the job and a done criterion (what has to be true for the
job to be complete, for example no `round_half_up` call left and the tests passing). A numbered list of
steps is fine if the goal and the done criterion are also stated; a list of steps alone does not count.

PASS only if all three of (a) to (c) are present. FAIL if any one is missing. Judge only the presence
of each item; the length and style of the brief do not matter.
