# General — the-custom-startup
<!-- Conventions, naming rules, code style, git workflow. Updated: 2026-09-01 -->
<!-- What goes here: how files are named, folder structure, style choices, branch conventions -->
<!-- What does NOT go here: tool-specific quirks (→ tools.md), domain rules (→ domain.md) -->
<!-- Form: one rule + its tell, ≤ 250 chars, no spec refs. See memory-add/reference/category-formats.md -->

<!-- 2026-05-09 -->
- **Teammates on one branch share the git index** — an in-flight `git add` from a sibling lands in your next `git commit`, even with explicit paths. → Accept the bundling and review per file, or give each teammate a worktree.
- **Match PRD-mandated user-facing strings verbatim in tests**, punctuation and markdown included — a substring match lets the implementer drift from the spec uncaught. → Pin the exact string.

<!-- 2026-05-22 -->
- **Scaffold a multi-task SKILL.md with `<!-- T2.X will populate -->` placeholders** — each later task grep-replaces its own without touching siblings, and `grep -c` on the marker tracks RED→GREEN (zero left is green).

<!-- 2026-07-02 -->
- **Assert evolving frontmatter fields by prefix, not exact match** — an exact `grep -q` on `argument-hint` turned a spec-mandated change into a false regression. → Anchor on the stable substring.

<!-- 2026-09-04 -->
- **A skill's examples silently language-lock its grep step** — `testing`'s smell patterns were Jest-shaped, so a pytest suite grepped clean and read as passing. → Have the step name the framework first, then list the equivalents.
- **`tr` maps byte to byte** — `tr ' ' '█'` writes only the first byte of a multibyte replacement, so a rendered bar is invalid UTF-8 shown as replacement glyphs. → Append whole characters in a loop.

<!-- 2026-09-10 -->
- **Golden-output fixtures live in `tests/fixtures/<area>/<task>_golden/`** — a committed `regenerate.py` diffs (`--write` captures once) against the frozen `.txt`; a sibling test runs it. → Never `--write` to silence a mismatch.
- **Build a fixture that must NOT be a git repo outside the worktree** — inside it, `check-ignore` answers with this repo's `.gitignore`, so the "not a repository" branch never runs. → `tempfile.TemporaryDirectory()` at run time.

<!-- 2026-09-12 -->
- **A bats needle can match the fixture name, not the message** — `_assert_contains "$output" "ignored"` passed because the work dir was `not-ignored`; the message says `does not ignore`. → Assert literal wording, then blank it and confirm red.
- **A reported defect is usually one of several** — sweeping for the class behind a reported instance found 9 shapes where 1 was named, 3 emit sites where 1 was, 4 constant pairs where 1 was. → Fix the class; the instance is the cheapest part.
- **Green is not evidence until the behaviour is broken** — a test that reads correctly can pass for a reason unrelated to what it claims, and reading the body does not reveal it. → Mutate what it covers; if it stays green it proves nothing.
- **Two specs' `SDD-AC-n` numbers collide** — each numbers from 1, so a bare reference in a file predating the current spec cites the older one's table. → Prefix every acceptance-criterion reference with its spec.

<!-- 2026-10-08 -->
- **A fixture file matched by `.gitignore` is tested nowhere** — absent from every clone, and pruned locally by the detect walk's git-ignore check, so a mutant survives both. → Re-include its directory with a `!path/` line and track it.
