---
type: llm
focus: {source: file, path: agents/compose-fixer.md}
weight: 1
---
This is an agent definition. Its caller is a program that parses what the agent returns (a diff proposal).
Check the body (everything after the frontmatter; the description does not count) for an output
contract that a parser could be written from without guessing. All three must hold:

(a) Every field: it names each field (or part) of the return value, including any nested items
(for example each field of one finding, row or change), not only the top-level container.
(b) Type or allowed values: every field has a type (string, integer, boolean, list of X, path, ...),
and every field that takes one of a fixed set of values (a status, verdict, severity, decision or
kind) lists those allowed values. A status, verdict or severity field typed only as "string" fails.
(c) Example or schema: it shows the return as the caller receives it, either a filled-in example
of the returned value or a schema or template of its serialized form (a JSON or YAML skeleton, a
JSON Schema, a line template such as `VERDICT: <value>`). A table or list that only describes the
fields does not count as (c) by itself.

PASS only if (a), (b) and (c) all hold. FAIL if any one is missing. Judge only these three points;
the quality of the rest of the agent does not matter.
