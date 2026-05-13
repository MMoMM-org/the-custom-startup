---
title: "Phase 3: CI maintainer-contract gate + E2E lockdown"
status: pending
version: "1.0"
phase: 3
---

# Phase 3: CI maintainer-contract gate + E2E lockdown

## Phase Context

**GATE**: Read all referenced files before starting this phase.

**Specification References**:
- `[ref: PRD/Feature 6]` — atomic bundle + CI-enforced version bump
- `[ref: PRD/Constraints/CON-4]` — maintainer contract enforced by CI, not honor-system
- `[ref: SDD/ADR-7]` — CI gate at `scripts/ci/check-hook-bundle-version.sh`
- `[ref: SDD/Risks and Technical Debt / Maintainer forgets to bump]`
- `[ref: SDD/Deployment View]` — no staged rollout; drift-check is non-breaking

**Key Decisions**:
- The CI gate runs on every PR, compares the diff of `templates/githooks/` against the diff of `templates/githooks/tcs-git-helpers-version`. If the directory changed but the version file did not bump in the same diff range, the build fails with a message naming the unbumped files.
- The gate runs in a new lightweight GitHub Actions workflow (the existing `release.yml` runs on tag push, not on PRs — adding the gate there would let unbumped PRs merge).
- End-to-end test installs the bundle, exercises the install → merge → cleanup loop in a throwaway repo, asserts cache file appears and `--cleanup` reports the right candidates.

**Dependencies**:
- Phases 1 and 2 complete: the bundle exists, the drift check is wired in, the version file is the documented source of truth.

**What this phase delivers**: The fix is now self-defending. Any future contributor who modifies a hook or shared lib without bumping `templates/githooks/tcs-git-helpers-version` is caught at PR review. A full end-to-end test demonstrates the install → merge → cleanup loop works in a real-ish repo. Plugin CHANGELOG and README updated.

---

## Tasks

- [ ] **T3.1 CI gate script `check-hook-bundle-version.sh`** `[activity: build-platform]`

  1. **Prime**: Read SDD `[ref: SDD/ADR-7]`. Inventory the file patterns that count as "hook bundle code": `plugins/tcs-git-helpers/templates/githooks/**` (recursively). Note that the version file itself lives at that path — the rule is "if any file in this dir changed AND the version file did not bump in the same range, fail."
  2. **Test**: Write `plugins/tcs-git-helpers/tests/bats/ci-bundle-gate.bats` covering:
     - Diff range with no `templates/githooks/*` changes → exit 0
     - Diff range with hook template change AND `tcs-git-helpers-version` bump → exit 0
     - Diff range with hook template change but NO version-file bump → exit non-zero, stderr names the offending files and tells maintainer what to do
     - Diff range with `lib-bundle.sh` change but NO version-file bump → exit non-zero, same message
     - Diff range with comment-only / whitespace-only change to a hook template → still exit non-zero (any diff in the dir counts — per SDD trade-off accepted)
  3. **Implement**: Create `plugins/tcs-git-helpers/scripts/ci/check-hook-bundle-version.sh`. Takes a base ref (default `origin/main`) and head ref (default `HEAD`). Uses `git diff --name-only <base>..<head>` to list changed paths. If any path matches `plugins/tcs-git-helpers/templates/githooks/*` AND `plugins/tcs-git-helpers/templates/githooks/tcs-git-helpers-version` is NOT in the changed-paths list, fail with a clear stderr message.
  4. **Validate**: bats tests pass; `shellcheck` clean; manual: clone the repo, create a branch that edits a hook without bumping the version, run the script, observe failure with the right message.
  5. **Success**:
     - [ ] Maintainer contract enforced mechanically `[ref: PRD/AC-F6.3, CON-4]`
     - [ ] False positive on no-op diffs is acceptable per SDD trade-off `[ref: SDD/ADR-7 trade-offs]`

- [ ] **T3.2 Wire CI gate into a PR workflow** `[activity: build-platform]`

  1. **Prime**: Read `.github/workflows/release.yml` to understand the existing workflow shape. Note that it triggers on `push: tags` not on PRs — this is why a new file is needed rather than amending it.
  2. **Test**: Write a smoke test asserting the workflow file is valid YAML and references the gate script. (Tested implicitly by GitHub Actions on the first PR; no local test infrastructure required.)
  3. **Implement**: Create `.github/workflows/hook-bundle-version-check.yml`:
     ```yaml
     name: Hook bundle version check
     on: [pull_request]
     jobs:
       check:
         runs-on: ubuntu-latest
         steps:
           - uses: actions/checkout@v4
             with: { fetch-depth: 0 }
           - run: plugins/tcs-git-helpers/scripts/ci/check-hook-bundle-version.sh origin/${{ github.base_ref }} HEAD
     ```
     Mark the job as required for merge in branch-protection settings (manual step, document in T3.4).
  4. **Validate**: Open a throwaway PR that touches a hook template without bumping the version; observe the check fail on GitHub. Close without merging.
  5. **Success**:
     - [ ] PRs that violate the contract are blocked from merging `[ref: PRD/AC-F6.3]`

