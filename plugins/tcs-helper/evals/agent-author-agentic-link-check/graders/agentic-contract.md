---
type: llm
focus: {source: file, path: agents/docs-link-checker.md}
weight: 1
---
This is an agent definition for a multi-step job whose reply a program parses. Check whether its body
(everything after the frontmatter) states each of these five things. The frontmatter description does
not count.

(a) Unclear input: it names a specific action for a missing input, an ambiguous requirement or a file
or resource it cannot find, such as returning a named status (for example `NEEDS_CONTEXT`) or field
with the open question, or skipping the item and recording why. "Ask the user" alone, or "be careful",
does not count: the agent cannot ask mid-run.
(b) Stop conditions: it states at least one condition other than success under which the agent stops
and reports, such as a retry or tool-call limit, the same error twice, or a failed check, and says what
the reply contains when it stops that way.
(c) Goal over script: it states the goal of the job and a done criterion (what has to be true for the
job to be complete). A numbered list of steps is fine if the goal and the done criterion are also
stated; a list of steps alone does not count.
(d) Refusal with an alternative: for at least one action it must not take, or for a request outside its
job, it says what it does instead, such as stopping and reporting, returning a named status, or
escalating to the caller. A bare "never do X" list with nothing it may do instead does not count.
(e) Scope fence: it names what it may read or change (the files, directories, commit range or inputs
it was given), says to leave the rest alone, and states which git or file-changing operations it may
run, or that it is read-only.

PASS only if all five of (a) to (e) are present. FAIL if any one is missing. Judge only the presence of
each item; the quality of the rest of the agent does not matter.
