# Where an Expectation Comes From

A test is only as independent as its expected value. Each shape below passes while the code is
wrong, because the expectation shares something with the code it checks.

---

## The expected value must not come from the code under test

Ask **where the expected value came from**, not what the test did to compute it. If the code under
test produced it at any remove, it is a second sample, not an expectation, and two samples of one
function agree about everything that function does.

- **Re-implementation.** A helper that parses, globs or normalises the same input the production
  code does is a second implementation. It shares every blind spot: both copies agree on exactly
  the inputs both get wrong.
- **Output as expectation.** Capturing a block the serializer wrote, then asserting it is still in
  the next file the same serializer wrote, proves self-consistency only. Field reordering or a
  dropped `sorted()` changes both sides and passes. This duplicates no logic, so it survives every
  "did you re-derive the logic?" review.

Prefer, in order: a hand-typed literal (insert items out of order so sorting is pinned); a fixture
whose observable outcome differs, so the existing comparison catches it; a value from a source the
code never reads.

## Agreement between two implementations is not correctness

A test holding two implementations of one rule in agreement turns silent divergence into a failure.
But agreement has two causes, both right or both wrong the same way, and the test cannot tell them
apart.

- Tie at least one side to ground truth: the real repository, a hand-written expectation, a tree
  whose answer you derived from the written rule.
- Look at the verdict distribution. If nearly every case gives the same answer, ask what a rule
  that always returned it would score.
- State which question each side answers. A file-scoped and a repo-scoped check agree on fixtures
  where the signal sits at the root, and disagree everywhere else.

## A partition invariant cannot see misassignment

"Disjoint, and the union is the whole domain" catches double assignment and omission. It is blind
to an item landing in the **wrong** set, and to **how** it got there.

- **Tie keys across the boundary:** if two modules must agree on identifier strings, assert
  `set(theirs) == set(mine)`. Two separately pinned literals miss a one-sided rename.
- **Assert the size of the enumerated space** as a hand-written constant. A sweep that silently
  shrinks still passes. Never derive that constant from the table under test.
- **Raise on input the function cannot partition honestly** instead of absorbing it into a shape
  that validates.

## Assert a property of the element you changed

For a transformation, "the result still parses" plus "everything else is unchanged" can be blind to
the one element the function rewrites: the second excludes it by definition, and the first is a
tolerant parser. A `(?m)^name:.*$` rewrite on a CRLF file drops the `\r` (`.` matches it), and
`yaml.safe_load` accepts the mixed line endings.

List what the changed element carries besides the value you meant to change, and assert what must
survive: line ending, surrounding whitespace and indentation, encoding and BOM, position among
siblings, file mode. Then ask which assertion would fail if that element were damaged while its
value still looked right. If none, more inputs will not help.

## Stubs emit the real wire format, envelopes included

A stub for a CLI or service must emit what production returns, wrapper included, even when the code
only reads a nested field. `claude -p --output-format json` puts the payload as a JSON **string**
under `.result`; a stub emitting the flat payload keeps a suite green while every real call fails.

- Capture one real response and build the stub from it.
- If the stub omits fields on purpose, say which and why in a comment.
- Include one case that exercises the unwrap path, such as an envelope without `result`.

## Fixtures for a parser must be valid in the target language's own tools

A parser tested against syntax no real codebase produces passes its tests and fails on real input.
Validate every fixture with the language's own tool before relying on it: `tsc --noEmit --strict`
for TypeScript, `jq -e .` for JSON, `python3 -c 'import ast,sys; ast.parse(open(sys.argv[1]).read())'`
for Python. When dispatching an implementer, state this requirement; a TDD gate checks RED before
GREEN, not whether fixtures are real syntax.
