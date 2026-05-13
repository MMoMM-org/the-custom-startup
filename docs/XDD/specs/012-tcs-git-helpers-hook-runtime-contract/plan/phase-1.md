---
title: "Phase 1: Self-contained hook bundle"
status: pending
version: "1.0"
phase: 1
---

# Phase 1: Self-contained hook bundle

## Phase Context

**GATE**: Read all referenced files before starting this phase.

**Specification References**:
- `[ref: PRD/Feature 1]` — post-merge writes stale cache reliably
- `[ref: PRD/Feature 5]` — silent failure modes eliminated
- `[ref: PRD/Feature 6]` — all four installed hooks + lib are one versioned bundle
- `[ref: SDD/Solution Strategy]` — self-contained per-repo install
- `[ref: SDD/Building Block View / Directory Map]` — file layout
- `[ref: SDD/ADR-1]` — sibling layout
- `[ref: SDD/ADR-2]` — `templates/githooks/tcs-git-helpers-version` source-of-truth
- `[ref: SDD/ADR-6]` — structured stderr one-liners
- `[ref: SDD/Implementation Examples / hook resolves its data dir without env vars]`

**Key Decisions**:
- Hooks become self-contained per-repo: source `lib-bundle.sh` via relative path; no `${CLAUDE_PLUGIN_*}` lookups at runtime.
- `_resolve_data_dir()` derives the data dir from `$HOME` + repo basename, respecting an explicit `CLAUDE_PLUGIN_DATA` override.
- Every guard path that prevents the hook's job completion emits a single-line structured stderr message and exits 0.
- `install_files.sh` writes a `<repo>/.githooks/tcs-git-helpers-version` file matching the substituted `__HOOK_BUNDLE_VERSION__` value.

**Dependencies**:
- None. This is the foundation. Phases 2 and 3 build on artifacts created here.

**What this phase delivers**: A complete, env-var-independent installed hook bundle. After Phase 1, a user who runs `/tcs-git-helpers:git-setup` in a repo gets four hooks that correctly write the stale-branch cache on every merge regardless of harness env state, with structured stderr messages for every degraded path.

---

## Tasks

- [x] **T1.1 `lib-bundle.sh` template with helpers** `[activity: build-platform]`

  1. **Prime**: Read SDD `[ref: SDD/Implementation Examples / hook resolves its data dir]`, SDD `[ref: SDD/ADR-6]` for stderr format, and the existing `plugins/tcs-git-helpers/scripts/nudge-hook.sh:108-110` defensive pattern (the working analog).
  2. **Test**: Write `plugins/tcs-git-helpers/tests/bats/lib-bundle.bats` covering:
     - `_resolve_data_dir` returns `${HOME}/.claude/plugins/data/tcs-git-helpers-<basename>/cache` when env vars unset
     - `_resolve_data_dir` respects an explicit `CLAUDE_PLUGIN_DATA` override
     - `_resolve_data_dir` exits non-zero when not inside a git repo
     - `_emit_skip <action> <reason> <suggestion>` writes one line to stderr in the format `tcs-git-helpers: <action> skipped — <reason>. <suggestion>.` and nothing to stdout
     - Library can be sourced under `set -uo pipefail` without unbound-variable errors
  3. **Implement**: Create `plugins/tcs-git-helpers/templates/githooks/lib-bundle.sh` exposing `_resolve_data_dir()`, `_emit_skip()`, and any small utilities the four hooks need (jq guard, `gh` guard, atomic write helper if shared). Bash 3.2 compatible. Stdout-silent.
  4. **Validate**: `bats tests/bats/lib-bundle.bats` passes; `shellcheck templates/githooks/lib-bundle.sh` clean.
  5. **Success**:
     - [ ] `_resolve_data_dir` produces the same path that harness-spawned `nudge-hook.sh` already writes to (so post-merge and nudge-hook share the cache dir) `[ref: SDD/Building Block View]`
     - [ ] Structured stderr format matches SDD `[ref: SDD/ADR-6]` exactly so future log-greppers can rely on it

