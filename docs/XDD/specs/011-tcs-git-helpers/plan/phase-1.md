---
title: "Phase 1: Plugin Foundation + Shared Libraries"
status: pending
version: "1.0"
phase: 1
---

# Phase 1: Plugin Foundation + Shared Libraries

## Phase Context

**GATE**: Read all referenced files before starting this phase.

**Specification References**:
- `[ref: SDD/§Plugin Layout]` — Directory structure
- `[ref: SDD/§Building Block View — Components]` — Component responsibilities
- `[ref: SDD/§Architecture Decisions ADR-2, ADR-3, ADR-5, ADR-6, ADR-7]` — Bash hot-path, .config parser, override single-shot, push-state cache, audit rotation
- `[ref: SDD/§Implementation Examples]` — `lib/override.sh` and `git_state.sh` traced walkthroughs
- `[ref: research/security.md §4]` — `.config` parser test corpus (MUST reject patterns)
- `[ref: research/performance.md §1]` — Empirical baselines for budget enforcement

**Key Decisions**:
- **ADR-3**: `.config` parser uses `printf -v` strict-allowlist; NO `eval`/`source`. Test corpus must reject 6+ injection patterns.
- **ADR-5**: Override consumption writes 5s sentinel file in `${CLAUDE_PLUGIN_DATA}/cache/override-consumed-<env-var>`.
- **ADR-7**: Audit log JSONL appends; rotate at 1MB to `.1`/`.2`.
- **CON-1**: Bash 3.2 compatibility — no `declare -A`, no `mapfile`/`readarray`, use `printf -v` and `case` glob for allowlists.
- **CON-9**: All command regexes MUST use `[[:space:]]+` (NEVER `\s+`, NEVER literal space). Word boundaries use `[[:<:]]`/`[[:>:]]` (NEVER `\b`). Empirically verified: `\s` and `\b` do NOT match in bash 3.2 `[[ =~ ]]`.

**Dependencies**:
- None (this is the foundation phase).

---

## Tasks

This phase establishes the plugin foundation: manifest, hook registration, shared `lib/*` modules with full test coverage, and test fixtures. All Phase 2-5 tasks depend on these libs being correct.

- [ ] **T1.1 Plugin Manifest + Hook Registration** `[activity: integration]` `[parallel: true]`

  1. Prime: Read `plugins/tcs-helper/.claude-plugin/plugin.json` and `plugins/tcs-helper/hooks/hooks.json` for shape conventions; SDD §Plugin Layout.
  2. Test: Write bats test `tests/bats/plugin_manifest.bats` asserting `claude --plugin-dir plugins/tcs-git-helpers` loads without error and registers expected hook events (PreToolUse, SessionStart, PostToolUse, PreToolUse:ExitWorktree).
  3. Implement: Create `plugins/tcs-git-helpers/.claude-plugin/plugin.json` (name, version 1.0.0, description, keywords, author) and `plugins/tcs-git-helpers/hooks/hooks.json` registering all 6 hook entry points referencing `${CLAUDE_PLUGIN_ROOT}/scripts/<name>.sh` (scripts themselves stubbed in this task; real logic in Phase 2-3).
  4. Validate: bats test passes; `claude --plugin-dir` succeeds; `/reload-plugins` does not warn.
  5. Success: Plugin loads cleanly `[ref: SDD/§Plugin Layout]`; hooks.json shape matches three-level nested format `[ref: SDD/§Implementation Context, hooks.md cache]`.

- [ ] **T1.2 README + CHANGELOG** `[activity: documentation]` `[parallel: true]`

  1. Prime: Read existing `plugins/tcs-helper/README.md` and `CHANGELOG.md`; PRD §Vision + §Value Proposition for messaging.
  2. Test: Manual review (no automated test for prose).
  3. Implement: Create `plugins/tcs-git-helpers/README.md` (overview, installation, basic usage, link to references) and `CHANGELOG.md` (initial v1.0.0 entry summarizing scope per PRD §Goals).
  4. Validate: Marcus reads through; English, concise, links resolve.
  5. Success: README mentions all 12 Goals at high level `[ref: PRD/§Feature Requirements]`; CHANGELOG follows TCS convention.

- [ ] **T1.3 lib/git_state.sh** `[activity: domain-modeling]` `[parallel: true]`

  1. Prime: SDD §Application Data Models BranchState; SDD §Implementation Examples `_is_branch_squash_merged`; ADR-9 algorithm.
  2. Test: Write `tests/bats/lib_git_state.bats` covering: `_get_branch_state` populates all expected vars; `_is_branch_squash_merged` returns 0 for all-`-` cherry output; returns 1 for mixed; `_is_branch_dangerously_merged` returns 1 when tip IS ancestor of default (merge-commit case is safe); `_bypass_state_check` returns 0 in each of {rebase, merge, cherry-pick, bisect, detached HEAD}; `_detect_default_branch` returns "main" or "master" via origin/HEAD chain.
  3. Implement: Create `scripts/lib/git_state.sh` exposing `_get_branch_state`, `_is_branch_squash_merged`, `_is_branch_dangerously_merged`, `_bypass_state_check`, `_detect_default_branch`, `_get_pr_state`, `git_safe` (filters known sandbox `.git/config` warnings).
  4. Validate: bats passes; shellcheck clean; bash 3.2 compat (no `declare -A`); `git -C "$PWD"` used everywhere (worktree-correctness per SDD §Worktree Behavior).
  5. Success: All branch-state APIs work `[ref: SDD/§Building Block View — git_state.sh]`; squash detection matches three traced scenarios `[ref: SDD/§Implementation Examples]`.