- [ ] **T3.3 End-to-end test: install → merge → cleanup** `[activity: test-strategy]`

  1. **Prime**: Read `plugins/tcs-git-helpers/tests/e2e/` to inventory existing E2E patterns. Read SDD `[ref: SDD/Runtime View / Primary Flow: stale-cache write on post-merge]` and `[ref: SDD/Runtime View / Primary Flow: skill drift-check on --cleanup]`.
  2. **Test design** (this task IS the test):
     - Setup: throwaway git repo, simulate `/tcs-git-helpers:git-setup` install (call `install_files.sh` directly with the repo path)
     - Inject a `gh` stub that returns one merged PR matching a local branch name
     - Run `git merge --no-ff feature-branch`
     - Assert: `<data-dir>/cache/<repo-hash>-stale-cache.tsv` and `.json` exist with the expected entry
     - Invoke `git_status_audit.py --cleanup` (non-interactive mode)
     - Assert: stdout lists the branch as a candidate
     - Mutate `.githooks/tcs-git-helpers-version` to `h999`
     - Re-invoke `--cleanup`
     - Assert: exit code 1, stderr contains drift message
  3. **Implement**: Write `plugins/tcs-git-helpers/tests/e2e/test_bundle_lifecycle.py` (pytest) implementing the above scenario. Reuse fixture patterns from existing e2e/python tests.
  4. **Validate**: `pytest tests/e2e/test_bundle_lifecycle.py` passes.
  5. **Success**:
     - [ ] Full install → merge → cleanup loop demonstrably works `[ref: PRD/AC-F1, F2, F3, F4]`
     - [ ] Drift scenario produces the right behavior end-to-end `[ref: PRD/AC-F4.1]`

- [ ] **T3.4 Documentation: CHANGELOG + README + branch-protection note** `[activity: design-system]` `[parallel: true]`

  1. **Prime**: Read `plugins/tcs-git-helpers/CHANGELOG.md` for entry format. Read `plugins/tcs-git-helpers/README.md` to find sections that describe install behavior or version model.
  2. **Test**: A maintenance script (or manual review) verifies CHANGELOG entry exists for the new bundle version.
  3. **Implement**:
     - Add a CHANGELOG entry describing the new self-contained install, `tcs-git-helpers-version` marker file, and the user-visible drift prompt
     - Update README under the "How it works" section (or equivalent) to explain that hooks are self-contained, that updates surface via drift prompts when running `/tcs-git-helpers:git-audit`, and that the user re-runs `/tcs-git-helpers:git-setup` to update
     - Add a maintainer-facing note (in README or CONTRIBUTING.md) describing CON-4: any change to `templates/githooks/` must bump `tcs-git-helpers-version`
     - Add a manual step note: the GitHub branch-protection rule must mark `Hook bundle version check` as required for PR merge (cannot be automated from this PR)
  4. **Validate**: Read-through by hand; CHANGELOG entry parses cleanly with the existing toolchain (if any).
  5. **Success**:
     - [ ] User-facing changes documented `[ref: PRD/Open Questions Q1 + Q5 resolutions]`
     - [ ] Maintainer contract documented `[ref: PRD/CON-4]`

- [ ] **T3.5 Plugin version bump + Phase 3 validation** `[activity: validate]`

  1. **Bump** `plugins/tcs-git-helpers/.claude-plugin/plugin.json` from 2.0.1 to 2.1.0 (minor — new install-state behavior). The `HOOK_BUNDLE_VERSION` (`tcs-git-helpers-version`) stays at `h1` from T1.3 since this is the inaugural bundled release — subsequent hook changes will bump it.
  2. **Run** all test suites:
     - `bats plugins/tcs-git-helpers/tests/bats/`
     - `pytest plugins/tcs-git-helpers/tests/python/`
     - `pytest plugins/tcs-git-helpers/tests/e2e/`
     - `shellcheck plugins/tcs-git-helpers/{scripts,templates,skills}/**/*.sh`
  3. **Cross-reference**: every PRD AC row in the README mapping table is covered by at least one test that demonstrates the criterion (file paths captured).
  4. **Manual smoke**: in this repo, run `/tcs-git-helpers:git-setup`; observe install completes; do a real `git merge`; verify cache files appear; run `--cleanup`; verify it returns candidates matching `git branch --merged main`.
  5. **Success**:
     - [ ] All test suites green
     - [ ] No remaining `[NEEDS CLARIFICATION]` markers in any spec doc
     - [ ] Manual smoke loop on this repo passes (install → merge → cleanup → drift)
     - [ ] Spec/012 ready for merge to main