- [x] **T1.2 Refactor four hook templates to self-contained, env-var-independent form** `[activity: build-platform]`

  1. **Prime**: Read existing `plugins/tcs-git-helpers/templates/githooks/{post-merge,pre-commit,commit-msg,pre-push}` to inventory every `${CLAUDE_PLUGIN_*}` usage and every silent `return 0`. Read SDD `[ref: SDD/Runtime View / Primary Flow: stale-cache write on post-merge]` and `[ref: SDD/Error Handling]` table.
  2. **Test**: Write `plugins/tcs-git-helpers/tests/bats/hooks-runtime-contract.bats` with one test per hook asserting:
     - Hook runs successfully in a throwaway git repo with `CLAUDE_PLUGIN_ROOT` and `CLAUDE_PLUGIN_DATA` both unset
     - Hook produces empty stdout, structured stderr (if any), exit 0
     - For `post-merge` specifically: the `<repo-hash>-stale-cache.{tsv,json}` files appear under the data dir after `git merge --no-ff` of an empty branch (using a `gh` stub fixture under `tests/fixtures/gh_stubs/`)
     - For every degraded path (no `gh`, no `gh` auth, no `jq`, data dir write failure): one stderr line in the structured format, exit 0
  3. **Implement**: Edit each of the four hook templates: remove all `${CLAUDE_PLUGIN_ROOT}` / `${CLAUDE_PLUGIN_DATA}` references; source `lib-bundle.sh` via `source "$(dirname "$0")/lib-bundle.sh"`; replace every silent `return 0` guard with `_emit_skip "<action>" "<reason>" "<suggestion>"; return 0`. Preserve the existing stderr suggestion line for stale-branch announcements (it's a feature, not a guard).
  4. **Validate**: `bats tests/bats/hooks-runtime-contract.bats` passes; `shellcheck` all four hook templates; verify by hand that grep for `CLAUDE_PLUGIN_` in `templates/githooks/*` returns 0 matches.
  5. **Success**:
     - [ ] All four hooks pass the runtime-contract test `[ref: PRD/AC-F1.3]`
     - [ ] `post-merge` writes the cache atomically on every merge with valid `gh` auth `[ref: PRD/AC-F1.1]`
     - [ ] Every guard path emits exactly one stderr line per the structured format `[ref: PRD/AC-F5.1]`
     - [ ] Stdout remains empty in all paths `[ref: PRD/AC-F5.2]`

- [x] **T1.3 `tcs-git-helpers-version` source file** `[activity: build-platform]` `[parallel: true]`

  1. **Prime**: Read SDD `[ref: SDD/ADR-2]`.
  2. **Test**: Write a one-line bats assertion in `tests/bats/hooks-version-bundle.bats`: the file `plugins/tcs-git-helpers/templates/githooks/tcs-git-helpers-version` exists and contains a single non-empty trimmed line matching `^[a-z0-9-]+$`.
  3. **Implement**: Create `plugins/tcs-git-helpers/templates/githooks/tcs-git-helpers-version` containing exactly `h1\n` (the inaugural bundle version).
  4. **Validate**: `bats tests/bats/hooks-version-bundle.bats` passes.
  5. **Success**:
     - [ ] File exists, is single-line, content `h1` `[ref: SDD/ADR-2]`

- [x] **T1.4 `install_files.sh` substitutes + copies + writes version file** `[activity: build-platform]`

  1. **Prime**: Read existing `plugins/tcs-git-helpers/skills/git-setup/lib/install_files.sh:40-100` (the version-banner substitution pattern). Read SDD `[ref: SDD/Directory Map / Repo install state]`.
  2. **Test**: Extend `tests/bats/install-files.bats` (or create new) covering:
     - After running install into a throwaway repo, `<repo>/.githooks/` contains all four hooks + `lib-bundle.sh` + `tcs-git-helpers-version`
     - Every installed hook contains the substituted version banner matching `templates/githooks/tcs-git-helpers-version` content (no `__HOOK_BUNDLE_VERSION__` leftover)
     - Installed `.githooks/tcs-git-helpers-version` content equals plugin's `templates/githooks/tcs-git-helpers-version` content (byte-equal after trim)
     - `lib-bundle.sh` is copied byte-equal (substitution applies only to hook files, not the lib)
  3. **Implement**: Modify `install_files.sh` to: read the bundle version from `templates/githooks/tcs-git-helpers-version`; substitute `__HOOK_BUNDLE_VERSION__` in each hook copy (alongside the existing `__TCS_GIT_HELPERS_VERSION__` substitution); copy `lib-bundle.sh` verbatim into `<repo>/.githooks/`; write `<repo>/.githooks/tcs-git-helpers-version` with the same content (atomic via `.tmp → mv`).
  4. **Validate**: bats install tests pass; `shellcheck install_files.sh` clean; manual smoke: install into `/tmp/test-repo`, inspect `.githooks/` listing.
  5. **Success**:
     - [ ] All five expected files present in `<repo>/.githooks/` after install `[ref: PRD/AC-F6.1]`
     - [ ] All hooks carry the same version banner `[ref: PRD/AC-F6.2]`
     - [ ] `tcs-git-helpers-version` byte-equal to plugin source `[ref: SDD/Quality Requirements/Reliability]`

- [ ] **T1.5 Phase 1 validation** `[activity: validate]`

  1. **Run** the full bash test suite for the plugin: `bats plugins/tcs-git-helpers/tests/bats/`.
  2. **Run** `shellcheck` across every modified or new shell file.
  3. **Manual integration check**: in a fresh throwaway repo, invoke `/tcs-git-helpers:git-setup`, confirm all files appear; run `git merge --no-ff` against an empty feature branch; confirm `<data-dir>/cache/<repo-hash>-stale-cache.{tsv,json}` files exist after the merge.
  4. **Cross-reference**: every PRD/AC row in the README mapping table that points at Phase 1 has a corresponding bats test that demonstrates the criterion.
  5. **Success**:
     - [ ] All bats tests green
     - [ ] shellcheck reports 0 issues on touched files
     - [ ] Manual integration check passes
     - [ ] No remaining `${CLAUDE_PLUGIN_ROOT}` or `${CLAUDE_PLUGIN_DATA}` references in `templates/githooks/*`
