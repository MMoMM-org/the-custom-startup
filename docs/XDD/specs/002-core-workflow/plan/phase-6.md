---
title: "Phase 6: Integration & Validation"
status: completed
version: "1.0"
phase: 6
---

# Phase 6: Integration & Validation

## Phase Context

**GATE**: Read all referenced files before starting this phase. All Phases 1-5 must be complete.

**Specification References**:
- `[ref: PRD/Feature 1–17]` — all acceptance criteria across all features
- `[ref: SDD/Constraints/CON-1–CON-7]` — all constraints must hold
- `[ref: SDD/Solution Strategy; lines: 116-129]` — architecture pattern and justification
- `[ref: SDD/Building Block View/Directory Map; lines: 173-258]` — complete directory map
- `[ref: PRD/Implementation Principles]` — cross-cutting rules (script-first, rg/fd, YOLO, handover)
- `[ref: SDD/ADR-1–ADR-5]` — all architecture decisions verified as implemented

**Key Decisions**:
- No new features in this phase — validation only.
- The install wizard (`./install.sh`) is the single integration test: if it installs `tcs-workflow` cleanly, the plugin structure is correct.
- YOLO mode is the primary regression check: all skills must work unattended.

**Dependencies**:
- All Phases 1–5 complete.

---

## Tasks

Integration, end-to-end testing, and final validation. Verifies all 17 PRD features against their acceptance criteria, confirms all SDD constraints hold, runs the full user journey from `/guide` through `/finish-branch`, and ensures the framework is installable and functional as a unit.

- [x] **T6.1 Plugin structure and install validation** `[activity: validate]`

  1. Prime: Read `install.sh` to understand plugin registration flow. Read `plugins/tcs-workflow/.claude-plugin/plugin.json`, `plugins/tcs-helper/.claude-plugin/plugin.json`, `plugins/tcs-team/.claude-plugin/plugin.json`. `[ref: SDD/Project Commands]`
  2. Test: `./install.sh` completes without error. Three plugins installed: `tcs-workflow`, `tcs-helper`, `tcs-team`. `plugins/tcs-start/` does not exist. All plugin.json files are valid JSON. `tcs-workflow/plugin.json` agents key includes `agents/tdd-guardian.md`. `tcs-team/plugin.json` agents key includes `the-architect/record-decision.md`. `[ref: PRD/Feature 1/AC-1.1–1.5]`
  3. Implement: Run `./install.sh`. If errors: fix the root cause (do not patch install.sh to skip validation). Verify plugin manifests with `python3 -c "import json; json.load(open('plugins/tcs-workflow/.claude-plugin/plugin.json'))"`. `[ref: SDD/CON-1]`
  4. Validate: `./install.sh` exit code 0. All three plugin.json files parse as valid JSON. Agent registration confirmed in manifests. `ls plugins/tcs-workflow/skills/` shows full skill tree (no `specify/`, `specify-requirements/`, `specify-solution/`, `specify-plan/`). `[ref: PRD/Feature 1/AC-1.1, AC-1.4]`
  5. Success: All three plugins install cleanly `[ref: PRD/Feature 1/AC-1.4]`; `tcs-start` absent `[ref: PRD/Feature 1/AC-1.1]`; agent registration correct `[ref: SDD/ADR-3]`

