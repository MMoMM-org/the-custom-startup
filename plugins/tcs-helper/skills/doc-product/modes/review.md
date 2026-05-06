# `review` Mode — Persona-Driven Reader Test via `claude -p`

> **Status: TODO — implemented in Phase 2** of spec 010-doc-product-skill.
> See `docs/XDD/specs/010-doc-product-skill/plan/phase-2.md`.
>
> This stub exists so the mode router (`SKILL.md`) can dispatch successfully.
> When invoked today, this mode prints the message below and exits.

---

`review` mode is not yet implemented. Phase 2 of the implementation plan delivers the killer feature of this skill:

- Persona-driven reader testing via headless `claude -p` subprocesses (per ADR-2)
- Default personas (`templates/personas-default.md`) with project-local override (`.claude/doc-personas.md`) per ADR-4
- Multi-page corpus per question — each question declares its own `pages: [...]` list, concatenated into a single `claude -p` call
- Strict 100% pass threshold on required questions
- Stateless: gap report rendered inline in the parent conversation, never persisted to disk (per ADR-3 / ADR-6)

Prerequisite when implemented: the `claude` CLI must be installed and authenticated. When the prereq is missing, the mode exits before any subprocess call with a setup-instruction message.

To proceed today, use one of the implemented modes (when their phase lands):
- Phase 2 → `review` mode (this one — coming next)
- Phase 3 → `extract` mode
- Phase 4 → `plan` and `write` modes
