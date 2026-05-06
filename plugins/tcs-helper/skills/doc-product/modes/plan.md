# `plan` Mode — Repo Analysis and `docs/` Skeleton Proposal

> **Status: TODO — implemented in Phase 4** of spec 010-doc-product-skill.
> See `docs/XDD/specs/010-doc-product-skill/plan/phase-4.md` (T4.1, T4.2).
>
> This stub exists so the mode router (`SKILL.md`) can dispatch successfully.
> When invoked today, this mode prints the message below and exits.

---

`plan` mode is not yet implemented. Phase 4 of the implementation plan delivers:

- Repo-type detection (Obsidian via `manifest.json`, Python via `pyproject.toml`, TCS plugin via `plugin.json`, generic fallback)
- Skeleton proposal from `templates/skeleton-{type}.md`
- Diff-vs-existing for repos that already have a `docs/` directory
- Author confirmation before any file writes; placeholders only, no fabricated content

To proceed today, use one of the implemented modes (when their phase lands):
- Phase 2 → `review` mode (reader-test killer feature)
- Phase 3 → `extract` mode (configuration reference from settings source)
- Phase 4 → `plan` and `write` modes