- [ ] **T1.4 lib/config_parser.sh** `[activity: domain-modeling]` `[parallel: true]`

  1. Prime: SDD §Implementation Examples Bash parser sketch; security.md §4 MUST-reject corpus.
  2. Test: Write `tests/bats/lib_config_parser.bats` with security corpus: `TCS_PROTECTED_BRANCHES=$(rm -rf ~)` rejected; backticks rejected; newline injection rejected; unknown key `EVIL=1` rejected; type mismatch `TCS_REQUIRE_SCOPE=true` rejected; path traversal `TCS_HOOK_EXCLUDE_PATHS_FILE=../../etc/passwd` rejected. Also: all `.config.example` lines uncommented are accepted; quoted values strip outer quotes; comments and blank lines tolerated.
  3. Implement: Create `scripts/lib/config_parser.sh` exposing `parse_tcs_config <file>` using `printf -v` strict allowlist per ADR-3.
  4. Validate: All security-corpus tests pass; shellcheck clean; bash 3.2 compat.
  5. Success: 6+ injection patterns rejected `[ref: research/security.md §4]`; parser ≤5ms per invocation `[ref: SDD/§Quality Requirements]`.

- [ ] **T1.5 lib/pattern_match.sh** `[activity: domain-modeling]` `[parallel: true]`

  1. Prime: PRD §Feature M7 destructive patterns table; SDD §Implementation Examples block-bad-git-ops dispatcher; CON-9 `[[:space:]]+` mandate.
  2. Test: Write `tests/bats/lib_pattern_match.bats` testing all 14+ destructive patterns: each pattern matches its canonical form AND tab-separated AND multi-space AND compound (`cd foo && git ...`). Each pattern's NEGATIVE matches: e.g. `git[[:space:]]+push.*--force[[:>:]]` does NOT match `--force-with-lease`. **All patterns must use `[[:space:]]+` and `[[:>:]]` — never `\s+` or `\b` (PCRE extensions; do not match in bash 3.2 POSIX ERE).**
  3. Implement: Create `scripts/lib/pattern_match.sh` with `_match_command <command> <pattern>` helper using bash `[[ =~ ]]`. Pattern constants exported as bash vars (named PATTERN_PUSH, PATTERN_RESET_HARD, etc.) for re-use.
  4. Validate: bats passes; positive AND negative matches correct; shellcheck clean.
  5. Success: All 14+ M7 patterns tested in both forms `[ref: PRD/§Feature M7]`; no false positives on `--force-with-lease` `[ref: SDD/§block-bad-git-ops dispatcher]`.

- [ ] **T1.6 lib/override.sh** `[activity: domain-modeling]`

  1. Prime: SDD §Implementation Examples `_check_and_consume_override`; ADR-5 traced walkthrough; M12 acceptance criteria.
  2. Test: Write `tests/bats/lib_override.bats` covering: env-var set → consumed (sentinel written, return 0); env-var unset → return 1; env-var set + sentinel <5s → double-tap denial (return 1, stderr); env-var set + sentinel >5s → consumed normally; master `CLAUDE_ALLOW_GIT_BAD_OPS` consumed with `OVERRIDE_MASTER=1`; mkdir failure does not block (graceful degradation).
  3. Implement: Create `scripts/lib/override.sh` exposing `_check_and_consume_override <rule>` per SDD §Implementation Examples. Sentinel file path: `${CLAUDE_PLUGIN_DATA}/cache/override-consumed-<env_var>`.
  4. Validate: bats passes including the timing tests (use `sleep 6` or fake clock); shellcheck clean; bash 3.2 compat.
  5. Success: Single-shot semantics work via 5s sentinel `[ref: ADR-5]`; master override emits loud warning `[ref: PRD/M7 AC3]`.

  Depends on: T1.7 (cache.sh) for sentinel-file IO helpers, T1.8 (audit_log.sh) for consumption-event logging.

