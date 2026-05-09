---
title: "Phase 5: Skills + References + Optional Components"
status: pending
version: "1.0"
phase: 5
---

# Phase 5: Skills + References + Optional Components

## Phase Context

**GATE**: Read all referenced files before starting this phase. Phases 1-4 must be COMPLETE.

**Specification References**:
- `[ref: SDD/§Building Block View — skills/setup, skills/status, references/]`
- `[ref: SDD/§Architecture Decisions ADR-10, ADR-11, ADR-12]` — Setup conflict policy, sentinel env-var, single-coder BP preset
- `[ref: PRD/§Feature M10, S1, S2]` — setup skill, branch protection, GHA template
- `[ref: PRD/§Open Questions OQ3]` — references plugin-internal only (decided)
- `[ref: research/integration.md §5, §6]` — Conflict-detection signatures, gh token scope matrix
- `[ref: SDD/§Detailed Feature Specifications]` — M2 traced flow (setup-relevant)

**Key Decisions**:
- **OQ3**: References stay plugin-internal — NOT installed in target repos.
- **OQ2 / ADR-12**: `--with-branch-protection` preset is single-coder (no PR-review-required).
- **ADR-11**: Setup skill exports `TCS_GIT_HELPERS_SETUP_ACTIVE=1` in a `(subshell)` block.
- **ADR-10**: Setup aborts on Husky / lefthook / pre-commit framework / simple-git-hooks; warns on `.git/hooks/` non-samples.
- Setup does NOT auto-commit (per M10 AC5); Marcus reviews and commits manually.

**Dependencies**:
- Phase 1 COMPLETE (lib/cache.sh for setup-lock).
- Phase 4 COMPLETE (templates to copy into target repos).
- Phase 3 COMPLETE (`git_status_audit.py` is the status skill backend).

---

## Tasks

This phase produces the user-facing slash-command skills, the reference knowledge base, and optional opt-in components (GHA, branch-protection).

- [ ] **T5.1 skills/setup/SKILL.md** `[activity: backend-api]`

  1. Prime: SDD §Skills — `/tcs-git-helpers:setup` `/tcs-git-helpers:setup` workflow; M10 acceptance criteria; ADR-10 conflict-detection signatures; ADR-11 sentinel; ADR-12 single-coder BP preset.
  2. Test: Write `tests/bats/skill_setup.bats` covering: clean repo → fresh install with version markers, `core.hooksPath=.githooks`; existing `.githooks/` no marker → conflict mode (per-file diff prompt); existing matching version → "up to date"; existing older version → per-file diff; Husky detected → abort + reference `migrating-from-husky.md`; lefthook/pre-commit/simple-git-hooks → abort with respective references; non-`.sample` files in `.git/hooks/` → warn + confirm; concurrent setup → second call fails on `.setup.lock`; stale lock (>5min) reclaimed; submodules detected and listed; setup does NOT auto-commit; `TCS_GIT_HELPERS_SETUP_ACTIVE=1` exported in subshell during file-write phase; `--update` mode shows per-file diff; `--with-gha` copies GHA template; `--with-branch-protection` calls `gh api` (mocked in tests).
  3. Implement: Create `plugins/tcs-git-helpers/skills/setup/SKILL.md` orchestrating the steps per SDD §Skills — `/tcs-git-helpers:setup`. Internal helper scripts allowed in `skills/setup/lib/` if needed for clarity. Subshell-wraps the `TCS_GIT_HELPERS_SETUP_ACTIVE=1` block.
  4. Validate: bats passes; manual: invoke `/tcs-git-helpers:setup` against `tests/fixtures/repos/clean-repo`, `…/with-husky`, `…/with-existing-hooks`; verify behaviors match acceptance criteria.
  5. Success: M10 AC1-AC6 all pass `[ref: PRD/M10]`; conflict policy matches ADR-10; sentinel scoping verified.

