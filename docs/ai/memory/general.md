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