- [ ] **T1.7 lib/cache.sh** `[activity: domain-modeling]` `[parallel: true]`

  1. Prime: SDD §Cache Schemas (TSV, JSON, lock file); ADR-4 hybrid format; SDD §Stale-Branch Cache for SessionStart.
  2. Test: Write `tests/bats/lib_cache.bats` covering: `_repo_hash` returns 12-char SHA1 prefix; atomic mv writes (`<file>.tmp` then `mv`); reads tolerate missing files; PID-file lock acquired AND released; stale lock (>5min) auto-reclaims; concurrent write attempt blocks then succeeds in serial; TSV with comment-header parses with `head`/`grep -v '^#'`/`wc -l`.
  3. Implement: Create `scripts/lib/cache.sh` exposing `_repo_hash`, `_read_stale_cache_tsv`, `_write_stale_cache (TSV+JSON)`, `_read_pr_state_cache <branch>`, `_write_pr_state_cache <branch> <state>`, `_acquire_lock`, `_release_lock`. Uses `${CLAUDE_PLUGIN_DATA}/cache/`.
  4. Validate: bats passes; lock contention serializes; corrupt cache returns empty (no crash).
  5. Success: Cache schemas match SDD §Data Storage Changes `[ref: SDD/§Cache Schemas]`; lock works without flock (PID-file + kill -0).

- [ ] **T1.8 lib/audit_log.sh** `[activity: domain-modeling]` `[parallel: true]`

  1. Prime: SDD §Audit Log Schema; ADR-7 rotation policy; M12 AC3-AC5.
  2. Test: Write `tests/bats/lib_audit_log.bats` covering: `_audit_log` appends one valid JSON line per call; field order stable; rotation at exactly 1MB threshold (using fixture file at 1024000 bytes); existing `.1` rotates to `.2`; `.3` overwritten on subsequent rotation; `_audit_log` returns 0 even when audit file is unwritable (chmod 000); stderr error logged.
  3. Implement: Create `scripts/lib/audit_log.sh` exposing `_audit_log <key=value> [<key=value>...]` building JSON via `printf` + `jq -c -n` (or pure printf escape). Rotation in `_rotate_if_oversized`. File: `${CLAUDE_PLUGIN_DATA}/audit/overrides.jsonl`.
  4. Validate: bats passes; JSON validity checked with `jq .`; rotation thresholds correct; write-failure does not block.
  5. Success: JSONL append works `[ref: M12/AC3]`; 1MB rotation works `[ref: M12/AC4]`; write-failure non-blocking `[ref: M12/AC5]`.

- [ ] **T1.9 Test Fixtures + Synthetic Repos** `[activity: test-fixtures]` `[parallel: true]`

  1. Prime: research/performance.md §7 worst-case scenarios; SDD §Risks Implementation Gotchas.
  2. Test: Fixture sanity check — each fixture file is valid; synthetic repos have expected branch/PR states.
  3. Implement: Create `tests/fixtures/`:
     - `repos/` — synthetic git repos with: clean+unmerged branch, dirty branch, squash-merged branch, merge-commit-merged branch, branch with closed PR, detached HEAD state, rebase-in-progress state, 50-branch repo, 1000-commit branch
     - `commands/destructive_corpus.txt` — 14+ canonical destructive patterns + tab/space variants + compound forms (positive cases) AND legitimate variants (`git push --force-with-lease`, etc., negative cases)
     - `commands/bypass_corpus.txt` — alias-like commands, function-like, subshells (positive/negative as documented)
     - `configs/{good,bad,malicious}.config` — security-corpus config files (good: all valid keys; bad: malformed; malicious: injection patterns)
     - `gh_stubs/` — mock `gh` binary returning canned JSON for offline testing
  4. Validate: All fixtures load; synthetic repos pass `git fsck`; corpus files end with newlines.
  5. Success: Fixtures support all Phase 2-6 test cases; coverage scenarios from research §7 are reproducible `[ref: research/performance.md §7]`.

- [ ] **T1.10 Phase 1 Validation** `[activity: validate]`

  Run all Phase 1 bats tests + shellcheck + (where applicable) ruff. Verify:
  - All 6 lib modules pass tests
  - Plugin loads via `claude --plugin-dir`
  - Hook registration is structurally valid (PreToolUse, PostToolUse, SessionStart, PreToolUse:ExitWorktree)
  - Test fixtures reproduce all worst-case scenarios from research §7
  - Spec compliance: every task above has `[ref: ...]` linking to PRD or SDD section

  Success: Phase 1 deliverables ready; Phase 2 can begin.

---

## Deliverables

- `plugins/tcs-git-helpers/.claude-plugin/plugin.json` (manifest)
- `plugins/tcs-git-helpers/hooks/hooks.json` (hook registration)
- `plugins/tcs-git-helpers/README.md` + `CHANGELOG.md`
- `plugins/tcs-git-helpers/scripts/lib/{git_state,config_parser,pattern_match,override,cache,audit_log}.sh`
- `plugins/tcs-git-helpers/tests/bats/{plugin_manifest,lib_*}.bats`
- `plugins/tcs-git-helpers/tests/fixtures/{repos,commands,configs,gh_stubs}/*`
- All shellcheck-clean and bats-passing.