- [ ] **T5.2 skills/status/SKILL.md** `[activity: backend-api]` `[parallel: true]`

  1. Prime: SDD §Skills — `/tcs-git-helpers:status` `/tcs-git-helpers:status`; PRD acceptance criteria for status modes.
  2. Test: Write `tests/bats/skill_status.bats`: default mode outputs structured sections (branch, PR state, stale branches, plugin version, suggestions); `--brief` outputs single-line; `--cleanup` interactive purge with worktree-checked-out exclusion; `--json` outputs valid JSON consumable by tooling; `--overrides` reads audit log and prints last N events; stale-cache warning when >24h; works when `.githooks/` not installed (notes "run /tcs-git-helpers:setup").
  3. Implement: Create `plugins/tcs-git-helpers/skills/status/SKILL.md` invoking `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/git_status_audit.py [--brief|--cleanup|--json|--overrides]`. Frontmatter triggers on natural-language ("status", "stale branches", etc.) per skill-author conventions.
  4. Validate: bats passes; manual: invoke each mode; verify output.
  5. Success: All 4 modes operational `[ref: SDD/§Skills 6.5.2]`; integration with audit log and cache verified.

- [ ] **T5.3 references/INDEX.md + best-practices.md** `[activity: documentation]` `[parallel: true]`

  1. Prime: SDD §References (Knowledge Base) — citation pattern; PRD §Feature M*; references content convention (5-part structure: What goes wrong / How to detect / Fix / Prevention / Why).
  2. Test: Manual review for completeness.
  3. Implement: Create `references/INDEX.md` (topical index linking to all 14 references) and `references/best-practices.md` (landing/overview document referencing the more specific guides). All other references are separate tasks.
  4. Validate: All inter-doc links resolve.
  5. Success: Knowledge base navigation works; INDEX surfaces by topic and by failure mode.

- [ ] **T5.4 references/squash-merge-trap.md** `[activity: documentation]` `[parallel: true]`

  1. Prime: Marcus's existing finding text from brainstorm session (preserve verbatim where possible); Boucle worktree-guard documentation.
  2. Test: Manual review.
  3. Implement: Create `references/squash-merge-trap.md` from Marcus's finding, formalized into the 5-part structure. Include the `git cherry` detection, `git rev-list --parents` cross-check, cherry-pick-onto-fresh-branch recovery procedure.
  4. Validate: Marcus reviews; matches his original finding intent.
  5. Success: Cited from M3 denial messages `[ref: PRD/M3/AC1]`; recovery instructions are non-destructive only `[ref: research/security.md §8]`.

- [ ] **T5.5 references/ — branch-lifecycle, conventional-commits, pr-vs-commit-messages, force-push-safety, rebase-vs-merge, stale-branch-cleanup, working-tree-hygiene** `[activity: documentation]` `[parallel: true]`

  1. Prime: PRD §Feature M*, M5; existing best practices in `~/Kouzou/standards/git-conventions.md`; SDD §Cross-Cutting Concepts.
  2. Test: Manual review per file.
  3. Implement: Create 7 reference files following 5-part structure:
     - `references/branch-lifecycle.md` — Create→Work→PR→Merge→Cleanup flow
     - `references/conventional-commits.md` — Format spec, type/scope guide, examples
     - `references/pr-vs-commit-messages.md` — Squash-merge implication: PR title becomes commit
     - `references/force-push-safety.md` — `--force` vs `--force-with-lease`, shared branches
     - `references/rebase-vs-merge.md` — When each applies, pitfalls
     - `references/stale-branch-cleanup.md` — auto-delete-head-branches setting, fetch --prune
     - `references/working-tree-hygiene.md` — Clean state, stash-vs-branch for WIP
  4. Validate: All 5-part structure honored; recovery snippets non-destructive.
  5. Success: All references cited from at least one denial or nudge `[ref: PRD/Feature M*]`.