- [x] **T6.2 Skill directory and frontmatter compliance** `[activity: validate]`

  1. Prime: Read `[ref: SDD/Constraints/CON-2, CON-4]`. Review all new/modified SKILL.md files added in Phases 2-5. `[ref: SDD/Building Block View/Directory Map; lines: 173-258]`
  2. Test: For every SKILL.md in `plugins/tcs-workflow/skills/`, `plugins/tcs-helper/skills/`, `plugins/tcs-team/`: `name:` field matches directory name. `user-invocable:` is either `true` or `false` (not absent). Size ≤ 25 KB. For new skills: PICS structure present (Purpose/Invocation/Constraints/Steps or equivalent). `[ref: SDD/CON-2, CON-4, PRD/Implementation Principles]`
  3. Implement: Run compliance checks:
     ```bash
     # Check sizes
     find plugins/ -name "SKILL.md" -exec wc -c {} \; | awk '$1 > 25600 {print "OVERSIZED:", $2}'
     # Check name fields match directory
     for f in plugins/*/skills/*/SKILL.md plugins/*/skills/*/*/SKILL.md; do
       dir=$(basename "$(dirname "$f")")
       name=$(grep "^name:" "$f" | head -1 | sed 's/name: *//')
       [ "$dir" != "$name" ] && echo "MISMATCH: $f dir=$dir name=$name"
     done
     ```
     Fix any issues found. `[ref: SDD/CON-2]`
  4. Validate: No OVERSIZED output. No MISMATCH output. All new skills have `user-invocable:` set. YOLO pattern `[ "${YOLO:-false}" = "true" ]` present in all interactive skills. `[ref: SDD/CON-5]`
  5. Success: All skills ≤ 25 KB `[ref: SDD/CON-2]`; all name fields match directory names `[ref: SDD/CON-4]`; YOLO pattern consistent `[ref: SDD/CON-5]`

- [x] **T6.3 Cross-reference and path compliance** `[activity: validate]`

  1. Prime: List of old paths that must not appear anywhere: `.start/specs/`, `tcs-start:`, `specify/`, `specify-requirements/`, `specify-solution/`, `specify-plan/`, `specify-meta/`. New paths that must appear: `docs/XDD/`, `tcs-workflow:`, `xdd/`, `xdd-prd/`, `xdd-sdd/`, `xdd-plan/`, `xdd-meta/`. `[ref: SDD/ADR-1, ADR-5, PRD/Feature 11]`
  2. Test: No old path/name references in any plugin skill file. `rg "tcs-start:" plugins/` returns 0. `rg "specify-requirements|specify-solution|specify-plan|specify-meta" plugins/` returns 0 (within skill invocation contexts). `rg "\.start/specs" plugins/` returns 0. All `xdd-*` skill references use new names. `[ref: PRD/Feature 1/AC-1.3, Feature 11/AC-11.1–11.5]`
  3. Implement: Run each rg check. For any match found, trace to the skill and update via `/tcs-helper:skill-author`. Do not patch by regex — use skill-author for correctness. `[ref: SDD/CON-4]`
  4. Validate:
     ```bash
     rg "tcs-start:" plugins/   # must return 0 results
     rg "\.start/specs" plugins/ # must return 0 results
     rg "/specify-requirements|/specify-solution|/specify-plan" plugins/ # must return 0
     rg "docs/specs[^/]" plugins/ # must return 0
     ```
     All return 0. `[ref: PRD/Feature 1/AC-1.3, Feature 11]`
  5. Success: Zero stale references in plugin files `[ref: PRD/Feature 1/AC-1.3]`; all xdd-* invocations use new names `[ref: PRD/Feature 11/AC-11.1–11.5]`; migration complete `[ref: SDD/ADR-5]`

- [x] **T6.4 Tool compliance — rg/fd/fzf usage** `[activity: validate]`

  1. Prime: Read `[ref: SDD/CON-3]`. Check all modified/new skills for `grep`/`find` usage in bash blocks. New skills must use `rg`/`fd`. If absent: skills must fail gracefully with install hint. `[ref: PRD/Implementation Principles/Modern CLI tools required]`
  2. Test: No new occurrence of `grep` or `find` (without fallback) in new skill bash blocks. All file-search bash blocks use `rg` or `fd`. Graceful failure: if `rg` absent, message `echo "rg required: brew install ripgrep"`. Same for `fd`. `[ref: SDD/CON-3]`
  3. Implement:
     ```bash
     # Check for raw grep in new skills
     rg "^\s*(grep|find )" plugins/tcs-workflow/skills/{guide,xdd-tdd,verify,parallel-agents,receive-review}/SKILL.md
     rg "^\s*(grep|find )" plugins/tcs-helper/skills/{git-worktree,finish-branch,docs}/SKILL.md
     ```
     For each hit: check if it has a fallback or is in a non-search context (e.g., `grep` for TOML parsing is allowed). Replace bare `grep`/`find` file searches with `rg`/`fd`. `[ref: SDD/CON-3]`
  4. Validate: All file-search operations in new skills use `rg` or `fd`. Graceful error messages present for missing tools. `rg "command -v rg\|command -v fd" plugins/tcs-workflow/skills/guide/SKILL.md` — check present. `[ref: SDD/CON-3]`
  5. Success: All new skills use modern CLI tools for file search `[ref: SDD/CON-3]`; graceful failure with install hint when tools absent `[ref: SDD/CON-3]`

