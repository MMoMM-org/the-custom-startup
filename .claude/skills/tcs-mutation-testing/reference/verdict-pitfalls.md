# Verdict Pitfalls

A mutation verdict is a measurement, and each pitfall below produces a wrong one that reads as a
right one. Check them before trusting a KILLED or a SURVIVED.

---

## A fixture that closes a gap is not done until it failed against the mutant

A surviving mutant proves nothing asserts the behaviour. The fixture written to close the gap often
does not reach it, and a green suite then reads as "closed" when it means "still open, with a test
beside it".

1. Name the mutation in words before writing the fixture.
2. Inject it and confirm **that test** fails.
3. Confirm the other tests do not. A fixture that fails broadly is testing something else.

Shapes that look right and miss:

- **The library decides first.** `os.walk`, `glob`, `pathlib` and `shutil` categorise entries before
  your code sees them, and some swallow errors doing it (`os.walk` turns a failed `is_dir()` into a
  file). Read the source of the function you are feeding.
- **N instances across N containers** when the bug is about 2+ in one. Check the accumulator's
  scope: one per container is the natural way to write the fixture and the wrong way to test it.
- **An error branch no static configuration can reach.** If only a race reaches it, a committed
  fixture cannot. Assert the mechanism, or delete the branch.

Ask of any proposed fixture, including one an agent suggests: "did you run it against the mutant,
or infer that it works?"

## A "nothing changed" digest cannot see a write that reproduces the same bytes

A before/after digest proves "nothing was written" only if the wrong write would change the bytes.
With a deterministic serializer and a fixture where the wrong write produces the current value, the
file comes back identical and every form of "unchanged" passes: file digest, tree digest, field
compare.

For each "nothing was written" assertion, name the wrong write and say what it would produce. If
that equals the current bytes, **fix the fixture's state, not the assertion**: put the data where
the wrong write would be visible (e.g. a stored version behind the catalogue, so a stray upsert
moves it). Such a fixture kills the plausible mutant, not every conceivable one; do not call it
airtight.

## A comment justifying a narrower check is itself a claim

"Only this direction matters", "sufficient because", "the inverse is legitimate", "uses the same
path as", "deliberately not": a comment explaining why a weaker assertion is enough was written by
whoever chose the weaker option, and it reads as diligence. It is an unverified claim.

Name the artefact the comment cites and check it. Better: delete or weaken the thing the comment
defends and see whether anything fails. A helper documented as "the exact same path the real test
uses" that re-implements the loop instead of calling it is the common case.

## A stale `.pyc` can keep a mutant running after the restore

Python treats `__pycache__/*.pyc` as valid while the source's **mtime and size** match. A
same-size mutant (two statements swapped, two guards reordered, `<` to `>`) restored within the same
second leaves the mutant's bytecode cached as valid. Every later run, in fresh interpreters too,
executes the mutant.

| Check while poisoned | Result |
|---|---|
| `git diff` | clean |
| file digest | matches |
| `inspect.getsource` | correct source |
| behaviour | the mutant's |

Guards, strongest first:

1. **Delete `__pycache__` before each run**, including `tests/__pycache__` and any other module you
   mutated. A delete after the round only protects whoever runs next.
2. `python3 -m compileall --invalidation-mode checked-hash <dir>` makes the cache validate on
   content for a tree you will mutate repeatedly.
3. **Re-run the baseline at the end** as well as the start, and refuse to report verdicts if it is
   dirty.
4. `-B` / `PYTHONDONTWRITEBYTECODE=1` stops the harness creating a stale `.pyc`. It does not stop a
   run reading one that exists, so never describe it as protection.

`pytest -p no:cacheprovider` is unrelated: it disables `.pytest_cache`, not bytecode.