- [ ] **T5.6 references/ — destructive-ops, worktree-discipline, sandbox-and-git-config, migrating-from-husky, gh-token-hygiene** `[activity: documentation]` `[parallel: true]`

  1. Prime: research/security.md §5 (bypass surface for destructive-ops); Boucle worktree-guard limitations (worktree-discipline); user's earlier sandbox-and-.git/config feedback; integration §5 (Husky migration), §6 (gh token UX matrix).
  2. Test: Manual review.
  3. Implement: Create 5 references:
     - `references/destructive-ops.md` — All M7 patterns, alternatives, citing Boucle URLs
     - `references/worktree-discipline.md` — Worktree patterns, citing Boucle worktree-guard limitations
     - `references/sandbox-and-git-config.md` — Known sandbox interactions, `git_safe()` filter
     - `references/migrating-from-husky.md` — Step-by-step removal of husky, install of tcs-git-helpers
     - `references/gh-token-hygiene.md` — Token scope warnings, fine-grained tokens
  4. Validate: All 5-part structure honored.
  5. Success: All 5 references cited from setup-skill conflict messages or destructive-ops denials `[ref: ADR-10, ADR-12]`.

- [ ] **T5.7 templates/github-actions/pr-title-check.yml** `[activity: integration]` `[parallel: true]`

  1. Prime: PRD §Feature S2 (GHA opt-in); existing GHA examples (e.g. amannn/action-semantic-pull-request as a baseline reference, NOT included).
  2. Test: Write `tests/bats/gha_pr_title_check.bats` (lightweight syntax check; full GHA testing happens in Phase 6 via real PR).
  3. Implement: Create `templates/github-actions/pr-title-check.yml` validating PR title against same Conventional Commits regex as `commit-msg` hook. Re-uses regex from `lib/config_parser.sh` indirectly (hard-coded in YAML for portability).
  4. Validate: YAML syntactically valid; regex matches commit-msg regex; runs in `pull_request` event.
  5. Success: S2 AC1-AC2 pass `[ref: PRD/S2]`.

- [ ] **T5.8 Branch-protection preset implementation in setup skill** `[activity: integration]`

  1. Prime: ADR-12 single-coder preset; integration §2 GitHub API endpoints; PRD §Feature S1 acceptance criteria.
  2. Test: bats test stub: `--with-branch-protection` invokes `gh api -X PUT …/branches/<default>/protection` with the single-coder preset body (no `required_pull_request_reviews`, etc.); aborts when `repo` scope missing; warns on excessive scopes (e.g. `admin:org`); idempotent on re-run; failure mode test (mocked gh failure) does not roll back unrelated setup steps.
  3. Implement: Add `--with-branch-protection` mode to setup skill (or its helper) per ADR-12 + integration §6 token-scope matrix.
  4. Validate: bats passes; manual: invoke `--with-branch-protection` against a test repo (Marcus owns); verify settings via `gh api …/protection`.
  5. Success: S1 AC1-AC7 pass `[ref: PRD/S1]`.

- [ ] **T5.9 Phase 5 Validation** `[activity: validate]`

  Run all Phase 5 tests (bats) + shellcheck + Markdown link check. Manual:
  - Run `/tcs-git-helpers:setup` in a fresh fixture repo
  - Run `/tcs-git-helpers:status` in repos with various states
  - Verify all references render and inter-link correctly
  - Verify `--with-gha` and `--with-branch-protection` modes (idempotent re-runs)

  Success: M10, S1, S2 all met; references knowledge base ready; skills shippable.

---

## Deliverables

- `plugins/tcs-git-helpers/skills/{setup,status}/SKILL.md`
- `plugins/tcs-git-helpers/references/{INDEX, best-practices, squash-merge-trap, branch-lifecycle, conventional-commits, pr-vs-commit-messages, force-push-safety, rebase-vs-merge, stale-branch-cleanup, working-tree-hygiene, destructive-ops, worktree-discipline, sandbox-and-git-config, migrating-from-husky, gh-token-hygiene}.md`
- `plugins/tcs-git-helpers/templates/github-actions/pr-title-check.yml`
- `plugins/tcs-git-helpers/tests/bats/{skill_setup,skill_status,gha_pr_title_check}.bats`
- All linters and tests pass; references navigable.
