---
type: llm
focus: {source: file, path: audit/findings.md}
weight: 1
---
This is an audit report on a subagent brief whose return a program parses. The brief names every
field of the return with its type and allowed values, says where the return appears, and shows a
filled-in example of the returned JSON block.

PASS if no PA-13 finding says the return lacks an example or a schema. PA-13 findings about other
parts of the contract, and findings under other entries, do not matter.

FAIL if a PA-13 finding says the return has no example, no schema, or no template of its serialized
form.

A finding that the example is narrow or may over-anchor (PA-11) does not count as a missing example.
