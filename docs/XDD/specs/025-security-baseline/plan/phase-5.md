---
title: "Phase 5: Skill, docs and end-to-end validation"
status: pending
version: "1.0"
phase: 5
---

# Phase 5: Skill, docs and end-to-end validation

## Phase Context

**GATE**: Read all referenced files before starting this phase.

**Specification References**:
- `[ref: SDD/Components; lines: 332-378]` K1
- `[ref: SDD/Internal API Changes; lines: 467-494]` CLI path resolution and exit codes the skill maps
- `[ref: SDD/User Interface & UX; lines: 901-925]` output order, diff header, choices, sandbox confirmation
- `[ref: SDD/Directory Map; lines: 380-435]` docs to modify
- `[ref: SDD/Quality Requirements; lines: 1054-1067]`
- `plugins/tcs-patterns/skills/patterns-setup/SKILL.md`, `plugins/tcs-helper/skills/observability-setup/SKILL.md` — structure and consent wording precedents

**Key Decisions**:
- ADR-2: the skill states what consent the tool can enforce and never claims more.
- ADR-6: the skill asks the developer to confirm `/sandbox` shows the sandbox active before passing `--sandbox-confirmed`.
- ADR-1: SKILL.md relays the verdict line and diffs verbatim and reads stdout only on exit 0.

**Dependencies**:
- Phase 4. T5.1 and T5.2 are parallel; T5.3 needs T5.1; T5.4 last.

---

## Tasks

Delivers the user-facing skill, its documentation, the manual container check, and an end-to-end proof that the PRD's success metrics hold.

- [ ] **T5.1 Skill narration (`SKILL.md`, `reference/workflow.md`)** `[activity: documentation]` `[parallel: true]`

  1. Prime: patterns-setup and observability-setup SKILL.md; UX section; setup sequence diagram `[ref: SDD/User Interface & UX; lines: 901-925]` `[ref: SDD/Primary Flow: setup; lines: 772-807]`
  2. Test (`tests/tcs-helper/test_security_baseline_skill.py`, pinned whole lines in order): frontmatter shape (`name`, short `description` with "Use when…" and triggers, `user-invocable: true`, `argument-hint`, `allowed-tools`); CLI lookup order exactly as the SDD; every call is `python3 -I -B "<cli>" …`; exit-code table maps 0/1/2/3; Never list includes: write without a diff shown and an explicit yes after it, paraphrase the diff or verdict, suggest an allow rule for the skill's own apply, pass `--sandbox-confirmed` without the developer's confirmation, run `apply` inside the sandbox; consent note relayed; body ≤ 17,000 bytes; no unescaped `$<digit>`; no `!` in composed commands; description ≤ 400 characters (patterns-setup precedent, `tests/test_patterns_setup_skill.py`), listing size measured before and after
  3. Implement: `plugins/tcs-helper/skills/security-baseline/SKILL.md` (Persona, Interface, Constraints, Workflow, Entry Point) and `reference/workflow.md` (setup loop, choice mapping to `--select/--deselect/--move`, sandbox confirmation, recovery after exit 3)
  4. Validate: `.venv/bin/pytest -q tests/tcs-helper/test_security_baseline_skill.py tests/test_skill_body_size.py tests/test_skill_dollar_substitution.py tests/test_shell_portability_lints.py tests/tcs-helper/test_prompt_lint_repo.py` (E2: placeholders like `<cli>` never alone on a line; E3: no dead links); run `tcs-helper:skill-author` audit before committing (memory rule)
  5. Success: `[ref: PRD/F9 AC2]` `[ref: PRD/Business Rules 1, 9, 10]` `[ref: SDD/F9.2, F9.14, R10]`

- [ ] **T5.2 Documentation and release notes** `[activity: documentation]` `[parallel: true]` `[model: routine]`

  1. Prime: SDD Directory Map docs list; `docs/ai/memory/tools.md` CHANGELOG rule `[ref: SDD/Directory Map; lines: 380-435]`
  2. Test: `tests/test_agents_md_tree.py` fails before the AGENTS.md entry and passes after (entry carries no `x.y.z` version — `test_states_no_plugin_version`); docs-sync rule A passes
  3. Implement: `AGENTS.md` tree entry inside the tcs-helper skills block (`AGENTS.md` lines 57-75, before the final `└── git-worktree/`), no version numbers in its comment; `README.md` tcs-helper table row (`| /security-baseline | … |`, lines 139-148); `plugins/tcs-helper/README.md` new `### Security` group heading with a `| Skill | Description |` table and a short section (modes, profiles, what it never does, consent limit); root `CHANGELOG.md`: `### Added` bullet under `## [Unreleased] — …` referencing #298; `plugins/tcs-helper/CHANGELOG.md`: new **first** heading exactly the next minor of `plugin.json` at merge time (today `## [4.6.0] - <date>`), not `[Unreleased]` — that is what requests a minor bump (`scripts/ci/check-changelog-version-sync.sh`)
  4. Validate: `.venv/bin/pytest -q tests/test_agents_md_tree.py`; `git diff --name-only origin/main... | bash scripts/ci/check-docs-sync.sh --changed-files -`; `bash scripts/ci/check-changelog-version-sync.sh` if it runs standalone
  5. Success: feature documented where the repo expects it `[ref: SDD/Implementation Boundaries]`

- [ ] **T5.3 Manual container check** `[activity: testing]` `[model: hard]`

  1. Prime: `plugins/tcs-git-helpers/tests/manual/host-sandbox-git-check.sh` precedent `[ref: SDD/Directory Map; lines: 380-435]` `[ref: SDD/Known Technical Issues; lines: 1174-1181]`
  2. Test: the script itself is the test — bash 3.2, exit 0 pass / 1 check failed / 2 prerequisite missing; it copies the current settings to a scratch home, runs `audit`, `plan`, `apply` on the copy, then starts `claude --version` and a `claude -p` smoke prompt with the copied settings (YOLO on and off) and checks startup succeeds; on Linux with bwrap installed it compares the probe with a real sandboxed command; never writes the real home
  3. Implement: `plugins/tcs-helper/tests/manual/security-baseline-container-check.sh`
  4. Validate: run it in this container and, by the developer, on the macOS host; record both results in the phase file
  5. Success: Claude Code still starts after setup, YOLO still works, git-helpers rules intact `[ref: PRD/Success Metrics "Quality"]`

- [ ] **T5.4 End-to-end validation** `[activity: validate]`

  - Run `./scripts/dev/test.sh pytest` (whole suite, failure set compared against a `main` baseline, not counts).
  - E2E fixture tests per profile in `test_security_baseline_cli.py`: audit → plan → apply → audit shows zero HIGH (PARTIAL counted at full severity) apart from ACCEPTED; a second plan selects nothing; `_digest()` proves audit wrote nothing.
  - Run `audit` read-only in this container and confirm the six 2026-11-27 gaps are reported; the developer decides whether to run `setup` for real.
  - Walk the skill once by hand (`/tcs-helper:security-baseline audit`, then `setup` up to the consent question, answering no) after copying it into the plugin cache and marketplace for testing; confirm nothing is written on "no".
  - Confirm every SDD criterion F1.1–F12.2, R10, E1–E4 has a passing test (traceability table in `plan/README.md`).
