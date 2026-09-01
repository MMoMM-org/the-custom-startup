# General — the-custom-startup
<!-- Conventions, naming rules, code style, git workflow. Updated: 2026-09-01 -->
<!-- What goes here: how files are named, folder structure, style choices, branch conventions -->
<!-- What does NOT go here: tool-specific quirks (→ tools.md), domain rules (→ domain.md) -->
<!-- Form: one rule + its tell + one pointer, ≤ 250 chars. See memory-add/reference/category-formats.md -->

<!-- 2026-05-09 -->
- **Teammates on one branch share the git index** — an in-flight `git add` from a sibling lands in your next `git commit`, even with explicit paths. → Accept the bundling and review per file, or give each teammate a worktree. [spec-011 T1.4]
- **Scope reviewer prompts to a commit range, not the working tree** — reviewers scan by path and then flag a teammate's uncommitted work as your task's extras. → Name the range, the expected files, and say to ignore the rest. [spec-011 T1.1]
- **Match PRD-mandated user-facing strings verbatim in tests**, punctuation and markdown included — a substring match lets the implementer drift from the spec uncaught. → Pin the exact string. [spec-011 M7 AC3]

<!-- 2026-05-22 -->
- **Scaffold a multi-task SKILL.md with `<!-- T2.X will populate -->` placeholders** — each later task grep-replaces its own without touching siblings, and `grep -c` on the marker tracks RED→GREEN (zero left is green). [spec-013]

<!-- 2026-07-02 -->
- **Assert evolving frontmatter fields by prefix, not exact match** — an exact `grep -q` on `argument-hint` turned a spec-mandated change into a false regression. → Anchor on the stable substring. [spec-016]
