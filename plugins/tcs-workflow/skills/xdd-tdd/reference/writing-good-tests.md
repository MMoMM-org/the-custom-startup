# Writing Good Tests

Load when writing or changing tests, adding mocks, or reviewing a test list.

A passing test is not evidence. A test earns its place by being able to **fail for
a real reason**. Two rules cover the ways that goes wrong.

```
1. Every test names the break it catches
2. Every test exercises the real thing
```

Strict TDD produces both for free: a test written first and watched failing against
real code has already proven it can fail.

---

## Rule 1 — Name the break

Before writing the test body, answer: **what production change should make this test
fail, and is that change a bug or a decision?**

A test earns its place by catching a wrong branch, a missing side effect, a wrong
argument, a boundary case, or a broken contract.

### Derive expectations independently

Use literals and hand-checked fixtures. An expectation computed by the code under
test — or by its helpers — passes no matter what that code does:

```typescript
// ❌ Mirror assertion — the same builder computes both sides. Always true.
const expected = buildSearchQuery({ tag: 'urgent' });
expect(buildSearchQuery({ tag: 'urgent' })).toBe(expected);

// ✅ Hand-derived literal
expect(buildSearchQuery({ tag: 'urgent' })).toBe('tag:"urgent"');
```

### The change-detector trap

If only an intentional decision can fail a test — a constant's value, exact message
wording, private structure — it fires on every redesign and sleeps through every bug.

Test the behavior that depends on the decision. Not `expect(MAX_RETRIES).toBe(5)`,
but "a failing call is retried 5 times and the 6th attempt never happens."

### The string-presence trap

**This one is TCS's occupational hazard.** Much of this repo is shell scripts, git
hooks, and Markdown skills — artifacts whose behavior is awkward to observe and whose
*text* is trivially greppable. That asymmetry is exactly the pressure that produces
counterfeit tests.

Asserting that a script, skill, or config **contains** a line proves only that the
source is the source. It passes when the artifact says the right words and does the
wrong thing, and it fails when someone rewords a sentence without changing behavior —
wrong on both sides.

```bash
# ❌ Source-is-source. Passes if the skill mentions the file and never reads it.
grep -q 'migrating-from-husky\.md' "$SKILL_PATH"

# ❌ Worse — a regex loose enough that almost any sentence with "commit" passes.
grep -qiE 'not.*commit|no.*auto.*commit|does not.*commit|never.*commit' "$SKILL_PATH"

# ✅ Run the artifact against a controlled input, assert what it did.
run bash "$HOOK" <<< "$payload"
[ "$status" -eq 2 ]
printf '%s' "$output" | grep -q 'DENIED'
```

Rules of thumb for this repo:

- **Scripts and hooks** — run them against controlled inputs; assert stdout, stderr,
  side effects, or exit codes.
- **Skills and agent-facing documents** — tested by the consuming agent's behavior,
  with the subagent-probe method in `tcs-helper:skill-author`
  (`reference/testing-with-subagents.md`), not by grepping their prose.
- **Prose written for humans** — earns no test at all.
- **Two artifacts that must agree** (a README listing fixtures that must exist, a
  link that must resolve) — a consistency check between them is legitimate. Derive
  one side from the filesystem rather than hard-coding both.

### Your code, not the framework

Test the contract your code makes at its boundaries — the route you register, the
query you emit, the payload you produce. Upstream mechanics are their maintainers'
tests to write. When upstream behavior genuinely surprised you, write one narrow
characterization test that names the assumption.

The same boundary applies inside your code: constructors, getters, and trivial
forwarding earn tests only when they validate, normalize, default, derive, enforce,
or cause a side effect.

### Gate

```
BEFORE writing the test body:
  Name the production change that would make this test fail.

  Cannot name one            → redesign around an observable behavior
  "The source text changed"  → run the artifact and assert its effects
  Only intentional decisions → change detector; test the behavior
                               that depends on the decision

  Confirm the expected value is derived WITHOUT the code under test.
  IF it reuses the code's logic or helpers:
    Replace it with a literal or hand-checked fixture
```

---

## Rule 2 — Exercise the real thing

A mock is earned, not assumed. Mock a dependency when it is genuinely slow, external,
non-deterministic, or destructive — not because wiring the real one is inconvenient.

A test whose every collaborator is a mock asserts that your mocks were configured the
way you configured them.

If a test needs so many mocks that the setup dwarfs the assertion, the design is the
finding — report it rather than mocking around it.

### Gate

```
BEFORE adding a mock:
  Why can't this use the real thing?

  "Slow" / "external" / "non-deterministic" / "destructive"  → mock is earned
  "Easier" / "the real one needs setup"                      → use the real thing
  More mocks than assertions                                 → design problem, report it
```

---

## The mutation check

Once green, ask: **what single-character change to the production code would this test
suite still pass?** If you can name one that matters, a test is missing.

`tcs-patterns:mutation-testing` automates this. The manual version is worth doing
whenever the suite feels thin.

---

## Warning signs

| Signal | What it usually means |
|---|---|
| The test passed the first time you ran it | It never proved it can fail — you skipped RED |
| The expected value is built by calling the code under test | Mirror assertion; it cannot fail |
| The assertion greps a `.md`, `.sh`, or config file for a phrase | String-presence trap; run the artifact instead |
| The assertion pins a constant or an exact message | Change detector; test the behavior that depends on it |
| Every collaborator is a mock | You are testing the mock configuration |
| Rewording a sentence broke a test | The test was reading text, not behavior |

---

*Rules 1 and 2, the gate functions, and the two named traps are adapted from
`obra/superpowers`' `writing-good-tests.md` (v6.2.0). The repo-specific guidance and
the shell examples are TCS's own — the string-presence examples are real findings
from an audit of this repo's bats suite.*