- [x] **T6.5 End-to-end journey: guide → implement → verify** `[activity: validate]`

  1. Prime: Read `[ref: PRD/User Journey Maps/Primary Journey: Feature Implementation Session]` (lines 110-122). This journey spans `/guide` → `/brainstorm` → `/xdd` → `/xdd-plan` → `/implement` → `/verify` → `/review` → `/receive-review` → `/finish-branch`. `[ref: PRD/User Journey Maps]`
  2. Test: Manually walk through the session recovery sub-journey (testable without full implementation):
     - Create a test branch. Create a fake plan file in `docs/XDD/specs/test-001/plan/phase-1.md` with one unchecked task.
     - Invoke `/guide` with no argument. Verify: (a) correct branch name announced; (b) unchecked task detected and stated; (c) `implement phase-1` announced as next step.
     - Verify decision tree: each of the 8 intent types resolves to a named skill.
     - Invoke `/verify` with no prior evidence. Verify: BLOCKED output and evidence commands listed.
     Clean up test artifact after validation. `[ref: PRD/Feature 7/AC-7.5, Feature 4/AC-4.2]`
  3. Implement: Execute the manual journey. Document any deviations. Fix any skill logic gaps found. `[ref: SDD/ADR-4]`
  4. Validate: `/guide` with open plan → correct state announced. `/verify` without evidence → BLOCKED. `/guide` intent=new feature → full sequence announced. `/guide` intent=code review → receive-review announced. `[ref: PRD/Feature 7/AC-7.1, 7.2, 7.3, 7.5]`
  5. Success: Guide correctly recovers from open plan state `[ref: PRD/Feature 7/AC-7.5]`; verify gates on evidence `[ref: PRD/Feature 4/AC-4.2]`; all 8 decision tree paths route to a named skill `[ref: PRD/Feature 7/AC-7.1]`

- [x] **T6.6 Python venv and test suite final run** `[activity: validate]`

  1. Prime: Read test files in `tests/tcs-helper/`. Confirm venv exists from T1.5. `[ref: SDD/CON-6]`
  2. Test: `source venv/bin/activate && python3 -m pytest tests/tcs-helper/ -v` — all tests pass, 0 failures. `rg "break-system-packages" .` returns 0 results. `[ref: SDD/CON-6]`
  3. Implement: Activate venv and run full test suite. Fix any test failures introduced by Phase 1-5 changes (path renames may affect test fixtures). `[ref: SDD/CON-6]`
  4. Validate: pytest output: `N passed, 0 failed`. No warnings about deprecated test patterns. `[ref: SDD/CON-6]`
  5. Success: All tcs-helper tests pass with venv `[ref: SDD/CON-6]`; `--break-system-packages` absent `[ref: SDD/CON-6]`

- [x] **T6.7 AGENTS.md and README documentation update** `[activity: validate]`

  1. Prime: Read `AGENTS.md` in root. Read `README.md`. Note all references to `tcs-start`, `.start/specs/`, old skill names. `[ref: PRD/Feature 1/AC-1.3]`
  2. Test: `rg "tcs-start" AGENTS.md README.md` returns 0 (or only in historical context, clearly marked as legacy). `rg "\.start/specs" AGENTS.md README.md` returns 0. Plugin names in AGENTS.md match: `tcs-workflow`, `tcs-helper`, `tcs-team`. XDD skill family names updated throughout. Skill invocation examples use new names. `[ref: PRD/Feature 1/AC-1.3]`
  3. Implement: Update `AGENTS.md`: rename `tcs-start` → `tcs-workflow` throughout. Update plugin directory reference from `plugins/tcs-start/` to `plugins/tcs-workflow/`. Update skill invocations: `tcs-start:brainstorm` → `tcs-workflow:brainstorm`, etc. Update spec path reference from `.start/specs/` to `docs/XDD/specs/`. Update README similarly. `[ref: PRD/Feature 1/AC-1.3]`
  4. Validate: `rg "tcs-start" AGENTS.md README.md` returns 0. `rg "\.start/specs" AGENTS.md README.md` returns 0. Plugin structure section in AGENTS.md reflects new directory map. `[ref: PRD/Feature 1/AC-1.3]`
  5. Success: AGENTS.md and README fully updated to reflect M1 changes `[ref: PRD/Feature 1/AC-1.3]`; no stale references to old names `[ref: PRD/Feature 1/AC-1.3]`

