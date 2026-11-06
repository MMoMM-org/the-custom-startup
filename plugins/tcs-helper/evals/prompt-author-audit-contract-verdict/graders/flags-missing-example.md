---
type: llm
focus: {source: file, path: audit/findings.md}
weight: 1
---
This is an audit report on a subagent brief whose return a program parses (one verdict with its reasons). The brief names
every field of the return with its type and allowed values, and says where the return appears in the
reply, but it shows no example of the return and no schema or template of its serialized form.

PASS if the report has a finding citing PA-13 that names this gap: the return has no example (a
filled-in instance of the returned value) or no schema or template of its serialized form.

FAIL if there is no PA-13 finding, or the PA-13 finding is about something else, or the missing
example or schema is raised only under another entry or as "uncatalogued".
