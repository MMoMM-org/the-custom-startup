# `extract` Mode — Settings → Configuration Reference

> **Status: TODO — implemented in Phase 3** of spec 010-doc-product-skill.
> See `docs/XDD/specs/010-doc-product-skill/plan/phase-3.md`.
>
> This stub exists so the mode router (`SKILL.md`) can dispatch successfully.
> When invoked today, this mode prints the message below and exits.

---

`extract` mode is not yet implemented. Phase 3 of the implementation plan delivers:

- Source detection (TypeScript interface / JSON Schema / Pydantic / dataclass)
- Three independent parser scripts (`scripts/parse-ts-settings.sh`, `parse-jsonschema.sh`, `parse-pydantic.sh`)
- Explicit missing-dependency reporting per ADR-5: when a parser's runtime is absent (e.g. `python3` for Pydantic), the mode names the dependency, why it's needed, and the install command
- Diff-vs-existing on re-run (never overwrite silently)
- `[NEEDS DESCRIPTION]` markers for fields without source-of-truth descriptions

To proceed today, use one of the implemented modes (when their phase lands):
- Phase 2 → `review` mode (reader-test killer feature)
- Phase 3 → `extract` mode (settings parsers)
- Phase 4 → `plan` and `write` modes