- [x] **T6.8 Phase 6 Final Validation** `[activity: validate]`

  - `./install.sh` — exit code 0; `tcs-workflow` listed; `tcs-start` absent.
  - All rg checks pass: no old names, no old paths, no `--break-system-packages`.
  - All skills ≤ 25 KB.
  - `python3 -m pytest tests/tcs-helper/ -v` — all pass.
  - Guide session recovery: open plan → correct state announced.
  - Verify without evidence: BLOCKED.
  - Decision tree: all 8 intents route to named skills.
  - AGENTS.md and README: no stale references.

  **PRD acceptance criteria coverage** (all must be verified):
  | Feature | Key ACs | Status |
  |---------|---------|--------|
  | F1: Plugin rename | AC-1.1 (name), AC-1.3 (docs), AC-1.4 (install), AC-1.5 (history) | ✅ |
  | F2: tdd-guardian | AC-2.1 (APPROVE/BLOCK), AC-2.3 (YOLO) | ✅ |
  | F3: xdd-tdd | AC-3.1 (RED gate), AC-3.3 (YOLO) | ✅ |
  | F4: receive-review | AC-4.1 (classify), AC-4.4 (tech reason), AC-4.6 (YOLO) | ✅ |
  | F5: parallel-agents | AC-5.1 (independence), AC-5.2 (conflict), AC-5.6 (YOLO) | ✅ |
  | F6: guide | AC-7.1 (orient), AC-7.5 (recovery), AC-7.7 (all skills reachable) | ✅ |
  | F7: brainstorm+ | AC-7.1 (spec-review offer), AC-7.3 (handoff) | ✅ |
  | F8: debug+ | AC-8.1 (hypothesis gate), AC-8.2 (anti-shortcut) | ✅ |
  | F9: review+ | AC-9.1 (SHA auto), AC-9.4 (conclude announcement) | ✅ |
  | F10: implement+ | AC-9.2 (tdd-guardian dispatch), AC-9.3 (spec compliance first) | ✅ |
  | F11: xdd-plan+ | AC-11.1 (RED/GREEN/REFACTOR tasks), AC-11.4 (conclude) | ✅ |
  | F12: git-worktree | AC-12.1 (create), AC-12.3 (cleanup) | ✅ |
  | F13: finish-branch | AC-13.2 (test gate), AC-13.3 (four options) | ✅ |
  | F14: docs | AC-14.1 (MCP check), AC-14.3 (cache) | ✅ |
  | F15: startup.toml + docs/XDD | AC-15.1 (dir tree), AC-15.3 (resolution), AC-15.4 (migration) | ✅ |
  | F16: xdd skill renames | AC-11.1–11.5 (all five renamed) | ✅ |
  | F17: CoD default-on | AC-17.1 (analyze), AC-17.3 (debug) | ✅ |

  **SDD constraint verification**:
  - CON-1 (bash 3.2): no `declare -A` — `rg "declare -A" plugins/` returns 0 □
  - CON-2 (≤ 25 KB): all SKILL.md ≤ 25600 bytes □
  - CON-3 (rg/fd): no bare grep/find in file-search contexts □
  - CON-4 (skill-author/agent-creator): all new/modified files authored via workflows □
  - CON-5 (YOLO pattern): `[ "${YOLO:-false}" = "true" ]` in all interactive skills □
  - CON-6 (Python venv): pytest passes with venv, no `--break-system-packages` □
  - CON-7 (plugin coexistence): tcs-workflow names don't conflict with superpowers/tcs-helper □
